"""Forward-only migration of the evidence store.

Three rules, in order of importance:

1. **Forward only.** A store written by a newer build than this one is refused, loudly, before any
   other statement runs. Reading it and then writing rows this build cannot express would corrupt
   evidence that a later (correct) build has to be able to trust. There is no downward path here and
   no ``--force``: the answer to "too new" is to use the newer build.
2. **v1 rows are never rewritten.** They keep ``schema_version = 1`` and NULL provenance. The store
   upgrades its *structure*; it does not upgrade anyone's past statements and does not invent
   coordinates for a claim that was made before coordinates existed. The same rule governs the
   source assessment added in v3: a claim is marked assessed only when its own snapshot recorded the
   registry the assessment was derived from. A run whose snapshot has no registry record migrates to
   "not assessed" - the missing-source list it happened to carry was a default, and keeping it as an
   assessment would have invented the look it never recorded.
3. **The upgrade ends at the same shape as a fresh database.** The ``claim`` table is rebuilt by
   copying the canonical DDL out of ``schema.sql`` itself, so a migrated store and a new store
   cannot drift apart while both claim to be the current version.

v5 (TESTOPS-45) is additive and needs no rebuild: ``schema.sql`` creates the vocabulary table, seeds
it with ``INSERT OR IGNORE`` and creates the two verdict triggers on every open. A store that already
holds rows under retired names keeps them exactly as they are - a trigger constrains what is written
next, never what was written before - and the upgrade records the new version without touching a
claim.

v6 (TESTOPS-46) changes the *body* of the INSERT trigger: a restore may carry a retired name, so the
trigger asks "has this product ever emitted this name?" rather than "is it current today?". The
``CREATE TRIGGER IF NOT EXISTS`` in ``schema.sql`` cannot express that change - it leaves an existing
v5 trigger body in place - so a v5 store has its two verdict triggers dropped here and recreated by
the ``executescript`` that follows. Rows are not copied or rewritten; only the guard above them is
replaced.

v7 (TESTOPS-72) adds ``repeats_product`` to the vocabulary table and refreshes the two refusal
messages that name the set. Same shape as v6: the triggers are dropped and recreated so the stored
refusal sentence matches what the store accepts. The vocabulary row arrives through the
``INSERT OR IGNORE`` in ``schema.sql``, which runs on every open, so a v6 store gains it without a
copy of any claim.

SQLite cannot add a table-level CHECK to an existing table, and AC4's refusal has to live in the
database - a Python guard in ``add_claim`` would be skippable by the next caller. So the ``claim``
table is rebuilt: same rows, same ids, same values, new columns defaulted to "not recorded", and the
constraints present. The rebuild runs inside one transaction with foreign keys off (dropping a table
others reference is otherwise refused); ``PRAGMA foreign_key_check`` runs before the transaction is
accepted.
"""
from __future__ import annotations

import json
import re
import sqlite3

from ..sources import assessment_for
from ..config import LEGACY_PROJECTS

# The schema this build writes and reads. A store above this is refused.
# v5 adds the verdict vocabulary table and its two claim triggers (TESTOPS-45): they change what may
# be written, not the shape of any stored row, so no existing row is copied or rewritten to get them.
# v6 widens the INSERT trigger's allowed set to every name the product has ever emitted (TESTOPS-46),
# so a store can be restored from its own history; the trigger is replaced, no row is touched.
# v7 adds `repeats_product` to the vocabulary (TESTOPS-72) and refreshes the two refusal messages,
# which name the set; the triggers are replaced again and no row is touched.
CURRENT_VERSION = 7

# The oldest store this build can still open. v1 is readable: its claims are evidence.
MIN_SUPPORTED_VERSION = 1

_VERSION_KEY = "schema_version"
_META_TABLE = "schema_meta"

# v1 claim columns, in v1 order. Only these are copied forward; everything the v2 table adds
# defaults to "not recorded", which is what a v1 claim actually knows.
_V1_CLAIM_COLUMNS = ("id", "run_id", "analyser", "analyser_version", "subject_ref", "statement",
                     "verdict", "confidence", "support")


class SchemaTooNewError(RuntimeError):
    """The store was written by a newer schema than this build understands."""


class SchemaCorruptError(RuntimeError):
    """The store cannot say which schema version it is written against."""


def stored_version(conn: sqlite3.Connection) -> int | None:
    """The version recorded in the store, or None for a store that predates the record."""
    if not _table_exists(conn, _META_TABLE):
        return None
    row = conn.execute(f"SELECT value FROM {_META_TABLE} WHERE key = ?", (_VERSION_KEY,)).fetchone()
    if row is None:
        return None
    try:
        return int(row[0])
    except (TypeError, ValueError) as exc:
        raise SchemaCorruptError(
            f"store records schema_version={row[0]!r}, which is not a version number. "
            "Refusing to guess: a store whose version cannot be read cannot be safely opened."
        ) from exc


