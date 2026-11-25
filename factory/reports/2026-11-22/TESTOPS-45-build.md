# TESTOPS-45 build report — the store refuses a verdict no analyser emits

Built 22 Nov 2026 on `factory/testops-45-verdict-trigger`, from HEAD `43c68d8`
(`Merge TESTOPS-43: partial reads named, clean runs unchanged`). Ticket: `factory/tickets/TESTOPS-45.md`.
Finding: `factory/reports/2026-11-22/TESTOPS-9-review.md`, section *The CHECK constraint*.

## What was built

- `testops/store/schema.sql` — a `verdict_vocabulary` table and two triggers:
  `claim_verdict_insert` (`BEFORE INSERT ON claim`) and `claim_verdict_update`
  (`BEFORE UPDATE OF verdict ON claim`). Both refuse `NEW.verdict` unless it is a row in the
  vocabulary with `status = 'current'`. The table lists the five current names and records
  `optimal`, `overbuilt`, `necessary` as retired by `TESTOPS-9`, with a CHECK that a retired name
  must carry the ticket that retired it.
- `testops/store/verdicts.py` — the one Python implementation of the rule:
  `validate_verdict(value, allowed)` names the value and the allowed set; `current(conn)` and
  `retired(conn)` read the store's definitions; `inventory(conn)` splits every non-current claim into
  *historical* (a documented retired name) and *unknown* (no record at all).
- `testops/store/migrate.py` — `CURRENT_VERSION = 5`. The upgrade is additive: `schema.sql` creates
  and seeds the vocabulary and installs both triggers on every open. No claim table is rebuilt, no
  row is copied and no verdict is rewritten.
- `testops/cli.py` — `testops check-store`. It prints the store path, the allowed set, the historical
  count with per-name counts, and every claim whose verdict is unknown; exit 0 when there are none,
  1 when there are. It refuses to create a missing store.
- `tests/test_verdict_trigger.py` — 15 tests (AC1–AC5), plus one existing assertion adjusted
  (`tests/test_sources_assessed.py`: version is no longer pinned to the literal 4).

## The decision, and why a trigger rather than a CHECK

A retroactive `CHECK (verdict IN (...))` cannot coexist with the stored evidence: the live store has
128 claims under retired names (`optimal` 36, `overbuilt` 67, `necessary` 25). A CHECK would either
reject them or force a rewrite of evidence to satisfy it, and the standing rule is that evidence is
immutable. A trigger constrains what is written *next*; it never validates or alters what was
written before. `PRAGMA` on the live store before this build: `schema_version = 4`, no triggers.

The allowed set has one definition: the `verdict_vocabulary` table. The triggers read it
(`WHEN NEW.verdict NOT IN (SELECT name FROM verdict_vocabulary WHERE status = 'current')`), and
`verdicts.current(conn)` reads the same table, so the CLI cannot disagree with the store. The retired
rows are in the same table so `check-store` can tell history from corruption without a second list.

## Criterion by criterion

