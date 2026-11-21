-- TestOps evidence store. Immutable rows, derived everything else.
--
-- schema_version 2: a claim is about one assertion and carries its own provenance. A v1 row keeps
-- schema_version = 1 and NULL provenance for ever - it is the record of what was claimed before the
-- record could express it, and rewriting it would destroy that record. The path from a v1 store
-- lives in testops/store/migrate.py.

CREATE TABLE IF NOT EXISTS schema_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL                      -- deliberately not json: readable with `sqlite3 file.db`
);

CREATE TABLE IF NOT EXISTS snapshot (
  id TEXT PRIMARY KEY,
  project TEXT NOT NULL,
  created_at TEXT NOT NULL,
  artefact_versions TEXT NOT NULL,         -- json: {slug: commit_sha, ...}
  schema_version INTEGER NOT NULL DEFAULT 1  -- claim schema in force when this snapshot was taken
);

CREATE TABLE IF NOT EXISTS artefact (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id TEXT NOT NULL REFERENCES snapshot(id),
  uri TEXT NOT NULL,                       -- github:owner/name@sha:path  |  jira:COTW-12
  kind TEXT NOT NULL,                      -- feature | stepdef | source | test | issue | run
  blob_sha TEXT,
  meta TEXT NOT NULL DEFAULT '{}',
  UNIQUE(snapshot_id, uri)
);

CREATE TABLE IF NOT EXISTS observation (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  artefact_id INTEGER NOT NULL REFERENCES artefact(id),
  extractor TEXT NOT NULL,
  extractor_version TEXT NOT NULL,
  key TEXT NOT NULL,                       -- scenario:Login works | ac_row:3
  value TEXT NOT NULL                      -- json
);

CREATE TABLE IF NOT EXISTS run (
  id TEXT PRIMARY KEY,
  project TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  analyser TEXT NOT NULL,
  status TEXT NOT NULL,                    -- running | ok | failed | partial
  started_at TEXT NOT NULL,
  finished_at TEXT,
  budget TEXT NOT NULL DEFAULT '{}',
  error TEXT
);

-- A v2 claim is about one assertion: which Gherkin step says it, where that step lives, and at
-- which commit. The store refuses a v2 row without those three coordinates, so no caller can write
-- a v2 claim a reader cannot check. Blanks are refused too: '' is not a path.
CREATE TABLE IF NOT EXISTS claim (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL REFERENCES run(id),
  analyser TEXT NOT NULL,
  analyser_version TEXT NOT NULL,
  subject_ref TEXT NOT NULL,               -- scenario:<feature>#<name> | issue:COTW-12
  statement TEXT NOT NULL,                 -- the claim's own heading, in plain words
  verdict TEXT NOT NULL,                   -- optimal | overbuilt | necessary | unplaced | duplicate
  confidence REAL NOT NULL DEFAULT 0.0,
  support TEXT NOT NULL DEFAULT '[]',      -- json: [observation ids]
  schema_version INTEGER NOT NULL DEFAULT 1,
  assertion_text TEXT,                     -- the Gherkin step text, verbatim
  assertion_path TEXT,                     -- repo-relative path of the feature file
  assertion_line INTEGER,                  -- 1-based line of the step
  assertion_commit TEXT,                   -- the commit the coordinates were read at
  interaction_label TEXT,                  -- what a reader sees: "needs a browser"
  interaction_code TEXT,                   -- I1..I4, KP - debugging shorthand, never primary text
  span TEXT,                               -- json: [layers the instrument actually reached]
  established_by TEXT,                     -- the analyser rule that establishes the claim
  sources_missing TEXT,                    -- json: [source names] | NULL = not recorded at all
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
  state TEXT NOT NULL,                     -- open | needs_fix | resolved | false_positive
  actor TEXT NOT NULL,
  at TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS suppression (
  fingerprint TEXT PRIMARY KEY,
  state TEXT NOT NULL,                     -- resolved | false_positive | accepted
  actor TEXT NOT NULL,
  at TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_artefact_snapshot ON artefact(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_obs_artefact ON observation(artefact_id);
CREATE INDEX IF NOT EXISTS idx_claim_run ON claim(run_id);
CREATE INDEX IF NOT EXISTS idx_finding_case ON finding(case_id);

CREATE INDEX IF NOT EXISTS idx_case_state_case ON case_state(case_id);