def starting_version(conn: sqlite3.Connection) -> int | None:
    """The version an open starts from, for the notice :func:`testops.store.db.connect` prints.

    A store that predates the version record is v1 by construction: ``schema_meta`` arrived with v2,
    so a store that holds a ``claim`` table and no recorded version was written by a v1 build. A file
    with neither is a new store - nothing is being migrated, and saying so would be a small lie.
    """
    version = stored_version(conn)
    if version is None and _table_exists(conn, "claim"):
        return 1
    return version


def prepare(conn: sqlite3.Connection, schema_text: str) -> int:
    """Bring the store up to CURRENT_VERSION, or raise. Returns the version now in force."""
    version = stored_version(conn)
    if version is not None and version > CURRENT_VERSION:
        raise SchemaTooNewError(
            f"store schema_version is {version}; this build understands at most {CURRENT_VERSION}. "
            "Refusing to open it: writing v2 rows into a newer store would corrupt evidence this "
            "build cannot read. Use the newer build."
        )
    if version is not None and version < MIN_SUPPORTED_VERSION:
        raise SchemaTooNewError(
            f"store schema_version is {version}; this build can still read a store at "
            f"version {MIN_SUPPORTED_VERSION} or above, and no downgrade path exists."
        )

    if _table_exists(conn, "claim") and not _has_column(conn, "claim", "assertion_path"):
        _upgrade_claim_to_v2(conn, schema_text)

    if _table_exists(conn, "claim") and not _has_column(conn, "claim", "sources_assessed"):
        _upgrade_claim_sources_to_v3(conn, schema_text)

    if _table_exists(conn, "snapshot") and not _has_column(conn, "snapshot", "schema_version"):
        # ADD COLUMN with a non-NULL default is safe here: every existing snapshot was taken under
        # the v1 claim schema, and 1 is the truth about it, not a stand-in for a missing value.
        conn.execute("ALTER TABLE snapshot ADD COLUMN schema_version INTEGER NOT NULL DEFAULT 1")

    if _table_exists(conn, "snapshot") and not _has_column(conn, "snapshot", "meta"):
        # Additive, and it rewrites no stored statement, so the schema version stays 2. '{}' is the
        # truth about an older snapshot: it recorded nothing about its arms or blind spots, which is
        # different from recording that nothing was missing - a rebuild refuses rather than guess.
        conn.execute("ALTER TABLE snapshot ADD COLUMN meta TEXT NOT NULL DEFAULT '{}'")

    if version is not None and version < 7:
        # schema.sql creates a trigger only if it is absent, so a v6 body - whose refusal message
        # names five verdicts - would survive the executescript below. Drop both and let the
        # canonical DDL install v7's guard and v7's wording.
        conn.execute("DROP TRIGGER IF EXISTS claim_verdict_insert")
        conn.execute("DROP TRIGGER IF EXISTS claim_verdict_update")

    conn.executescript(schema_text)  # creates anything missing; a no-op on a current store
    if version is not None and version < 4:
        _seed_projects(conn)
    _record_version(conn, CURRENT_VERSION)
    return CURRENT_VERSION


