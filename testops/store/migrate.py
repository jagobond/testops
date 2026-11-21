"""Forward-only migration of the evidence store.

Three rules, in order of importance:

1. **Forward only.** A store written by a newer build than this one is refused, loudly, before any
   other statement runs. Reading it and then writing rows this build cannot express would corrupt
   evidence that a later (correct) build has to be able to trust. There is no downward path here and
   no ``--force``: the answer to "too new" is to use the newer build.
2. **v1 rows are never rewritten.** They keep ``schema_version = 1`` and NULL provenance. The store
   upgrades its *structure*; it does not upgrade anyone's past statements and does not invent
   coordinates for a claim that was made before coordinates existed.
3. **The upgrade ends at the same shape as a fresh database.** The v2 ``claim`` table is rebuilt by
   copying the canonical DDL out of ``schema.sql`` itself, so a migrated store and a new store
   cannot drift apart while both claim to be version 2.

SQLite cannot add a table-level CHECK to an existing table, and AC4's refusal has to live in the
database - a Python guard in ``add_claim`` would be skippable by the next caller. So the v1 ``claim``
table is rebuilt: same rows, same ids, same values, new columns defaulted to "not recorded", and the
constraint present. The rebuild runs inside one transaction with foreign keys off (dropping a table
others reference is otherwise refused); ``PRAGMA foreign_key_check`` runs before the transaction is
accepted.
"""
from __future__ import annotations

import re
import sqlite3

# The schema this build writes and reads. A store above this is refused.
CURRENT_VERSION = 2

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

    if _table_exists(conn, "snapshot") and not _has_column(conn, "snapshot", "schema_version"):
        # ADD COLUMN with a non-NULL default is safe here: every existing snapshot was taken under
        # the v1 claim schema, and 1 is the truth about it, not a stand-in for a missing value.
        conn.execute("ALTER TABLE snapshot ADD COLUMN schema_version INTEGER NOT NULL DEFAULT 1")

    conn.executescript(schema_text)  # creates anything missing; a no-op on a current store
    _record_version(conn, CURRENT_VERSION)
    return CURRENT_VERSION


def _record_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(f"CREATE TABLE IF NOT EXISTS {_META_TABLE} (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute(f"INSERT INTO {_META_TABLE} (key, value) VALUES (?, ?) "
                 f"ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                 (_VERSION_KEY, str(version)))
    conn.commit()


def _upgrade_claim_to_v2(conn: sqlite3.Connection, schema_text: str) -> None:
    new_table = "claim__v2"
    ddl = _canonical_claim_ddl(schema_text)
    new_ddl, replaced = re.subn(r"^CREATE TABLE\s+claim\b", f"CREATE TABLE {new_table}", ddl, count=1)
    if not replaced:
        raise RuntimeError(f"schema.sql no longer creates a table named claim: {ddl[:80]!r}")

    columns = ", ".join(_V1_CLAIM_COLUMNS)
    conn.commit()
    previous_isolation = conn.isolation_level
    try:
        conn.isolation_level = None  # explicit transaction control for the rebuild
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(f"DROP TABLE IF EXISTS {new_table}")
        conn.execute(new_ddl)
        # Every v1 column copied by name; ids preserved so claims, findings' claim_ids and inference
        # rows all keep pointing at the same claim.
        conn.execute(f"INSERT INTO {new_table} ({columns}) SELECT {columns} FROM claim")
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
