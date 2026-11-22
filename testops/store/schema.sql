-- TestOps evidence store. Immutable rows, derived everything else.
--
-- schema_version 2: a claim is about one assertion and carries its own provenance. A v1 row keeps
-- schema_version = 1 and NULL provenance for ever - it is the record of what was claimed before the
-- record could express it, and rewriting it would destroy that record. The path from a v1 store
-- lives in testops/store/migrate.py.
--
-- schema_version 3: whether a claim's sources were assessed at all is stored, distinctly from which
-- were missing. The default is "not assessed", so a claim written without an assessment record
-- cannot read as a clean bill; the pairing of the two columns is a CHECK, not a convention. The row
-- schema_version stays 1 or 2: it says what the row knows about the assertion, and this column says
-- what it knows about the sources. Both are additive; neither rewrites a past statement.
--
-- schema_version 5: the verdict column is guarded at the store, not only described. Two triggers
-- (BEFORE INSERT and BEFORE UPDATE OF verdict) refuse a value outside the current vocabulary, so
-- an analyser, a fixture, the CLI or a future connector meets the same refusal. A trigger rather
-- than a CHECK: 128 stored rows carry retired names (optimal 36, overbuilt 67, necessary 25), and a
-- retroactive CHECK would either reject them or require rewriting evidence to satisfy it. The
-- triggers read the vocabulary table below, so the allowed set has one definition; retired names
-- are recorded there with the ticket that retired them (TESTOPS-9), kept readable and never
-- writable again.

CREATE TABLE IF NOT EXISTS schema_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL                      -- deliberately not json: readable with `sqlite3 file.db`
);

