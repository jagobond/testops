"""A real v2 store, built the way v2 built it.

The DDL below is schema.sql as it stood before TESTOPS-17 (commit c880a7d), copied verbatim rather
than generated from today's schema: the point of a migration test is to open a store this build did
not create. If this fixture were derived from the current schema it would prove nothing.

The store has two runs over two snapshots, and the difference between them is the whole ticket:

  * ``snap-registry`` records the source registry and the analyser's needs, so its claim's missing
    list was derived from something and the migration may keep it as an assessment;
  * ``snap-no-registry`` records only ``sources_missing`` and ``arms``, so its claim's list was
    written without a registry behind it. The migration must not promote it into an assessment.

Both claims carry the same stored list - ``["jira", "ado"]`` - so a migration that decides the state
by looking at the list rather than at the snapshot cannot tell them apart.
"""
from __future__ import annotations

import json
import sqlite3

V2_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshot (
  id TEXT PRIMARY KEY,
  project TEXT NOT NULL,
  created_at TEXT NOT NULL,
  artefact_versions TEXT NOT NULL,
  schema_version INTEGER NOT NULL DEFAULT 1,
  meta TEXT NOT NULL DEFAULT '{}'
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
  support TEXT NOT NULL DEFAULT '[]',
  schema_version INTEGER NOT NULL DEFAULT 1,
  assertion_text TEXT,
  assertion_path TEXT,
  assertion_line INTEGER,
  assertion_commit TEXT,
  interaction_label TEXT,
  interaction_code TEXT,
  span TEXT,
  established_by TEXT,
  sources_missing TEXT,
  proposed_action TEXT,
  CONSTRAINT claim_v2_requires_provenance CHECK (
    schema_version = 1
    OR (
      schema_version = 2
      AND assertion_path IS NOT NULL AND length(trim(assertion_path)) > 0
      AND assertion_line IS NOT NULL
      AND assertion_commit IS NOT NULL AND length(trim(assertion_commit)) > 0
    )
  )
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
COMMIT = "a" * 40
PATH = "features/panel_api.feature"
STATEMENT = ("This test asserts that the panel is served. Only a browser works that out, and this "
             "test only reads the responses the server sends instead, so nothing checks it.")
MISSING = '["jira", "ado"]'
REGISTRY_CLAIM = 1        # the claim of snap-registry: assessed by the v2 run, through the registry
NO_REGISTRY_CLAIM = 2     # the claim of snap-no-registry: a list with no gateway behind it

# The registry record and the analyser's needs, exactly as the v2 pipeline wrote them.
REGISTRY_META = {
    "sources_missing": ["jira", "ado"],
    "arms": {"test": "o/tests", "product": "o/product"},
    "sources": {
        "github": {"id": "github", "title": "GitHub", "capabilities": ["code", "test_code"],
                   "state": "available", "reason": "", "blocked_by": "", "observed": 12,
                   "route": "github-api", "note": "", "order": 0},
        "jira": {"id": "jira", "title": "Jira", "capabilities": ["requirements"],
                 "state": "blocked", "reason": "no credentials", "blocked_by": "Quilter policy",
                 "observed": None, "route": "", "note": "", "order": 1},
        "ado": {"id": "ado", "title": "Azure DevOps", "capabilities": ["test_execution",
                                                                      "requirements"],
                "state": "blocked", "reason": "no credentials", "blocked_by": "Quilter policy",
                "observed": None, "route": "", "note": "", "order": 2},
    },
    "analysers": {"level_fitness": {"needs": ["code", "test_code"],
                                    "consults": ["requirements", "test_execution"]}},
}

# The same run, before the registry existed: it recorded what it could not consult and nothing about
# how it knew. This is the meta a migration must read as "not assessed".
NO_REGISTRY_META = {
    "sources_missing": ["jira", "ado"],
    "arms": {"test": "o/tests", "product": "o/product"},
}


def build(path) -> None:
    """Write a v2 store with one registry-recorded run and one run without registry meta."""
    conn = sqlite3.connect(path)
    try:
        conn.executescript(V2_SCHEMA)
        conn.execute("INSERT INTO schema_meta (key, value) VALUES ('schema_version', '2')")
        for name, meta in (("snap-registry", REGISTRY_META), ("snap-no-registry", NO_REGISTRY_META)):
            conn.execute(
                "INSERT INTO snapshot (id, project, created_at, artefact_versions, schema_version, meta)"
                " VALUES (?,?,?,?,?,?)",
                (name, PROJECT, TS, '{"o/tests": "' + COMMIT + '", "o/product": "' + COMMIT + '"}',
                 2, sqlite3_json(meta)))
            run = f"run-{name}"
            conn.execute("INSERT INTO run (id, project, snapshot_id, analyser, status, started_at)"
                         " VALUES (?,?,?,?,?,?)", (run, PROJECT, name, "level_fitness", "ok", TS))
            conn.execute(
                "INSERT INTO claim (run_id, analyser, analyser_version, subject_ref, statement,"
                " verdict, confidence, support, schema_version, assertion_text, assertion_path,"
                " assertion_line, assertion_commit, interaction_label, interaction_code, span,"
                " established_by, sources_missing, proposed_action)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run, "level_fitness", "0.8.0", f"scenario:{PATH}#the panel is served", STATEMENT,
                 "gap", 0.5, "[]", 2, "the panel is served", PATH, 17, COMMIT,
                 "needs a browser", "I4", '["api"]', "asserts an accessibility property",
                 MISSING, "Move the step into a test that drives a browser."))
        conn.commit()
    finally:
        conn.close()


def sqlite3_json(meta) -> str:
    return json.dumps(meta, sort_keys=True)
