# TESTOPS-34 — build report

Verdict: **implemented, suite green, rehearsed on a copy of the live store**. The live store at
`C:/Users/Chester/Projects/testops/data` was read only (SQLite opened `?mode=ro`); nothing in it was
written, migrated or deleted.

## What the defect actually was

The Product Owner read `case-cotw-dup-20261120T194032` and asked what an open case telling him there
were no findings was doing there. Two separate things were true:

1. **The creation path was already gated.** Since TESTOPS-4 the pipeline writes one case per
   *actionable* claim, so a run that raises nothing writes no `case_` row. The four rows the Product
   Owner named (`case-cotw-dup-20261120T153507`, `case-cotw-dup-20261120T194032`,
   `case-cotw-levels-20261121T173120`, `case-cotw-levels-20261121T173223`) are legacy rows from the
   older one-case-per-run shape: no `-01` suffix, one row per run.
2. **The read path had no rule.** `cases.list_cases` returned every `case_` row, so those legacy rows
   were still listed as open cases waiting for a decision. A case exists to carry a decision about a
   finding; a row with no finding is evidence that a run happened, not a case. The rule was missing
   from the query every list goes through.

## What changed

| File | Change |
|------|--------|
| `testops/cases.py` | `list_cases` now carries `WHERE EXISTS (SELECT 1 FROM finding f WHERE f.case_id = c.id)` in the query itself, plus an optional `run_id` filter. Every caller — dashboard, CLI, run page — gets the rule without remembering it. No row is deleted. |
| `testops/queries.py` | `run_analysis` split into `run_analysis` (per case, unchanged behaviour), `run_analysis_by_id` (per run, findings counted over all its cases) and one shared `_run_analysis`. New `_source_facts` (one reader for the recorded registry, used by the case page, run page and runs list), `run_read` (a run's page model), `cases_for_run`, `list_runs` (counts: claims, cases with a finding, findings, and how many are decided). `case_row` gains `run_id`. |
| `testops/web/app.py` | New `GET /runs` (`runs_index`) and `GET /run/<run_id>` (`run_response`/`run_page`). A quiet run renders the TESTOPS-22 block unchanged — "No findings in this run", the counts, the commit, "What this run could not consult" — plus a sentence saying a case carries a decision about a finding and this run raised none. A run with findings lists its cases; a run whose cases are all decided says so ("All decided", "a closed finding is evidence, not a clean bill"). `stale_run_page` answers 404 for a pruned id and for an unregistered analyser. Home page links to `/runs` and, when there are no cases, to the newest run. A zero-finding legacy case page says it is not a case and links to its run. |
| `testops/cli.py` | `testops runs [--project] [--limit]`: every run with claims, findings and cases. `testops cases` inherits the query rule, so it no longer prints `findings=0` rows. |
| `tests/test_run_view.py` | 10 new tests (list query, closed-vs-quiet distinction, runs view, run page, legacy row, 404s). |
| `tests/test_case_per_claim.py` | 1 new test: a pipeline run that raises nothing keeps its run row and has a page. |
| `tests/test_unregistered_case_page.py` | The control case now carries a finding; without one it would be excluded by the new rule rather than by the unregistered-analyser rule, and the test would prove nothing. |

No analyser, pipeline, scoring or schema change. No migration: the rows stay where they are.

## Acceptance criteria

| id | where |
|----|-------|
| AC1 | `tests/test_case_per_claim.py::test_a_run_that_raised_nothing_keeps_its_run_and_has_a_page` drives the real pipeline over a corpus whose only claim is `distinct`: no case, no finding, the run row kept, and `/run/<id>` shows the counts, the commit and the blind spots. |
| AC2 | The rule is in `cases.list_cases`'s SQL. `tests/test_run_view.py::test_the_case_list_query_cannot_return_a_case_with_no_finding` inserts a zero-finding row beside a real case and asserts no list (unfiltered, project-filtered, limit 500) returns it. |
| AC3 | The row is asserted still present in the same test. It is not a case, so it is absent from every list; it is still evidence, so `/case/<old id>` still renders and names the run. |
| AC4 | `tests/test_run_view.py::test_the_quiet_run_page_survives_reached_by_run_id` renders `app.run_response(conn, run_id)` and asserts the TESTOPS-22 text: heading, feature/scenario/exclusion counts, commit, analyser, "What this run could not consult", no percentages. All six TESTOPS-22 tests still pass unchanged. |
| AC5 | No analyser, pipeline or score code touched. `tests/test_level_sample_agreement.py`, the duplication corpus tests and the per-claim verdict tests pass unchanged; the live store's claim rows and verdict counts are identical before and after (read only, below). |

## Live store: case list before / after

Read from `C:/Users/Chester/Projects/testops/data/testops.db` with `?mode=ro`, running the old query
and the new one side by side.

```
BEFORE (old query): 184 rows; 4 with zero findings
AFTER  (new query): 180 rows; 0 with zero findings

case-cotw-dup-20261120T153507     before=True  after=False  row_still_in_store=True  run=cotw-dup-20261120T153507
case-cotw-dup-20261120T194032     before=True  after=False  row_still_in_store=True  run=cotw-dup-20261120T194032
case-cotw-levels-20261121T173120  before=True  after=False  row_still_in_store=True  run=cotw-levels-20261121T173120
case-cotw-levels-20261121T173223  before=True  after=False  row_still_in_store=True  run=cotw-levels-20261121T173223

Totals: case_ 184 | finding 683 | claim 2070 | run 40   (unchanged)
Claims by verdict: distinct 1536, duplicate 143, gap 28, necessary 25, optimal 36,
                    overbuilt 67, review 40, unplaced 195   (unchanged)
```

## How a reader reaches the run instead

Three ways, all read from the store:

1. **`/runs`** (or `testops runs`): every run, newest first, with its claims, its findings, its
   cases, the commit it looked at and what it could not consult. The four rows above appear here as
   runs, with `No findings`.
2. **`/run/<run_id>`** — e.g. `/run/cotw-dup-20261120T194032`. This is the TESTOPS-22 page,
   addressed by the run. The run id is printed in the page header.
3. **The old case URL still works**: `/case/case-cotw-dup-20261120T194032` renders the same honest
   page and says "This row raised no finding, so it is not a case. The run it recorded is
   cotw-dup-20261120T194032", linking to `/run/...`. A shared or bookmarked URL is not broken by
   the row ceasing to be a case.

## Rehearsal (copy at the scratch dir, `TESTOPS_HOME` pointed at it)

`cp -r data <scratch>/t34-rehearsal/data`, `TESTOPS_HOME=<scratch>/t34-rehearsal`.

`testops cases` — 0 rows with `findings=0` (the four are gone from the list).
`testops runs` — 40 runs, e.g.:

```
reqoverflow-dup-20261122T164254   ok   claims=17  findings=17  cases=17  duplication
cotw-levels-20261122T120603       ok   claims=94  findings=3   cases=3   level_fitness
```

All 40 run pages render 200 (no missing-blob or bad-meta failures). The Product Owner's example:

```
GET /run/cotw-dup-20261120T194032 -> 200
← all cases · all runs   cotw · Duplication   No findings · Ran 45 hours ago at
cotw-bdd@a3f19853, cotw-continuity@b901ea4d · cotw-dup-20261120T194032
No findings in this run
This run analysed 6 feature files and 41 scenarios: 17 exclusion patterns read from
CotwBdd.csproj left 21 of 27 stored feature files outside the build, and the duplication analyser
recorded no claim about any of them.
What this run could not consult
This run recorded no source registry, so it cannot say which sources it could not consult.
Nothing here says the sources it did not have were clean.
A case carries a decision about a finding. This run raised none, so it created no case: the run
itself is the record, and it stays in the store with the counts above.
```

And a run whose findings were all closed, for the contrast:

```
GET /run/cotw-levels-20261121T173046 -> 200
cotw · Level fitness   All decided · Ran 23 hours ago ... · cotw-levels-20261121T173046
This run raised 42 findings
... [the case: Resolved, 42 findings, case-cotw-levels-20261121T173046]
Every case this run raised has been decided, so its findings are closed. The run still recorded
them: a closed finding is evidence, not a clean bill.
```

## Test suite

Baseline before the change: 370 passed, 7 skipped. Now: **381 passed, 7 skipped**, run from the
worktree with

```
env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1 PYTHONPATH=. \
  C:/Users/Chester/Projects/testops/.venv/Scripts/python.exe -m pytest -q
```

`import testops` resolves to `C:\Users\Chester\Projects\testops-t34\testops\__init__.py`.

## What the Product Owner has to run

Nothing. There is no migration, no deletion and no new dependency. `testops serve` gains `/runs` and
`/run/<id>`; `testops runs` is the same view in the terminal.