CREATE TABLE IF NOT EXISTS snapshot (
  id TEXT PRIMARY KEY,
  project TEXT NOT NULL,
  created_at TEXT NOT NULL,
  artefact_versions TEXT NOT NULL,         -- json: {slug: commit_sha, ...}
  schema_version INTEGER NOT NULL DEFAULT 1, -- claim schema in force when this snapshot was taken
  meta TEXT NOT NULL DEFAULT '{}'          -- json: which arm is which, and what the run could not consult
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

-- TESTOPS-45. The verdict vocabulary is data, not prose: the claim triggers read this table, and
-- `testops check-store` reads it to tell a historical name from an unknown one. A current row is a
-- value an analyser may write today. A retired row is a value that stored evidence still carries;
-- it is historical fact and cannot be written again, which is why the triggers never consult it.
CREATE TABLE IF NOT EXISTS verdict_vocabulary (
  name TEXT PRIMARY KEY,
  status TEXT NOT NULL CHECK (status IN ('current', 'retired')),
  retired_by TEXT,                         -- the ticket that retired the name; NULL while current
  CONSTRAINT verdict_retired_names_have_a_ticket CHECK (
    (status = 'current' AND retired_by IS NULL)
    OR (status = 'retired' AND retired_by IS NOT NULL AND length(trim(retired_by)) > 0)
  )
);

INSERT OR IGNORE INTO verdict_vocabulary (name, status, retired_by) VALUES
  ('distinct',  'current', NULL),
  ('gap',       'current', NULL),
  ('review',    'current', NULL),
  ('unplaced',  'current', NULL),
  ('duplicate', 'current', NULL),
  ('optimal',   'retired', 'TESTOPS-9'),
  ('overbuilt', 'retired', 'TESTOPS-9'),
  ('necessary', 'retired', 'TESTOPS-9');

-- A v2 claim is about one assertion: which Gherkin step says it, where that step lives, and at
-- which commit. The store refuses a v2 row without those three coordinates, so no caller can write
-- a v2 claim a reader cannot check. Blanks are refused too: '' is not a path.
--
-- The verdict vocabulary is the analysers' own: the column comment below follows the code, and
-- tests/test_verdict_vocabulary.py fails if the two disagree. Rows written before the vocabulary
-- settled may carry retired names; they are read, never rewritten (see LEGACY_JUDGEMENT in
-- testops/web/app.py).
CREATE TABLE IF NOT EXISTS claim (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL REFERENCES run(id),
  analyser TEXT NOT NULL,
  analyser_version TEXT NOT NULL,
  subject_ref TEXT NOT NULL,               -- scenario:<feature>#<name> | issue:COTW-12
  statement TEXT NOT NULL,                 -- the claim's own heading, in plain words
  verdict TEXT NOT NULL,                   -- distinct | gap | review | unplaced | duplicate
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
  sources_missing TEXT,                    -- json: [source names] | NULL = not assessed, or not recorded
  sources_assessed INTEGER NOT NULL DEFAULT 0, -- 1 = a registry was consulted for this claim
  proposed_action TEXT,
  CONSTRAINT claim_v2_requires_provenance CHECK (
    schema_version = 1
    OR (
      schema_version = 2
      AND assertion_path IS NOT NULL AND length(trim(assertion_path)) > 0
      AND assertion_line IS NOT NULL
      AND assertion_commit IS NOT NULL AND length(trim(assertion_commit)) > 0
    )
  ),
  -- "Not assessed" is a state, not an empty list. A missing-source list is only readable as a fact
  -- when the run recorded that it looked; without that record the list is a default, and a default
  -- must not render as a guarantee. The database enforces the pairing, so no writer can store
  -- "assessed" with nothing to show or an unassessed claim with a list that reads like an answer.
  CONSTRAINT claim_sources_assessed_pairing CHECK (
    sources_assessed IN (0, 1)
    AND (
      (sources_assessed = 0 AND sources_missing IS NULL)
      OR (sources_assessed = 1 AND sources_missing IS NOT NULL)
    )
  )
);

-- TESTOPS-45. The store's verdict guard. A trigger, not a CHECK, because the 128 historical rows
-- under retired names must stay readable and unrewritten (AC3); a CHECK would have to reject them.
-- Two triggers, because INSERT and UPDATE are different events: a row's other columns may change
-- freely, but its verdict may not become a name no analyser emits. Both read the vocabulary table,
-- so the allowed set has one definition. RAISE() takes a literal message only, so the message names
-- the allowed set while the offending value is named by `verdicts.validate_verdict` for callers,
-- by this refusal's row context, and by `testops check-store` for a legacy store.
CREATE TRIGGER IF NOT EXISTS claim_verdict_insert
BEFORE INSERT ON claim
WHEN NEW.verdict NOT IN (SELECT name FROM verdict_vocabulary WHERE status = 'current')
BEGIN
  SELECT RAISE(ABORT,
    'claim.verdict is not one of distinct|gap|review|unplaced|duplicate: the store refuses an unknown verdict');
END;

CREATE TRIGGER IF NOT EXISTS claim_verdict_update
BEFORE UPDATE OF verdict ON claim
WHEN NEW.verdict NOT IN (SELECT name FROM verdict_vocabulary WHERE status = 'current')
BEGIN
  SELECT RAISE(ABORT,
    'claim.verdict is not one of distinct|gap|review|unplaced|duplicate: the store refuses an unknown verdict');
END;

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

-- TESTOPS-38. A project is an identity and owns no data; a service is one analysable resource
-- inside it. Runs and cases keep their ``project`` column and it holds this slug, so every existing
-- row and every existing page keeps its meaning without a rewrite.
CREATE TABLE IF NOT EXISTS project (
  slug TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT ''
);

-- The service's own last-consulted state and reason (AC4): what it said about itself the last time
-- a run resolved the project, never a guess made at render time. ``settings`` holds hosts, repo
-- coordinates, board keys and paths - never a credential; secrets resolve from the environment.
CREATE TABLE IF NOT EXISTS service (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project TEXT NOT NULL REFERENCES project(slug) ON DELETE CASCADE,
  type TEXT NOT NULL CHECK (type IN ('git_repo', 'jira_board', 'ado_pipeline')),
  role TEXT NOT NULL DEFAULT '' CHECK (role IN ('', 'product', 'test')),
  name TEXT NOT NULL CHECK (length(trim(name)) > 0),
  settings TEXT NOT NULL DEFAULT '{}',
  last_state TEXT,
  last_reason TEXT,
  last_consulted_at TEXT,
  created_at TEXT NOT NULL DEFAULT '',
  CONSTRAINT service_role_for_git_repo CHECK (
    type != 'git_repo' OR role IN ('product', 'test')
  )
);

CREATE INDEX IF NOT EXISTS idx_service_project ON service(project);
