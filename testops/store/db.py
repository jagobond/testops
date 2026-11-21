"""SQLite access. One file, explicit transactions, no ORM."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..config import DB_PATH
from . import migrate
from .migrate import SchemaCorruptError, SchemaTooNewError  # re-exported: callers catch db.SchemaTooNewError

SCHEMA = Path(__file__).with_name("schema.sql")


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Open the store, upgrading it forward if it is older, refusing it if it is newer.

    ``schema.sql`` alone cannot do this: ``CREATE TABLE IF NOT EXISTS`` leaves an old ``claim`` table
    exactly as it found it, so a v1 database would keep opening while claiming to be current. The
    version check and the migration live in ``store/migrate.py`` and run before anything is read.
    """
    p = path or DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate.prepare(conn, SCHEMA.read_text(encoding="utf-8"))
    return conn


def j(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def jn(obj):
    """JSON for a value that may legitimately be absent.

    NULL and ``[]`` are different facts - "nothing was recorded" and "nothing was missing" - so the
    absent case must not be spelled ``[]`` and ``[]`` must not be folded to NULL.
    """
    return None if obj is None else j(obj)


def uj(s, default=None):
    try:
        return json.loads(s) if s else default
    except json.JSONDecodeError:
        return default


def upsert_snapshot(conn, snapshot_id: str, project: str, created_at: str, versions: dict,
                    schema_version: int = 1, meta: dict | None = None) -> None:
    """Write a snapshot row.

    ``meta`` records what a rebuild needs and the artefacts cannot say: which repository is the test
    arm and which the product arm, and the sources the run knew it could not consult. ``None`` is
    stored as ``{}`` - "nothing was recorded" - never as a clean bill of health.
    """
    conn.execute(
        "INSERT OR REPLACE INTO snapshot (id, project, created_at, artefact_versions, schema_version, meta)"
        " VALUES (?,?,?,?,?,?)",
        (snapshot_id, project, created_at, j(versions), int(schema_version), j(meta or {})),
    )


def add_artefact(conn, snapshot_id: str, uri: str, kind: str, blob_sha: str | None, meta: dict | None = None) -> int:
    cur = conn.execute(
        "INSERT OR IGNORE INTO artefact (snapshot_id, uri, kind, blob_sha, meta) VALUES (?,?,?,?,?)",
        (snapshot_id, uri, kind, blob_sha, j(meta or {})),
    )
    if cur.lastrowid:
        return cur.lastrowid
    row = conn.execute("SELECT id FROM artefact WHERE snapshot_id=? AND uri=?", (snapshot_id, uri)).fetchone()
    return row["id"]


def add_observation(conn, artefact_id: int, extractor: str, version: str, key: str, value: dict) -> int:
    cur = conn.execute(
        "INSERT INTO observation (artefact_id, extractor, extractor_version, key, value) VALUES (?,?,?,?,?)",
        (artefact_id, extractor, version, key, j(value)),
    )
    return cur.lastrowid


def start_run(conn, run_id: str, project: str, snapshot_id: str, analyser: str, started_at: str) -> None:
    conn.execute(
        "INSERT INTO run (id, project, snapshot_id, analyser, status, started_at) VALUES (?,?,?,?,?,?)",
        (run_id, project, snapshot_id, analyser, "running", started_at),
    )


def finish_run(conn, run_id: str, status: str, finished_at: str, error: str | None = None, budget: dict | None = None) -> None:
    conn.execute(
        "UPDATE run SET status=?, finished_at=?, error=?, budget=? WHERE id=?",
        (status, finished_at, error, j(budget or {}), run_id),
    )


def add_claim(conn, run_id: str, analyser: str, version: str, subject_ref: str,
              statement: str, verdict: str, confidence: float, support: list[int],
              *, schema_version: int = 1,
              assertion_text: str | None = None, assertion_path: str | None = None,
              assertion_line: int | None = None, assertion_commit: str | None = None,
              interaction_label: str | None = None, interaction_code: str | None = None,
              span: list | None = None, established_by: str | None = None,
              sources_missing: list | None = None, proposed_action: str | None = None) -> int:
    """Write one claim.

    ``schema_version`` defaults to 1, which is what the analysers written before TESTOPS-4 are: they
    assert per scenario and know no coordinates. A v2 call must pass the three assertion coordinates;
    if it does not, the *database* raises ``sqlite3.IntegrityError`` on the CHECK constraint. There is
    deliberately no Python check here - a guard in this function is a guard the next caller skips.

    ``sources_missing``: ``[]`` means everything was consulted; ``None`` means nothing was recorded.
    The two are stored and read back differently on purpose.
    """
    cur = conn.execute(
        "INSERT INTO claim (run_id, analyser, analyser_version, subject_ref, statement, verdict,"
        " confidence, support, schema_version, assertion_text, assertion_path, assertion_line,"
        " assertion_commit, interaction_label, interaction_code, span, established_by,"
        " sources_missing, proposed_action)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (run_id, analyser, version, subject_ref, statement, verdict, float(confidence), j(support),
         int(schema_version), assertion_text, assertion_path, assertion_line, assertion_commit,
         interaction_label, interaction_code, jn(span), established_by, jn(sources_missing),
         proposed_action),
    )
    return cur.lastrowid


def add_inference(conn, claim_id: int, model: str, model_version: str, prompt_hash: str,
                  input_refs: list, output: dict, tokens_in: int = 0, tokens_out: int = 0) -> None:
    conn.execute(
        "INSERT INTO inference (claim_id, model, model_version, prompt_hash, input_refs, output, tokens_in, tokens_out)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (claim_id, model, model_version, prompt_hash, j(input_refs), j(output), int(tokens_in), int(tokens_out)),
    )
