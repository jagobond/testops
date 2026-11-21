"""SQLite access. One file, explicit transactions, no ORM."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..config import DB_PATH

SCHEMA = Path(__file__).with_name("schema.sql")


def connect(path: Path | None = None) -> sqlite3.Connection:
    p = path or DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return conn


def j(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def uj(s, default=None):
    try:
        return json.loads(s) if s else default
    except json.JSONDecodeError:
        return default


def upsert_snapshot(conn, snapshot_id: str, project: str, created_at: str, versions: dict) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO snapshot (id, project, created_at, artefact_versions) VALUES (?,?,?,?)",
        (snapshot_id, project, created_at, j(versions)),
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
              statement: str, verdict: str, confidence: float, support: list[int]) -> int:
    cur = conn.execute(
        "INSERT INTO claim (run_id, analyser, analyser_version, subject_ref, statement, verdict, confidence, support)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (run_id, analyser, version, subject_ref, statement, verdict, float(confidence), j(support)),
    )
    return cur.lastrowid


def add_inference(conn, claim_id: int, model: str, model_version: str, prompt_hash: str,
                  input_refs: list, output: dict, tokens_in: int = 0, tokens_out: int = 0) -> None:
    conn.execute(
        "INSERT INTO inference (claim_id, model, model_version, prompt_hash, input_refs, output, tokens_in, tokens_out)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (claim_id, model, model_version, prompt_hash, j(input_refs), j(output), int(tokens_in), int(tokens_out)),
    )
