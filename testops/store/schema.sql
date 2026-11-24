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
-- rewritten.
--
-- schema_version 6 (TESTOPS-46): the guard answers two different questions, at two levels, and
-- they must not be collapsed again.
--
--   * At the DATABASE, on INSERT, a verdict must be a name this product has EVER emitted - current
--     or retired. That is what a restore is: `INSERT INTO claim SELECT ...` carrying `optimal` out
--     of an older store is the store keeping its own past, not a new claim being invented. The
--     v5 trigger asked for a name current today and therefore refused exactly the historical rows
--     a restore exists to preserve; a store could no longer be rebuilt from its own history.
--   * In the CODE, an analyser may emit only a name that is current today. `db.add_claim` calls
--     `store/verdicts.validate_verdict` against the current set, so no live run can write a
--     retired name even though the database would accept it from a restore. A code guard is
--     skippable by the next connector, which is why the database guard exists too - but they are
--     not the same rule and do not belong in the same query.
--
-- `claim_verdict_update` deliberately stays current-only. Changing an existing row's verdict to a
-- retired name is a rewrite of evidence, not a restore; the 128 historical rows are read, never
-- rewritten. Restore is INSERT, so widening INSERT is enough and leaves UPDATE's original
-- protection intact.
--
-- schema_version 7 (TESTOPS-72) adds one name to the vocabulary, `repeats_product`, and the two
-- trigger messages that name the set in a refusal. The INSERT trigger reads the table, so its
-- *behaviour* did not change - but a refusal sentence naming five verdicts while the store accepts
-- six is a small lie, and `CREATE TRIGGER IF NOT EXISTS` cannot replace a body. A v6 store has both
-- triggers dropped and recreated on open, exactly as v6 did for v5; no row is copied or rewritten.

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
  ('repeats_product', 'current', NULL),
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
  verdict TEXT NOT NULL,                   -- distinct | gap | review | unplaced | duplicate | repeats_product
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

-- TESTOPS-45, widened by TESTOPS-46. The store's verdict guard. A trigger, not a CHECK, because
-- the 128 historical rows under retired names must stay readable and unrewritten (AC3); a CHECK
-- would have to reject them.
--
-- The INSERT trigger asks "has this product ever emitted this name?", so restore from an older
-- store's history is accepted; it reads the whole vocabulary table, current and retired. The code
-- path is stricter: db.add_claim refuses a retired name through verdicts.validate_verdict, and
-- nothing but a restore or a migration writes by SQL. The UPDATE trigger keeps asking the v5
-- question, because rewriting a stored verdict to a retired name is not a restore.
-- RAISE() takes a literal message only, so the messages name both sets while the offending value
-- is named by `verdicts.validate_verdict` for callers and by `testops check-store` for a store.
CREATE TRIGGER IF NOT EXISTS claim_verdict_insert
BEFORE INSERT ON claim
WHEN NEW.verdict NOT IN (SELECT name FROM verdict_vocabulary)
BEGIN
  SELECT RAISE(ABORT,
    'claim.verdict is not a verdict this product has ever emitted: current are distinct|gap|review|unplaced|duplicate|repeats_product; retired are necessary|optimal|overbuilt, accepted only from a restore');
END;

CREATE TRIGGER IF NOT EXISTS claim_verdict_update
BEFORE UPDATE OF verdict ON claim
WHEN NEW.verdict NOT IN (SELECT name FROM verdict_vocabulary WHERE status = 'current')
BEGIN
  SELECT RAISE(ABORT,
    'claim.verdict is not one of distinct|gap|review|unplaced|duplicate|repeats_product: a stored verdict may not be rewritten to an unknown or retired name');
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

-- TESTOPS-88. The agent ledger: what the explanation was asked to do, what it cost, and what a
-- reader said about it. Additive, like every table above: a store written before this ticket gains
-- these tables on open and loses nothing. No schema version bump, because no stored row is copied
-- or rewritten and an older build reading this store ignores tables it does not know.
--
-- The verdict is evidence; the explanation is commentary. These tables hold only commentary, and
-- ``agent_view.variant`` records which page a reader was shown so the two can be weighed against
-- each other instead of assumed.
-- TESTOPS-93. ``variant`` gains ``foundry``: the third page is an explanation written by the hosted
-- Foundry agent rather than by this build's own model call. It is a variant and not a sub-flag of
-- ``on`` because the two explanations come from different routes, and the report must be able to put
-- a view of one beside a view of the other.
CREATE TABLE IF NOT EXISTS agent_view (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id TEXT NOT NULL,
  variant TEXT NOT NULL CHECK (variant IN ('on', 'off', 'foundry')),
  at TEXT NOT NULL,
  -- What the page actually carried: ``fresh`` (an explanation written for this view), ``cached``
  -- (one served from the store), ``rejected`` (a reply that failed the check),
  -- ``failed_unavailable``, ``failed_unconfigured``, ``no_finding``, ``off`` or ``pending``
  -- (a render that never closed). Every other value is a failure mode, named, so a blank block can
  -- never be counted as a served one, and the report breaks its figures down by this column.
  served TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '',         -- the cause, or the model name; never a credential
  call_id INTEGER                           -- the agent_call this view used, when it made one
);

