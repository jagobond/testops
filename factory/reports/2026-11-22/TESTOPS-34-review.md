# TESTOPS-34 review — reviewer

## Verdict — PASS

The rule lives in the SQL every list read goes through, the four legacy rows stay in the store but stop
being listed, the closed case and the quiet run are provably distinct on both surfaces, and a constructed
store with five shapes of run returns the right answer for each.

## Criteria

- **AC1 HOLDS.** The pipeline writes one case per actionable claim and deletes a case whose finding
  failed to emit (`testops/pipeline.py:247-262`, `:400-412`), so a run that raises nothing writes no
  `case_` row. Probe-verified: a run with a claim and no case row (`rq5-nocase`) renders `/run/<id>` 200
  with badge "No findings" and the sentence "Raised no finding, so it created no case."
- **AC2 HOLDS.** `cases.list_cases` carries `WHERE EXISTS (SELECT 1 FROM finding f WHERE f.case_id = c.id)`
  in the query itself (`testops/cases.py:83`), and every list read routes through it or repeats the
  predicate (see Callers). A test asserts the list query cannot return a zero-finding row
  (`tests/test_run_view.py`), and my probe confirmed it against a store copy: unfiltered, project-filtered
  and limit-500 all exclude it. The four legacy cases are absent from every list. "All decided"
  (`state=resolved`) and "no findings" (absent from the list) are distinguishable in the output.
- **AC3 HOLDS.** On the copy, before the suite: `case_ 184, finding 683, claim 2070, run 40`. After a
  full suite run: identical, plus the probe rows I inserted. All four legacy rows still present
  (`case-demo-product-dup-20261120T153507/-T194032`, `case-demo-product-levels-20261121T173120/-T173223`), finding 683,
  claim 2070 and run 40's rows all intact. A reader reaches the run via `/runs`, `/run/<run_id>`, or the
  link on the old case URL.
- **AC4 HOLDS.** The quiet-run block is unchanged and reachable by run id; all TESTOPS-22 tests pass
  unchanged in the 381-passed suite. Probe: `/run/rq1-zero` 200, "No findings in this run", blind-spot
  section, no percentages.
- **AC5 HOLDS.** No analyser/pipeline/score code touched in the diff; verdict and claim rows on the copy
  unchanged before and after the suite.

## The four cases — each constructed on a copy of the live store

Probe rows inserted into a copy (`case_ 184→188, finding 683→686, run 40→45`); probe script and copy left
in the scratch dir, live store never written.

| constructed shape | `list_cases` returned |
|---|---|
| zero-finding case (`case-rq1-zero`) | excluded from every list (default, project-filtered, limit 500, run-filtered). Row still in store. |
| one finding, no decision (`case-rq2-open`) | listed, `findings=1, state=open` |
| one finding, decided via `set_state(resolved)` (`case-rq3-decided`) | listed, `findings=1, state=resolved` — distinguishable from a quiet run |
| findings all suppressed, no `case_state` row (`case-rq4-suppressed`) | listed, `findings=1, state=open` — see Concern 2 |
| run with a claim and no case at all (`rq5-nocase`) | no case; `/runs` shows it with badge "No findings" |

Run view: `rq1-zero`/`rq5-nocase` → "No findings"; `rq3-decided` → "All decided" with "a closed finding is
evidence, not a clean bill"; `rq2-open` → "1 finding" hot. Closed and quiet are distinct on both `/runs`
and `/run/<id>`.

## Callers

Every `FROM case_` select in `testops/`, checked:

- `cases.list_cases` (`cases.py:79-94`) — filtered (EXISTS predicate). Feeds `cli.cmd_cases`,
  `queries.recent`, `queries.latest_per_analyser` (dashboard), `queries.cases_for_run` (run page).
- `queries.list_runs` (`queries.py:650-661`) — counts cases with the same EXISTS predicate inline. Filtered.
- `queries.case_row`, `queries.run_analysis`, `scrub.py`, `retention.py`, `pipeline.py` inserts/deletes —
  single-case reads and writes, not lists; correctly unfiltered.

No caller lists cases without the predicate.

## Old URL check

`GET /case/case-rq1-zero` → 200, badge "No findings" (not "Resolved"), the sentence "This row raised no
finding, so it is not a case. The run it recorded is rq1-zero" linking `/run/rq1-zero`, then the honest
quiet-run block. `decision_form` renders nothing for a decisionless zero-finding case — no "Decide this
case" form is offered on a row that is not a case. Honest.

## Nothing deleted

Copy counts before suite `184/683/2070/40`, after suite `184/683/2070/40` (plus my 4 probe runs / 4 probe
cases / 3 probe findings / 1 probe claim, all mine). finding id 683, claim id 2070, run 40's rows and the
four legacy case ids all verified present after the suite.

## Three sharpest concerns

1. **Closure is defined by `case_state` only.** `run_badge`'s "All decided" and `decided_cases` count
   terminal `case_state` rows. My suppression-only construction (suppression rows present, no
   `case_state` row) showed as "1 finding", open, hot — not closed. Product code cannot produce that
   state (`set_state` writes both halves), but TESTOPS-35 just proved hand-written rows exist, and the
   ticket's note says "findings but all suppressed" is a case that exists and is closed.
2. **`list_runs` filters unregistered analysers after the SQL `LIMIT ?`** (hard-coded 200 at
   `queries.py:668`), and applies the caller's limit in Python. A store holding 200 fixture runs would
   crowd every real run out of `/runs`, and a CLI `--limit` above 200 silently truncates.
3. **The legacy case page can still offer "Reopen this case"** if a zero-finding row ever had a decision
   recorded on it (`decision_form`'s `n==0 and terminal` branch, `app.py:1298-1302`) — a decision form on
   a row the tool now says is not a case. None of the four legacy rows holds one today, so it is latent.

Suite: 381 passed, 7 skipped, from the worktree (`testops.__file__` confirmed inside `testops-t34`).
