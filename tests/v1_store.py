"""A real v1 store, built the way v1 built it.

The DDL below is schema.sql as it stood before TESTOPS-3 (commit 95d60bc), copied verbatim rather
than generated from today's schema: the point of the migration tests is to open a store this build
did not create. If this fixture were derived from the current schema it would prove nothing about
backwards compatibility.

Rows are inserted exactly as the v1 code inserted them - no schema_version column existed, and a
claim's only coordinates were its subject_ref.
"""
from __future__ import annotations

import sqlite3

V1_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshot (
  id TEXT PRIMARY KEY,
  project TEXT NOT NULL,
  created_at TEXT NOT NULL,
  artefact_versions TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artefact (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id TEXT NOT NULL REFERENCES snapshot(id),
  uri TEXT NOT NULL,
  kind TEXT NOT NULL,
  blob_sha TEXT,
  meta TEXT NOT NULL DEFAULT '{}',
  UNIQUE(snapshot_id, uri)
);

CREATE TABLE IF NOT EXISTS observation (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  artefact_id INTEGER NOT NULL REFERENCES artefact(id),
  extractor TEXT NOT NULL,
  extractor_version TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS run (
  id TEXT PRIMARY KEY,
  project TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  analyser TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  budget TEXT NOT NULL DEFAULT '{}',
  error TEXT
);

CREATE TABLE IF NOT EXISTS claim (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL REFERENCES run(id),
  analyser TEXT NOT NULL,
  analyser_version TEXT NOT NULL,
  subject_ref TEXT NOT NULL,
  statement TEXT NOT NULL,
  verdict TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 0.0,
  support TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS inference (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  claim_id INTEGER NOT NULL REFERENCES claim(id),
  model TEXT NOT NULL,
  model_version TEXT NOT NULL,
  prompt_hash TEXT NOT NULL,
  input_refs TEXT NOT NULL DEFAULT '[]',
  output TEXT NOT NULL,
  tokens_in INTEGER NOT NULL DEFAULT 0,
  tokens_out INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS case_ (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES run(id),
  project TEXT NOT NULL,
  analyser TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS finding (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id TEXT NOT NULL REFERENCES case_(id),
  title TEXT NOT NULL,
  severity TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  claim_ids TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS case_state (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id TEXT NOT NULL REFERENCES case_(id),
  state TEXT NOT NULL,
  actor TEXT NOT NULL,
  at TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS suppression (
  fingerprint TEXT PRIMARY KEY,
  state TEXT NOT NULL,
  actor TEXT NOT NULL,
  at TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_artefact_snapshot ON artefact(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_obs_artefact ON observation(artefact_id);
CREATE INDEX IF NOT EXISTS idx_claim_run ON claim(run_id);
CREATE INDEX IF NOT EXISTS idx_finding_case ON finding(case_id);
CREATE INDEX IF NOT EXISTS idx_case_state_case ON case_state(case_id);
"""

TS = "2020-01-01T00:00:00+00:00"
PROJECT = "fixture"
SNAPSHOT = "snap-v1"
RUN = "run-v1"
CASE = "case-run-v1"
CLAIM_ID = 1
SUBJECT = "scenario:features/panel_api.feature#the panel is served"
STATEMENT = "KP claim established at the api boundary - asserts the page-as-served"
VERDICT = "gap"
CONFIDENCE = 0.42


def build(path) -> None:
    """Write a v1 store with one claim, its inference, and the finding that cites it."""
    conn = sqlite3.connect(path)
    try:
        conn.executescript(V1_SCHEMA)
        conn.execute("INSERT INTO snapshot (id, project, created_at, artefact_versions) VALUES (?,?,?,?)",
                     (SNAPSHOT, PROJECT, TS, '{"fixture/test": "' + "0" * 40 + '"}'))
        conn.execute("INSERT INTO run (id, project, snapshot_id, analyser, status, started_at)"
                     " VALUES (?,?,?,?,?,?)", (RUN, PROJECT, SNAPSHOT, "level_fitness", "ok", TS))
        conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at, summary)"
                     " VALUES (?,?,?,?,?,?,?)", (CASE, RUN, PROJECT, "level_fitness", SNAPSHOT, TS, "{}"))
        conn.execute("INSERT INTO claim (id, run_id, analyser, analyser_version, subject_ref, statement,"
                     " verdict, confidence, support) VALUES (?,?,?,?,?,?,?,?,?)",
                     (CLAIM_ID, RUN, "level_fitness", "0.5.0", SUBJECT, STATEMENT, VERDICT,
                      CONFIDENCE, "[]"))
        conn.execute("INSERT INTO inference (claim_id, model, model_version, prompt_hash, output)"
                     " VALUES (?,?,?,?,?)", (CLAIM_ID, "none", "none", "", '{"claim": "KP"}'))
        conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                     " VALUES (?,?,?,?,?)", (CASE, STATEMENT[:160], "high", "f" * 32, "[1]"))
        conn.commit()
    finally:
        conn.close()
