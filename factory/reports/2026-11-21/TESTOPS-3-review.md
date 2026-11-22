# TESTOPS-3 review — 2026-11-21 (reviewer)

## Verdict

PASS — all nine criteria hold under independent attack, including raw SQL attempts to bypass the constraint and a future-version store that refuses to open without changing a byte.

## Criteria

- AC1 — HOLDS. `snapshot.schema_version` column added; builder tests assert v2 writes record 2. My probe: `schema_meta.schema_version = 2` recorded on every new store via `migrate.prepare`.
- AC2 — HOLDS. Applied `schema.sql` twice to a fresh database in my own probe: no exception, identical structure (only `INSERT OR REPLACE` bookkeeping differs).
- AC3 — HOLDS. I built a store from `git show feature/f1:testops/store/schema.sql`, inserted a v1 claim, opened it with the new code: claim reads back `schema_version = 1`, all provenance fields `None`, `span`/`sources_missing` `None` (not `[]`), statement/confidence/support byte-for-byte intact. The file's bytes change on open (structural rebuild), but the v1 row's values are untouched — that is the migration writing structure, not rewriting the record.
- AC4 — HOLDS. Raw `INSERT INTO claim ...` bypassing `add_claim`, on a store I built myself: NULL provenance refused, blank `'  '` path refused, NULL line refused — all `IntegrityError: CHECK constraint failed: claim_v2_requires_provenance`. A v1 row (schema_version=1, NULLs) still inserts, and a fabricated `schema_version=3` row is also refused by the same constraint. The refusal is genuinely in the database.
- AC5 — HOLDS. `jn`/`_list_or_none` keep `NULL` and `[]` distinct both ways; tests cover it; my AC3 probe confirmed a v1 claim reads back `None`, not `[]`.
- AC6 — HOLDS. `claim_view` is the single constructor carrying statement, `provenance`, `sources_missing` and `span` together; `finding_rows` routes through it. The field-by-field comparison test fails if provenance is dropped from the query.
- AC7 — HOLDS. Round-trip test writes via `add_claim` and reads via a fresh connection; every new field including `assertion_line` and `sources_missing` compares equal.
- AC8 — HOLDS. I set `schema_version = 3` in `schema_meta` myself: `db.connect` raises `SchemaTooNewError` before any other statement, and the file's sha256 is unchanged after the failed open. A non-numeric version string raises `SchemaCorruptError` instead of being guessed.
- AC9 — HOLDS. Suite run by me, clean environment: 53 passed, 0 failures. `git diff feature/f1..HEAD --stat` touches nothing under `analysers/` or `web/`.

## Three sharpest concerns

1. The claim-table rebuild drops the table while `foreign_keys = OFF`. `PRAGMA foreign_key_check` runs after, which is the right mitigation, but a claim table with views or triggers attached would lose them silently. None exist today; note it for future schema work.
2. `add_claim` accepts a `schema_version` argument unrelated to the snapshot's `schema_version`. Nothing ties a claim's version to the snapshot it belongs to, so a writer could put a v2 claim in a v1-marked snapshot. TESTOPS-4 should decide whether that coupling matters.
3. `stored_version` returns `None` for a store with no `schema_meta`, and `prepare` then trusts table-shape sniffing (`has_column`). Correct for pre-v1 stores, but a store with a v2-shaped claim table and no meta row is silently adopted as current rather than flagged. Low risk, worth a line in migrate.py's docstring.

## Demo

The problem: a claim was one unverifiable sentence per scenario — no coordinates, no provenance, no record of what was not consulted, and a store that could not refuse a claim a reader could not check.

What changed: claims are per assertion. v2 claims carry the Gherkin step text, path, line and commit, a plain-language interaction label, the span reached, the establishing rule, an explicit missing-sources list (empty list vs NULL kept distinct) and a proposed action. Per-snapshot `schema_version` recorded; forward-only migration rebuilds the v1 claim table with the CHECK constraint while never rewriting v1 rows; a store newer than the code refuses to open.

How we know it works: reviewer suite run (53 passed), plus independent probes — raw SQL INSERTs bypassing `add_claim` refused by the CHECK constraint (including blank-path and fake schema_version=3); a store built from the feature/f1 schema opens with v1 rows intact and NULL (not empty-list) provenance; a store bumped to version 3 fails to open with its bytes unchanged; double schema application is idempotent.

What it does not solve: nothing populates the new fields yet (TESTOPS-4), the UI does not render provenance (TESTOPS-6), and source adapters that would fill `sources_missing` are TESTOPS-5.

Where to look: `testops/store/schema.sql:76` (the constraint), `testops/store/migrate.py:67` (prepare/forward-only), `testops/queries.py:44` (claim_view), `tests/v1_store.py` and `tests/test_migration_v1.py`.