| id | verdict | evidence |
|----|---------|----------|
| AC1 | SATISFIED (one limitation, below) | `tests/test_verdict_trigger.py::test_an_unknown_verdict_is_refused_on_insert_by_direct_sql` — six parameters (`total_nonsense`, `optimal`, `overbuilt`, `necessary`, `Distinct`, `""`), each written with `conn.execute` and no repository call; each raises `sqlite3.IntegrityError`, the refusal names all five allowed values, and the claim count stays 0. Also proved on a copy of the live store: the insert was refused and no row was written. |
| AC2 | SATISFIED | `::test_updating_a_verdict_to_an_unknown_value_is_refused` — a stored `gap` updated to `total_nonsense` and to `optimal` raises, the stored verdict stays `gap`, and `UPDATE claim SET statement = ...` still succeeds (the trigger is `UPDATE OF verdict`, so editing other columns is unchanged). Proved directly on the migrated live-store copy too. |
| AC3 | SATISFIED | `::test_the_128_retired_rows_stay_readable_and_render_as_today` — 36 `optimal` + 67 `overbuilt` + 25 `necessary` written into a store whose triggers are dropped (the legacy state), then reopened: the migration installs the triggers, all 128 rows remain with their names, and the render functions return exactly today's output (`list_judgement`: `Checked`/`Checked`/`Checked, but over-tested`; `verdict_label`: `Optimal`/`Overbuilt`/`Necessary`). On a copy of the live store, all 2,310 claim rows have the same SHA-256 before and after migration (`62d3b35b…`), and `check-store` reports the 128 as historical. |
| AC4 | SATISFIED | `::test_the_trigger_the_analysers_and_the_documents_name_the_same_set` — reads both installed trigger bodies from `sqlite_master`, asserts each reads `verdict_vocabulary` with `status = 'current'`, parses the names in each refusal message, and compares the trigger set to `emitted_verdicts()` (the AST scan of `testops/analysers`) and to all three documented places (schema column comment, `Claim` docstring, field comment) in both directions using the TESTOPS-9 `disagreement` helper. It also asserts the retired set equals `web.app.LEGACY_JUDGEMENT` and is disjoint from the allowed set. |
| AC5 | SATISFIED | `::test_check_store_reports_an_unknown_verdict` (one `total_nonsense` row → exit 1, the row is named with its id, run, analyser, `total_nonsense`, and every allowed name is printed); `::test_check_store_reports_retired_rows_as_history_not_corruption` (128 rows → exit 0, per-name counts, `unknown 0`); `::test_check_store_does_not_create_a_missing_store`. |
| AC6 | SATISFIED | 534 passed, 11 skipped (the 11 are the live-store page tests, which skip in a worktree with no `data/`). Demo Product latest run `demo-product-levels-20261122T204947`: 94 claims = 90 distinct / 1 gap / 2 review / 1 unplaced. DemoService latest run `demo-service-dup-20261122T205100`: 17 claims, 17 cases, all `duplicate`. Page rendering is byte-identical (`tests/test_projects_services.py::test_every_case_page_and_the_indexes_are_byte_identical_after_the_migration`). No analyser, pipeline, query or template file changed. |

## The one thing SQLite would not do

`RAISE(ABORT, message)` accepts a **string literal only**. I tested concatenation, `printf()`, a
subquery and `NEW.verdict` directly (SQLite 3.45.3): all are syntax errors, so a trigger cannot
interpolate the offending value into its message. The trigger therefore names the column and the
allowed set; the value is named by the one function (`verdicts.validate_verdict`) and by
`testops check-store`, which prints `verdict 'total_nonsense'` beside the row. This is a limit of the
SQLite trigger language, not a design choice, and it is why the rule is also expressed in Python
for anyone moving to Postgres, whose `RAISE EXCEPTION … USING` can format the value.

The set is written twice in `schema.sql` — once as vocabulary rows, once in the literal refusal
message — because SQL cannot build the message from a query. The AC4 test compares the two in both
directions, so the copy cannot drift.

## Exact numbers

- `env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1
  C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe -m pytest -q`
  → **534 passed, 11 skipped** in 90.66s. The 15 tests in `tests/test_verdict_trigger.py` are new;
  the one existing change is the version assertion in `tests/test_sources_assessed.py`.
- `tests/test_verdict_trigger.py`: 15 collected, 15 passed. `tests/test_verdict_vocabulary.py`: 6
  passed unchanged.
- Live-store copy migration: `migrated store v4 -> v5`, 2,310 claims, identical row digest,
  128 historical, 0 unknown, exit 0.

## What was not done

- No row of the live store was touched. Every live-store proof above used a copy under the builder
  scratch directory; the original remains at `schema_version = 4` with no triggers, as the TESTOPS-9
  review recorded. The next ordinary `db.connect()` will install the guard and record v5.
- No page was changed. An unknown verdict still renders through the existing fallback; `check-store`
  is the honest way to find such a row before a reader meets it. Making the page itself refuse or
  flag unknown verdicts is a UI decision this ticket did not take.
- The retired names are still rendered by `verdict_label` as their old capitalised words
  (`Optimal`, `Overbuilt`, `Necessary`); only the list surface maps them through
  `LEGACY_JUDGEMENT`. I pinned that as today's behaviour rather than changing a render, because AC3
  forbids a behaviour change and AC6 asks for pages unchanged.
