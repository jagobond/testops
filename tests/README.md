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