def _seed_projects(conn: sqlite3.Connection) -> None:
    """Carry the projects this build knew as Python literals into the store, once.

    TESTOPS-38 AC1. The migration reads :data:`testops.config.LEGACY_PROJECTS`, which existed only
    so that a store written before the model could be brought forward without a second source of
    truth; it is not consulted at run time. A store that already holds a project is not touched:
    a second team's rows are their configuration, and a migration may not overwrite configuration.
    """
    already = conn.execute("SELECT COUNT(*) FROM project").fetchone()[0]
    if already:
        return
    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")

    def add(slug: str, kind: str, role: str, name: str, settings: dict) -> None:
        conn.execute(
            "INSERT INTO service (project, type, role, name, settings, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (slug, kind, role, name, json.dumps(settings, sort_keys=True), now))

    for slug, project in LEGACY_PROJECTS.items():
        conn.execute("INSERT INTO project (slug, name, created_at) VALUES (?,?,?)",
                     (slug, slug, now))
        for role, repo in (("product", project.product), ("test", project.test)):
            if repo is None:
                continue
            add(slug, "git_repo", role, f"{repo.slug} ({role})", {"repo": repo.slug})
        if project.jira_key:
            add(slug, "jira_board", "", f"Jira board {project.jira_key}",
                {"board": project.jira_key})
        if project.ado_org:
            ids = project.ado_pipeline_ids or (None,)
            for pipeline_id in ids:
                settings: dict[str, object] = {"org": project.ado_org,
                                               "project": project.ado_project or ""}
                if pipeline_id is not None:
                    settings["pipeline_id"] = pipeline_id
                name = f"{project.ado_project or project.ado_org} pipeline"
                if pipeline_id is not None:
                    name += f" #{pipeline_id}"
                add(slug, "ado_pipeline", "", name, settings)
    conn.commit()


def _record_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(f"CREATE TABLE IF NOT EXISTS {_META_TABLE} (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute(f"INSERT INTO {_META_TABLE} (key, value) VALUES (?, ?) "
                 f"ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                 (_VERSION_KEY, str(version)))
    conn.commit()


def _upgrade_claim_to_v2(conn: sqlite3.Connection, schema_text: str) -> None:
    columns = ", ".join(_V1_CLAIM_COLUMNS)

    def insert(new_table: str) -> None:
        # Every v1 column copied by name; ids preserved so claims, findings' claim_ids and inference
        # rows all keep pointing at the same claim. The columns this build adds keep their defaults:
        # a v1 claim was made before provenance and before source assessment existed, and "not
        # recorded" is the truth about it - not an assessment invented from its missing list.
        conn.execute(f"INSERT INTO {new_table} ({columns}) SELECT {columns} FROM claim")

    _rebuild_claim_table(conn, schema_text, insert)


def _upgrade_claim_sources_to_v3(conn: sqlite3.Connection, schema_text: str) -> None:
    """Add ``sources_assessed``, and settle every existing claim's source state honestly.

    A v2 store has no record of *whether* the registry was consulted - only, sometimes, of what it
    said. The snapshot's meta is the evidence that decides it: a claim whose snapshot carries the
    registry record and the analyser's needs was assessed, and keeps its stored list; a claim whose
    snapshot carries no registry record is not assessed, whatever list the row happens to hold. That
    list was written without a registry behind it - a default - and promoting it to an assessment is
    exactly the failure this ticket exists to close. Nothing is deleted: the snapshot still holds
    what the run recorded about its sources; only the claim stops claiming it was looked at.
    """
    rows = [dict(row) for row in conn.execute("SELECT * FROM claim ORDER BY id")]
    metas: dict[str, dict | None] = {}
    for row in rows:
        if row["run_id"] not in metas:
            metas[row["run_id"]] = _snapshot_meta(conn, row["run_id"])

    columns = [row[1] for row in conn.execute("PRAGMA table_info(claim)")]
    target = [column for column in columns
              if column not in ("sources_missing", "sources_assessed")]
    target += ["sources_missing", "sources_assessed"]
    values = []
    for row in rows:
        assessed = assessment_for(metas[row["run_id"]], row["analyser"]) is not None
        values.append(tuple([row[column] for column in target[:-2]]
                            + [row["sources_missing"] if assessed else None,
                               1 if assessed and row["sources_missing"] is not None else 0]))

    def insert(new_table: str) -> None:
        conn.executemany(
            f"INSERT INTO {new_table} ({', '.join(target)}) VALUES ({', '.join('?' for _ in target)})",
            values)

    _rebuild_claim_table(conn, schema_text, insert)


def _rebuild_claim_table(conn: sqlite3.Connection, schema_text: str, insert) -> None:
    """Rebuild ``claim`` from ``schema.sql``'s own DDL, filling it through ``insert(new_table)``."""
    new_table = "claim__rebuild"
    ddl = _canonical_claim_ddl(schema_text)
    new_ddl, replaced = re.subn(r"^CREATE TABLE\s+claim\b", f"CREATE TABLE {new_table}", ddl, count=1)
    if not replaced:
        raise RuntimeError(f"schema.sql no longer creates a table named claim: {ddl[:80]!r}")

    conn.commit()
    previous_isolation = conn.isolation_level
    try:
        conn.isolation_level = None  # explicit transaction control for the rebuild
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(f"DROP TABLE IF EXISTS {new_table}")
        conn.execute(new_ddl)
        insert(new_table)
        conn.execute("DROP TABLE claim")
        conn.execute(f"ALTER TABLE {new_table} RENAME TO claim")
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        conn.isolation_level = previous_isolation
        conn.execute("PRAGMA foreign_keys = ON")

    broken = conn.execute("PRAGMA foreign_key_check").fetchall()
    if broken:
        raise RuntimeError(f"migration left dangling references: {broken[:5]}")


def _snapshot_meta(conn: sqlite3.Connection, run_id: str) -> dict | None:
    """The snapshot meta for a claim's run, or ``None`` when there is none to read.

    Unreadable JSON is treated as no record here rather than as an assessment: a migration that
    cannot read what a run could see must not decide that it could see everything.
    """
    row = conn.execute(
        "SELECT s.meta FROM run r JOIN snapshot s ON s.id = r.snapshot_id WHERE r.id = ?",
        (run_id,)).fetchone()
    if row is None or not row[0]:
        return None
    try:
        value = json.loads(row[0])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _canonical_claim_ddl(schema_text: str) -> str:
    """The CREATE TABLE claim statement exactly as schema.sql writes it.

    Read from SQLite's own normalisation rather than duplicated in Python: a second copy of the DDL
    is a second thing to keep in step, and the whole point of this migration is that a migrated
    store ends up shaped like a new one.
    """
    scratch = sqlite3.connect(":memory:")
    try:
        scratch.executescript(schema_text)
        row = scratch.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'claim'").fetchone()
    finally:
        scratch.close()
    if not row or not row[0]:
        raise RuntimeError("schema.sql does not define a claim table")
    return row[0]


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone() is not None


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column for row in conn.execute(f"PRAGMA table_info({table})"))
