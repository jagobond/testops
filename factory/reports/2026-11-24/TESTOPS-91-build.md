# TESTOPS-91 build — the reply that is 90 percent of an answer is repaired, not discarded

2026-11-24, worktree `C:/Users/<name>/Projects/testops-t91`, branch
`factory/testops-91-repair-citations`, implementation commit `62117ab`.

Suite, from the project `.venv` with `PYTHONPATH`/`PYTHONHOME`/`VIRTUAL_ENV`/`CONDA_PREFIX` stripped
and `PYTHONNOUSERSITE=1`: **1357 passed, 2 skipped** (247 s). `tests/contracts` ran inside that
number and is green. No test reaches the network; the live measurement below is a signed-off script,
not a test.

`testops/judgement/client.py` was **not touched**. Product files changed: `testops/judgement/agent.py`
(the reply classifier, the citation repair round, one state) and `testops/web/app.py` (the report's
repaired column and one paragraph; the feedback gate accepts the new state). The agent-off page
template was not touched.

## The defect, and AC1

`parse_reply` required `citations` to be a list before it would return a `Reply`. A real reply of
the shape

    {"explanation": "The claim asserts ..."}

therefore returned `malformed`, `explain_case` recorded an error and served nothing — and the repair
round built in TESTOPS-90, whose whole purpose is "the reply was almost usable, ask once with the
faults quoted", never saw it. In the TESTOPS-90 measurement this was 3 of 10 real replies.

The reply is now read by `read_reply`, which classifies three shapes:

| shape | cause | second call? |
|---|---|---|
| JSON object, explanation, usable citations | `""` (Reply) | no |
| JSON object, explanation, citations missing or unusable | `repairable` | **yes, once** |
| not JSON, no explanation, or no prose | `malformed` / `empty` | no |

`parse_reply` keeps its two-value signature and now returns `repairable` as a cause, so every
existing caller still works. The fault quoted to the model is chosen by the shape, and the exact
string for the real failure is:

    you wrote the explanation but omitted the citations array - add one entry per sentence

`citations_repair_prompt` shows the model the whole original prompt, the explanation it already wrote,
and that exact fault, and asks only for the citations array — "write the explanation again exactly as
you wrote it" — so a citation repair cannot become a second attempt at the answer. Pinned:

- `test_a_reply_one_field_short_is_repairable_not_malformed` (4 params): explanation-only;
  `citations` as a string; `citations: []`; `citations` naming sentence 7 of a 3-sentence
  explanation. Each asserts the cause is `repairable`, not `malformed`, and pins the exact fault
  (`FAULT_OMITTED_CITATIONS`, `FAULT_CITATIONS_AS_STRING`, `FAULT_EMPTY_CITATIONS`,
  `FAULT_MISSING_SENTENCE`).
- `test_a_reply_that_forgot_its_citations_is_repaired_once_and_served`: fake model fails once, then
  succeeds. Exactly two calls; the second prompt contains the exact fault string **and** the previous
  explanation; ledger rows `error` (cause `repairable`) then `ok`; the explanation is stored and the
  page carries `agent-text`; the view is `fresh_repaired`.

The repair shares the one-round budget (`REPAIR_ROUNDS = 1`) with the violation repair: if a
citation repair comes back with a violation, the view is `rejected` and there is no third call.

## AC2 — not-JSON, or no explanation, stays malformed

`test_a_reply_with_nothing_to_repair_is_malformed_and_not_repaired` (3 params: non-JSON prose; a JSON
object with citations but no explanation; a 9-character explanation) asserts the fake model is called
**once**, the ledger says `error` / `malformed`, and nothing is stored. A second call in those cases
would be a guess, and no guess is bought.

## AC3 — measured, ten real cases, real model, before and after

Same ten cases and the same conditions as TESTOPS-90, so the two runs are comparable. Records read
from `data/testops.db` opened **read-only** (`?mode=ro`); ledger and cache in a throwaway store. Model
`deepseek-flash`, endpoint `https://<account>.services.ai.azure.com/openai/v1/chat/completions`,
token from the local `az login`, 8 s between cases (the endpoint throttles a burst). Script:
`factory/reports/2026-11-24/tes91_measure.py`; raw data including every model reply:
`factory/reports/2026-11-24/tes91-measurement.json`.

"Before" = the first reply parsed and passed the check. "After" = what the feature served, repair
included. Both are read off the same run.

| # | case (suffix) | first reply | state | before | after | tokens in | tokens out | wall ms |
|---|---|---|---|---|---|---|---|---|
| 1 | T123451-01 | repairable | fresh_repaired | no | yes | 3341 | 501 | 1922 |
| 2 | T123451-02 | repairable | fresh_repaired | no | yes | 3392 | 533 | 4313 |
| 3 | T123451-03 | usable | fresh | yes | yes | 1551 | 263 | 2546 |
| 4 | T123451-04 | usable | fresh | yes | yes | 1551 | 343 | 1469 |
| 5 | T123451-05 | usable | fresh | yes | yes | 1753 | 338 | 2047 |
| 6 | T114627-01 | usable | fresh | yes | yes | 1250 | 271 | 1500 |
| 7 | T114627-02 | usable | fresh | yes | yes | 1256 | 252 | 1421 |
| 8 | T114627-03 | usable | fresh | yes | yes | 1256 | 275 | 1969 |
| 9 | T114627-04 | usable | fresh | yes | yes | 1256 | 259 | 1297 |
| 10 | T114627-05 | usable | fresh | yes | yes | 1753 | 333 | 2047 |

