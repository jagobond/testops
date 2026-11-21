---
id: TESTOPS-2
title: Test harness baseline
feature: F1
status: ready
autonomy: build
depends_on: none
---

# TESTOPS-2 — Test harness baseline

## Why

TestOps has no automated tests. Every number the analysers have produced so far came from
throwaway probe scripts that no longer exist, so no claim about precision, agreement or
classification can be reproduced. More urgently for the factory: the review gate is a test run
that distinguishes *pass* from *genuine failure* from *environment error*, and there is nothing to
run. A reviewer asked to judge the next ticket can only read the diff and accept the builder's
word.

This ticket creates the smallest suite that makes the next ticket reviewable. It does not aim at
coverage; it aims at the invariants that everything later depends on.

## Scope

In scope: `pyproject.toml`, `tests/`, and the minimum fixtures those tests need.

Out of scope: changing analyser behaviour, changing the schema, adding any network-dependent or
Jira-dependent test, and "while I was there" refactors of `testops/`.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | `pytest` is declared as a development dependency in `pyproject.toml` and installed by the documented command. |
| AC2 | `pyproject.toml`'s package list names only packages that exist. It currently declares `testops.cases` (a module, not a package) and omits `testops.web` and `testops.scripts`, so an editable install of the current tree cannot import the UI. |
| AC3 | `python -m pytest` from the repo root collects and passes at least 8 tests, offline, with no credentials and no network access. |
| AC4 | A test applies `store/schema.sql` to a fresh temporary database and asserts the tables the pipeline depends on exist: `snapshot`, `artefact`, `observation`, `run`, `claim`, `inference`, `case_`, `finding`, `suppression`, `case_state`. |
| AC5 | A test writes a claim through `store.db.add_claim` and reads it back through a fresh connection, asserting statement, verdict, subject_ref and confidence survive unchanged. This is the evidence invariant in miniature: evidence is immutable, everything else is derived. |
| AC6 | A test drives `analysers.level_fitness.analyse(...)` over an in-memory fixture and asserts a claim that needs a browser but is asserted over HTTP is classified `gap`, and a claim settled by the response body is classified `distinct`. No network, no repository checkout. |
| AC7 | A test asserts the emission gate in `pipeline._emit`: a claim with verdict `distinct` raises no finding, and a claim with verdict `gap` raises exactly one. |
| AC8 | A test asserts that re-running the same evidence produces the same `cases.fingerprint`, and that a different `subject_ref` produces a different one. Suppression depends on this and nothing currently proves it. |
| AC9 | Running the suite with every test file absent exits with pytest's "no tests collected" code, not success — i.e. a broken collection must not read as a pass. |
| AC10 | No test writes to `data/testops.db`, to the repository, or to any path outside pytest's `tmp_path`. |

## Verification

```
cd C:/Users/Chester/Projects/testops
env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
  .venv/Scripts/python.exe -m pytest -q
```

## Notes for the builder

- Reuse the existing APIs rather than inventing a harness: `store.db.connect(path)`,
  `store.db.add_claim(...)`, `analysers.level_fitness.analyse(features, bindings, surfaces,
  uri_for_path, budget)`, `cases.fingerprint(...)`, `pipeline._emit(...)`.
- Fixtures are in-memory objects, not files on disk, wherever the API allows it. AC6 must not
  need `cotw-bdd` to be present on the machine.
- If an acceptance criterion cannot be satisfied without changing product code, **stop and report
  it** rather than changing `testops/`. A criterion that requires a product change is a finding
  about this ticket, and the Lead decides how to split it.
