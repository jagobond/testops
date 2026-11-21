---
id: TESTOPS-3
title: Claim schema v2 — one claim per assertion, with provenance and blind spots
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-2
---

# TESTOPS-3 — Claim schema v2

## Why

A claim is currently one row per scenario. Its `statement` cannot be checked by a reader: it does not
say which of the scenario's assertions it is about, where that assertion lives in the repository, or
what source the analysis could not consult. The Product Owner's ruling (2026-11-21): **a claim is
per assertion**, because the system is claiming it has found something worth a development team's
attention, and the case is how that claim is presented for a decision.

This ticket defines and stores that shape. It does **not** change what the analyser concludes —
TESTOPS-4 populates the new fields.

## The shape

Every claim must be able to answer these without re-reading any repository:

| question | field |
|---|---|
| what exactly is asserted? | `assertion_text` — the Gherkin step text, verbatim |
| where is it asserted? | `assertion_path`, `assertion_line`, `assertion_commit` |
| what is the claim's own heading, in plain words? | `statement` |
| what kind of interaction does it need? | `interaction_label` — the plain-language label |
| the shorthand, for debugging only | `interaction_code` — `I1`..`I4`, `KP`, kept out of primary text |
| what did the instrument actually reach? | `span` |
| what establishes it, per the analyser's rule? | `established_by` |
| what could it not consult? | `sources_missing` |
| what does the analysis propose? | `proposed_action` |

## Scope

In scope: `store/schema.sql`, a migration path in `store/`, `store/db.py`, `queries.py`, and
`tests/`.

Out of scope: `analysers/level_fitness.py` and everything that decides a verdict (TESTOPS-4), the
web UI (TESTOPS-6), and any source adapter (TESTOPS-5).

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A `schema_version` is stored per snapshot, and a claim written under v2 records `schema_version = 2`. |
| AC2 | Applying the schema to an empty database twice leaves an identical structure and raises nothing. |
| AC3 | A database created at v1 still opens, and its claims read back with `schema_version = 1` and empty provenance fields — no exception, and no invented values standing in for absent ones. |
| AC4 | The store refuses a v2 claim with no `assertion_path`, `assertion_line` or `assertion_commit`. A constraint, not a convention: the refusal must come from the database, so a bypass path does not exist. |
| AC5 | `sources_missing` is an explicit list, and an empty list stays distinguishable from NULL on read. "We consulted everything" must never look like "we recorded nothing". |
| AC6 | `queries.py` returns statement, provenance and blind spots in one call, so no page can render a claim without them. Prove it: the read model's keys include all three, and a test fails if provenance is dropped from the query. |
| AC7 | Round-trip fidelity: a v2 claim written through `db.add_claim` and read through a fresh connection returns every new field unchanged, including line numbers and the missing-sources list. |
| AC8 | Migration is forward-only: opening a database whose `schema_version` is newer than the code understands fails loudly rather than reading it and writing v2 rows into it. |
| AC9 | Every existing test still passes, and the new tests are added to the same suite. Nothing under `analysers/` or `web/` is modified. |

## Verification

```
cd C:/Users/Chester/Projects/testops
env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
  .venv/Scripts/python.exe -m pytest -q
```

## Notes for the builder

- **Do not migrate v1 rows in place.** The record of what was claimed before this change is itself
  evidence; a v1 row keeps `schema_version = 1` and its empty provenance forever.
- `db.connect()` currently applies `schema.sql` unconditionally, which means `CREATE TABLE IF NOT
  EXISTS` silently leaves old structure in place. Whatever mechanism you choose must make a v1
  database become v2 *and* stay readable, and must be proven by AC3 rather than assumed.
- `span` is a list of layers; `sources_missing` is a list of source names. Store them as JSON text
  and be explicit about the empty case, so AC5 is decidable.
- The shorthand (`I4`, `KP`) is for debugging and belongs in `interaction_code`. `interaction_label`
  is what a reader sees; the Product Owner's team will not know the codes.
- If a criterion cannot be met without touching `analysers/` or `web/`, stop and report — the Lead
  will split the ticket rather than widen it.
