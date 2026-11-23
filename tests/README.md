# TestOps test suite

## Install

    pip install -e ".[dev]"

`pytest` is declared under `[project.optional-dependencies].dev` in `pyproject.toml`.

## Run

From the repository root:

    env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
      .venv/Scripts/python.exe -m pytest -q

The stripped environment matters: with an inherited `PYTHONPATH` or a different interpreter the
result is an environment error, not a pass.

## Fast lane

Three tests build a wheel and a venv to prove the package works when *installed*
(`test_distribution.py`, TESTOPS-8). The wheel is built once per session and shared with the
packaging check (`test_packaging.py`, TESTOPS-48), so there is one build, not one per test. They
reach no network but take ~20s, and the distribution tests are marked:

    ... -m "not distribution"

CI runs the whole suite; the fast lane skips them by marker, never by deleting them.

## What the suite covers

The suite is deliberately small. It pins the invariants later tickets depend on:

- the packaging declaration matches the packages that exist (`test_packaging.py`);
- `package-data` ships every non-Python file in the package - the built wheel's namelist is the
  authority, so a new template or static directory is a failing test rather than a 500 on an
  installed copy (`test_packaging.py`, TESTOPS-8 AC5 / TESTOPS-48);
- a wheel built from a copy of the tree, installed into a fresh venv, imports from that venv's
  site-packages (never the checkout) and serves `/`, `/runs`, `/config` and a case page with 200
  from a store it created - proving `schema.sql` and the prompt files shipped (`test_distribution.py`,
  TESTOPS-8 AC1/AC2);
- `store/schema.sql` creates the tables the pipeline uses (`test_store_schema.py`);
- the schema version is recorded per snapshot, and a v2 claim records 2 (`test_schema_version.py`);
- applying the schema twice leaves an identical structure (`test_schema_idempotent.py`);
- a store built at v1 opens, its claims read back as v1 with absent provenance, and the rebuilt
  `claim` table is shaped like a new one (`test_migration_v1.py`, fixture in `v1_store.py`);
- the database itself refuses a v2 claim without its assertion coordinates, including when the
  INSERT is written by hand (`test_claim_constraint.py`);
- every source declares its identity, capabilities and state, and Jira/ADO are `blocked` with the
  Quilter policy reason (`test_source_registry.py`);
- a source declared `available` that fails at use stops the run, and a `blocked` source is refused
  rather than returning an empty result (`test_source_registry.py`);
- every run records the registry in its snapshot, and a claim's `sources_missing` is derived from it
  (a fake absent source flows into the claims without an analyser naming it)
  (`test_source_registry.py`);
- an absent source and an empty source produce different verdicts, different sentences and
  different pages, read back from stored rows in both directions (`test_source_registry.py`);
- the case page's "what could not be checked" section names the reason and who blocked it, not just
  the source (`test_source_registry.py`);
- no source needs a credential to be declared, and a run writes no credential into the snapshot
  (`test_source_registry.py`);
- an empty `sources_missing` list stays distinguishable from NULL *and* is only a fact when an
  assessment was recorded with it; a claim nobody assessed reads as "not assessed"
  (`test_sources_missing.py`, `test_sources_assessed.py`);
- a claim whose sources were never assessed, one assessed with nothing missing, and one assessed
  with names missing each render their own exact sentence, from stored rows
  (`test_sources_assessed.py`);
- a v2 store migrates so that a claim with no registry in its snapshot becomes "not assessed",
  while a registry-recorded claim keeps its assessment (`test_sources_assessed.py`, fixture in
  `v2_store.py`);
- the read model returns statement, provenance and blind spots in one call
  (`test_read_model.py`);
- a v2 claim round-trips every new field through a fresh connection
  (`test_claim_v2_roundtrip.py`);
- a store written by a newer schema is refused rather than read or written
  (`test_schema_too_new.py`);
- a claim survives a round trip through a fresh connection unchanged (`test_claim_roundtrip.py`);
- the level-fitness analyser classifies a browser claim asserted over HTTP as `gap` and a
  response-body claim as `distinct`, offline (`test_level_fitness.py`);
- the emission gate turns `gap` into exactly one finding and `distinct` into none
  (`test_emission_gate.py`);
- `cases.fingerprint` is stable for the same evidence and differs for a different subject
  (`test_fingerprint.py`);
- a suite with no test files exits 5 (no tests collected), never 0 (`test_collection_gate.py`);
- nothing in the run writes to the repository or to `data/` (`test_isolation.py`);
- the suite cannot open a product store for writing: a test that calls `sqlite3.connect` or
  `db.connect` on `data/testops.db` fails at the connection, a store under `tmp_path` works, and
  the only permitted access to a real store is a declared read-only open
  (`file:<path>?mode=ro`), which SQLite enforces (`test_store_guard.py`, guard in
  `conftest.py`/`support.py`);
- `testops scrub-fixtures` reports every case whose `analyser` is not a registered analyser, and
  removes only with `--yes`: the case, its findings, its decisions and its orphaned suppressions
  go; the run, snapshot, artefacts, observations and claims stay (`test_scrub_fixtures.py`);
- a case naming an unregistered analyser answers 404 with the "no longer in the store" page, is
  not listed on the dashboard, and a registered case still renders (`test_unregistered_case_page.py`);
- every file the collector refused is recorded with its reason and kind, a capability is read /
  returned-nothing / could-not-be-read with a different sentence for each, a Java product's run
  names the `.java` files it skipped and says no product code file was fetched, and the kind list is
  configuration (`test_skipped_is_not_consulted.py`).

Every test that needs a database creates it under pytest's `tmp_path`. No test reads the network,
credentials, Jira, or an external repository - and no test may write to the live store.

## Fixtures and the live store

A review fixture belongs in a COPY of `data/`, never in the live store (TESTOPS-35). The reviewer
workflow is `factory/prompts/REVIEW-WORKFLOW.txt`. If a fixture has already reached the live
store, run `python -m testops.cli scrub-fixtures --dry-run` first and `--yes` only after reading
what it will remove; never hand-edit SQLite.