| | before repair | after repair |
|---|---|---|
| accepted | **8 / 10 (80%)** | **10 / 10 (100%)** |
| 95% exact (Clopper–Pearson) | 44.4% – 97.5% | 69.2% – 100% |

- **Needed a repair:** 2 of 10, both the citation shape (no `citations` array). None needed a
  violation repair in this sample.
- **Repairs that succeeded:** 2 of 2. Both survivors are honest: they were checked from scratch after
  the repair, not waved through.
- **Token cost of a repaired explanation (two calls):** 3366.5 in / 517.0 out mean, against 1453.2 in
  / 291.8 out for a single-call explanation — i.e. the second call adds about **1913 input and 225
  output tokens** on such a case. Whole run: 18,359 in / 3,368 out.

**This is not a rate.** Ten cases cannot carry a percentage: the intervals overlap heavily (the two
flips would be p ≈ 0.5 on a two-sided sign test), so the run does **not** establish that repair
raises the true accept rate. What it does establish is mechanistic and was observed directly: two
replies that the old classifier discarded as `malformed`, and that therefore served a blank
explanation, were each served after exactly one repair call. The honest summary is "in ten real
calls, the two replies that previously produced nothing were repaired into explanations; the sample
is too small to quote a rate". The 30% seam in TESTOPS-90 was stochastic, so this run's 8/10 before is
itself a sample, not a baseline.

## AC4 — `fresh_repaired` is its own ledger state

A repair that lands returns `Outcome(state=STATE_FRESH_REPAIRED)`; `finish_view` writes that word into
`agent_view.served` exactly as it writes `fresh`. `STATE_FRESH_REPAIRED` is in `VIEW_STATES`, counts
as value (not cost) alongside `fresh` and `cached`, and is included in the variant's "explanations
shown" total.

The report page shows it two ways: a new **Accepted after repair** column in the variant table, and its
own row in "What each view actually was" (`fresh_repaired - an explanation a repair round made
acceptable`), which is where its calls and tokens are attributed. A repaired view also accepts a
feedback vote (the gate previously named only `fresh`/`cached`).

Pinned by `test_the_report_shows_a_repaired_explanation_as_its_own_state`: one view, two calls, tokens
360; `states["fresh"]["views"] == 0`, `states["fresh_repaired"]["views"] == 1`, `value` true,
`repaired_accepts == 1`, `explanation_views == 1`, and the page text carries both the column and the
label. `test_one_rejection_is_repaired_once_and_the_good_repair_is_served` was updated from `fresh` to
`fresh_repaired` — that is AC4 working, not a fudge: a violation repair that lands is also an
explanation the model had to be asked for twice.

## AC5 — no weakening

- The four TESTOPS-88 lies still reject (`test_each_of_the_reviewers_four_lies_is_rejected`, 4
  params), and the uncited sentence still rejects.
- The mask tests (TESTOPS-90) are untouched and green: a `claim:2405` id in prose is accepted, a plain
  "the number 7" beside it is still refused.
- `test_every_real_case_page_is_byte_identical_to_the_pre_change_build` compares 226 real case pages
  and 49 run pages against `fixtures/agent/off-golden.json`: unchanged.
- Full suite and `tests/contracts`: **1357 passed, 2 skipped**.
- A repaired reply is re-checked from scratch (`violations` runs after the repair), so the repair
  cannot make a lie countable, and a second failure falls back to the honest sentence.

## Limitations, stated plainly

- The repair round fixes *missing structure*, not a weak explanation. A reply whose prose is honest
  but thin is still served as it was; a reply with a fabricated count is still rejected after the
  repair.
- The measurement fired zero violation repairs, so this run says nothing new about that path's live
  yield; the TESTOPS-90 finding that a repair can double the spend and still fail stands.
- If the repair call itself returns another unusable reply, the view is `failed_unavailable` with
  cause `malformed` and no explanation is served; that path is pinned only with fakes here.

## Files

| file | change |
|---|---|
| `testops/judgement/agent.py` | `Reading`/`read_reply`, `_citations_fault`, the five exact faults, `citations_repair_prompt`, `parse_reply` kept as a two-value wrapper, `REPAIRABLE`, `STATE_FRESH_REPAIRED`, the citation branch in `explain_case`, report arithmetic |
| `testops/web/app.py` | "Accepted after repair" column + paragraph on `/agent-report`; feedback gate accepts `fresh_repaired` |
| `tests/test_agent_case.py` | 9 new pin cases (4 + 1 + 3 + 1) for AC1, AC2, AC4; one existing assertion updated `fresh` → `fresh_repaired` |
| `factory/reports/2026-11-24/tes91_measure.py` | the live measurement, before/after from one run |
| `factory/reports/2026-11-24/tes91-measurement.json` | the run's raw rows and every model reply |