CREATE TABLE IF NOT EXISTS agent_call (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id TEXT NOT NULL,
  variant TEXT NOT NULL,
  -- TESTOPS-93: which route answered - this build's own model call (``model``) or the hosted Foundry
  -- agent (``foundry``). A row written before this column existed was a model call, and the migration
  -- says so rather than leaving the route unknown.
  route TEXT NOT NULL DEFAULT 'model' CHECK (route IN ('model', 'foundry')),
  model TEXT NOT NULL,
  prompt_hash TEXT NOT NULL,
  tokens_in INTEGER NOT NULL DEFAULT 0,
  tokens_out INTEGER NOT NULL DEFAULT 0,
  cached INTEGER NOT NULL DEFAULT 0,        -- 1: served from the store, so it cost nothing
  wall_ms INTEGER NOT NULL DEFAULT 0,
  outcome TEXT NOT NULL,                    -- ok | cached | rejected | error
  cause TEXT NOT NULL DEFAULT ''            -- unreachable | http_429 | empty | ... | not_configured
);

-- The explanation cache: (case, prompt hash, model) identifies one answer. The prompt hash covers
-- the prompt text and the model, so a changed record or a changed prompt is a new key rather than a
-- stale hit.
CREATE TABLE IF NOT EXISTS agent_explanation (
  case_id TEXT NOT NULL,
  prompt_hash TEXT NOT NULL,
  model TEXT NOT NULL,
  text TEXT NOT NULL,
  created_at TEXT NOT NULL,
  tokens_in INTEGER NOT NULL DEFAULT 0,
  tokens_out INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (case_id, prompt_hash, model)
);

-- Feedback without JavaScript, cookies or identity. A vote is tied to the view a reader was
-- looking at, so clicking both links on one page counts once; nothing about the reader is stored.
CREATE TABLE IF NOT EXISTS agent_feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id TEXT NOT NULL,
  variant TEXT NOT NULL,
  verdict TEXT NOT NULL CHECK (verdict IN ('helped', 'did_not_help')),
  at TEXT NOT NULL,
  view_id INTEGER NOT NULL,
  UNIQUE (view_id, case_id, variant)
);

CREATE INDEX IF NOT EXISTS idx_agent_view_case ON agent_view(case_id);
CREATE INDEX IF NOT EXISTS idx_agent_call_case ON agent_call(case_id);
CREATE INDEX IF NOT EXISTS idx_agent_feedback_case ON agent_feedback(case_id);

-- TESTOPS-92. What each case page's ``?agent=`` flag actually said. A reader who types
-- ``?agent=true`` and gets the agent-off page must be able to see, in the meter, that the value was
-- recorded and what it meant - and a demo-day typo must be visible as a typo rather than inferred
-- from a variant column that stays empty. ``flag_value`` is the value as typed, trimmed; '' is a
-- page that carried no value (no parameter, or an empty one). ``understood`` is 1 when the value is
-- one of the eight accepted spellings, so an unrecognised one is counted as itself, not as "off".
CREATE TABLE IF NOT EXISTS agent_flag (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT NOT NULL,
  case_id TEXT NOT NULL,
  flag_value TEXT NOT NULL DEFAULT '',
  variant TEXT NOT NULL CHECK (variant IN ('on', 'off', 'foundry')),
  understood INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_agent_flag_value ON agent_flag(flag_value);

-- TESTOPS-89. Why a token did not arrive, recorded where the ledger records everything else. One
-- row per lookup, and no column can hold a token: ``access_token`` is not in this table's
-- vocabulary by construction, and ``attempts`` is the probe's own token-free JSON. A page that says
-- "no token" without this row beside it is the state this ticket exists to end.
CREATE TABLE IF NOT EXISTS agent_token_probe (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT NOT NULL,
  endpoint TEXT NOT NULL DEFAULT '',
  endpoint_variable TEXT NOT NULL DEFAULT '',    -- the env var that set it, '' when derived
  model TEXT NOT NULL DEFAULT '',
  model_variable TEXT NOT NULL DEFAULT '',
  environment_token INTEGER NOT NULL DEFAULT 0,  -- 1: TESTOPS_AGENT_TOKEN was set. Never its value.
  token_obtained INTEGER NOT NULL DEFAULT 0,
  token_source TEXT NOT NULL DEFAULT '',         -- environment | imds | az | ''
  imds_attempted INTEGER NOT NULL DEFAULT 0,
  imds_answered INTEGER NOT NULL DEFAULT 0,
  imds_status INTEGER,
  imds_cause TEXT NOT NULL DEFAULT '',
  imds_error_code TEXT NOT NULL DEFAULT '',
  imds_detail TEXT NOT NULL DEFAULT '',
  imds_api_version TEXT NOT NULL DEFAULT '',     -- the version that answered, when one did
  imds_attempt INTEGER NOT NULL DEFAULT 0,
  imds_elapsed_ms INTEGER NOT NULL DEFAULT 0,
  imds_attempts TEXT NOT NULL DEFAULT '[]',      -- every attempt, as the probe recorded it
  az_present INTEGER NOT NULL DEFAULT 0,
  az_answered INTEGER NOT NULL DEFAULT 0,
  az_cause TEXT NOT NULL DEFAULT '',
  az_detail TEXT NOT NULL DEFAULT '',
  az_elapsed_ms INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_agent_token_probe_at ON agent_token_probe(at);
