# TESTOPS-35 — build report

Verdict: **implemented and rehearsed on a copy**. Nothing in this report was run against the live
store at `C:/Users/<name>/Projects/testops/data`.

## What changed

| File | Change |
|------|--------|
| `testops/analysers/__init__.py` | Single registry of analyser names (`duplication`, `level_fitness`), read from the modules themselves. `is_registered()` is the only test for "could this build have raised this case". |
| `testops/scrub.py` | `plan()` / `scrub(conn, yes=False)`. Finds cases whose `analyser` is unregistered; removes the case, its findings, its decisions and its orphaned suppressions, on `yes` only. Never touches run, snapshot, artefact, observation or claim rows; a suppression goes only when no surviving finding carries its fingerprint. |
| `testops/cli.py` | `testops scrub-fixtures [--dry-run] [--yes]`. Report is the default; `--yes` performs; contradictory flags exit 2; a missing store exits 1 without creating one. Prints the store path, the analyser name, finding ids, fingerprints, per-table row counts, before/after totals and the remaining fixture count. |
| `testops/web/app.py` | `case_response()` answers 404 with the TESTOPS-30 page for a case whose analyser is unregistered, and the page names that analyser and points at `scrub-fixtures` instead of claiming retention pruned it. `stale_case_page` keeps its old wording (byte-identical) for genuinely missing ids. |
| `testops/queries.py` | The dashboard's `latest_per_analyser` skips such a case: a list entry whose link answers 404 would still repeat the fixture. |
| `tests/support.py`, `tests/conftest.py` | Session guard patches `sqlite3.connect` and `testops.store.db.connect`: a writable open resolving under a checkout's `data/` raises `StoreWriteRefused` before SQLite (and before `db.connect` creates the directory). A `file:...?mode=ro`/`immutable=1` open is the declared read-only path and SQLite enforces it. Both this checkout's data dir and the main checkout's are protected, because the suite usually runs from a worktree with no `data/`. |
| `tests/test_scrub_fixtures.py`, `test_unregistered_case_page.py`, `test_store_guard.py` | 17 new tests. |
| `factory/prompts/REVIEW-WORKFLOW.txt` | The reviewer workflow: worktree, copy of the store, `TESTOPS_HOME`, where a fixture goes, what to do if one reached the live store, and what a review may never do. |
| `factory/prompts/review-*.txt` (24 files) | A standing rule at the top: a fixture belongs in a COPY of the store; never write into `data/`; `scrub-fixtures --dry-run` then `--yes`; never hand-edit SQLite. |
| `tests/README.md` | The guard and the command recorded where the suite is documented. |

## Rehearsal (on a copy at `%TEMP%/scrub`)

`cp -r data/. %TEMP%/scrub/data/`, `TESTOPS_HOME=%TEMP%/scrub`, then the exact command shipped.

`scrub-fixtures --dry-run`:

```
store         ...\scrub\data\testops.db
registered    duplication, level_fitness
fixture cases 1

  rev-duplicate
    project=review analyser='x' run=reqoverflow-dup-20261122T090439 findings=1
    finding 601 fingerprint 00000000000000000000000000001606

rows to remove: case_ 1 · finding 1 · case_state 0 · suppression 0
kept: the run, snapshot, artefacts, observations and claims the cases rested on

Dry run — nothing was removed. Re-run with --yes to remove these rows.
```

`scrub-fixtures --yes`:

```
removed suppression 0 · finding 1 · case_state 0 · case_ 1
store totals: case_ 168 -> 167 · finding 667 -> 666
fixture cases remaining: 0
```

Afterwards, on the copy:

- `/case/rev-duplicate` → 404 with the "no longer in the store" page (it was 404 with the
  "not one this build can run" variant before the removal, so the page never rendered between the
  deploy and the scrub); `rev-duplicate` never appears on `/`.
- a surviving case page is byte-for-byte identical before and after
  (sha256 `d066b27d…`, 11,788 bytes).
- claim verdict counts and the 2,053 claim rows unchanged; run 39 → 39; snapshot 22 → 22.
- a second `--dry-run` reports 0 fixture cases.

## Test suite

Baseline before the change: 334 passed, 7 skipped. Now: **351 passed, 7 skipped**, run from the
worktree with

```
env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 PYTHONPATH=. \
  C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe -m pytest -q
```

`import testops` resolves to `C:\Users\<name>\Projects\testops-t35\testops\__init__.py`.

## What the Product Owner has to run

```
cd C:/Users/<name>/Projects/testops
.venv/Scripts/python.exe -m testops.cli scrub-fixtures --dry-run
.venv/Scripts/python.exe -m testops.cli scrub-fixtures --yes
```

Expected deletion on the live store: `case_ 168 -> 167`, `finding 667 -> 666`, nothing else moved.
`rev-duplicate` is the only case with an unregistered analyser.
