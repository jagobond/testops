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

## What the suite covers

The suite is deliberately small. It pins the invariants later tickets depend on:

- the packaging declaration matches the packages that exist (`test_packaging.py`);
- `store/schema.sql` creates the tables the pipeline uses (`test_store_schema.py`);
- the schema version is recorded per snapshot, and a v2 claim records 2 (`test_schema_version.py`);
- applying the schema twice leaves an identical structure (`test_schema_idempotent.py`);
- a store built at v1 opens, its claims read back as v1 with absent provenance, and the rebuilt
  `claim` table is shaped like a new one (`test_migration_v1.py`, fixture in `v1_store.py`);
- the database itself refuses a v2 claim without its assertion coordinates, including when the
  INSERT is written by hand (`test_claim_constraint.py`);
- an empty `sources_missing` list stays distinguishable from NULL on read (`test_sources_missing.py`);
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
- nothing in the run writes to the repository or to `data/` (`test_isolation.py`).

Every test that needs a database creates it under pytest's `tmp_path`. No test reads the network,
credentials, Jira, or an external repository.