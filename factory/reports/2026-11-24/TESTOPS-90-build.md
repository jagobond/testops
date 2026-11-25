# TESTOPS-90 build — a citation id is not a statistic, and a rejection gets one repair

2026-11-24, branch `factory/testops-90-citation-id`, worktree
`C:/Users/<name>/Projects/testops-t90`.

Suite, from the project `.venv` with `PYTHONPATH`/`PYTHONHOME`/`VIRTUAL_ENV`/`CONDA_PREFIX` stripped
and `PYTHONNOUSERSITE=1`: **1338 passed, 2 skipped** (273 s). `tests/contracts` ran inside that
number and is green. No test reaches the network.

`testops/judgement/client.py` was **not touched**, so TESTOPS-89's work on the same file merges
without a conflict. The only product files changed are `testops/judgement/agent.py` (the mask, the
prompt, the repair round, one `Outcome` field) and one paragraph of `/agent-report`'s wording in
`testops/web/app.py`.

## AC1 — a number inside a citation id is not a fact

`violations` masks `claim:<id>` and `reason:<id>` out of a sentence before the number scan
(`_CITATION_ID`), so the digits in an identifier are never read as a measurement. The exact sentence
from the rejected reply is pinned in `test_a_citation_id_written_in_the_prose_is_not_a_statistic`,
against a record whose claim is 2405:

    The record does not contain the defect's origin, and claim:2405 is the claim whose record that
    gap concerns.

- before: `['the number 2405, which no cited fact holds']`
- after: `[]`
- and re-checked against the **real** record of `case-demo-booking-levels-20261124T123451-05` in the
  product store: `[]`. The old scan read `[('2405', 2405)]` from that sentence.

The mask is the identifier, not the sentence: `the number 7` beside a valid `claim:2405` citation
still yields `['the number 7, which no cited fact holds']` (pinned). `reason:<id>` is pinned the same
way. The four TESTOPS-88 lies and the uncited sentence are untouched and still reject.

## AC2 — the prompt says ids belong in the citations array

`SYSTEM_PROMPT` now says, under the first absolute rule: *"The identifiers belong in the "citations"
array and nowhere else: never write one in the explanation's prose."* `PROMPT_VERSION` moved
`explain-a-case/2` → `explain-a-case/3`, and a test pins both facts plus that the version is part of
the cache key (the same record hashes differently under the old version).

## AC3 — one repair round

On a violation, `explain_case` records the rejected attempt, then asks once more with
`repair_prompt`: the model is shown the exact violations and its own previous reply, and told to
change only the sentences those violations name. The repaired reply is checked from scratch against
the same rules. A second rejection falls back to the honest sentence and the view is recorded
`rejected`. Pinned by:

- `test_one_rejection_is_repaired_once_and_the_good_repair_is_served` — fake fails once, then
  succeeds: two ledger rows (`rejected`, `ok`), repair prompt contains `the verb PATCH`, the
  explanation is stored and the view is `fresh`.
- `test_a_second_rejection_falls_back_to_the_honest_sentence_with_state_rejected` — fake fails twice:
  exactly two calls, both rows `rejected`, view `rejected`, nothing stored, one honest sentence on
  the page.

Both calls are in the ledger (one row per call, as before). The view links to the call it closed on,
so the first attempt shows as an unlinked call in the variant total — the report paragraph now names
that case ("a first attempt that a repair round replaced"). One existing arithmetic test was updated
for it: `test_the_report_separates_every_state_so_value_and_loss_are_not_confused` now asserts
`unlinked_calls == 1, unlinked_tokens == 180, total_tokens == 540` where it asserted `0 / 0 / 360`.

## AC4 — measured, ten real cases, real model

Ten cases from the stored level-fitness runs of 2026-11-24 (five from `...T123451`, five from
`...T114627`, including `...T123451-05`, the ticket's case). Records read from `data/testops.db`
opened **read-only**; ledger and cache in a throwaway store. Model `deepseek-flash`, endpoint
`https://<account>.services.ai.azure.com/openai/v1/chat/completions`, token from the local
`az login`. Script: `factory/reports/2026-11-24/tes90_measure.py`; raw data, including every
model reply: `factory/reports/2026-11-24/tes90-measurement.json`.

| # | case (suffix) | state | tokens in | tokens out | wall ms | reason |
|---|---|---|---|---|---|---|
| 1 | T123451-01 | failed_unavailable | 1537 | 176 | 4077 | malformed |
| 2 | T123451-02 | fresh | 1551 | 327 | 4250 | served |
| 3 | T123451-03 | failed_unavailable | 1551 | 190 | 2608 | malformed |
| 4 | T123451-04 | failed_unavailable | 1551 | 185 | 2390 | malformed |
| 5 | T123451-05 | fresh | 1753 | 258 | 3359 | served (the ticket's case) |
| 6 | T114627-01 | fresh | 1250 | 274 | 3219 | served |
| 7 | T114627-02 | fresh | 1256 | 253 | 2000 | served |
| 8 | T114627-03 | fresh | 1256 | 294 | 2405 | served |
| 9 | T114627-04 | fresh | 1256 | 244 | 1844 | served |
| 10 | T114627-05 | fresh | 1753 | 332 | 5687 | served |

**Accept rate: 7 of 10 (70%).** Mean tokens per case **1471.4 in / 253.3 out**; mean wall time
**3.18 s**; totals 14,714 in / 2,533 out over 31.8 s.

The three failures are **not** the citation-id bug and not a rejection by `violations`: in each case
the model returned well-formed JSON with an `explanation` but **no `citations` array at all**, so
`parse_reply` classified it `malformed`. That is a different seam: a missing `citations` key is not a
violation with a sentence to quote, so the repair round does not apply to it. It is worth a ticket of
its own (an explanation-only reply could either be repaired or refused as `malformed`), and it is the
remaining reason the feature serves nothing on 3 in 10 cases.

Two other measured facts, both honest caveats on the number above:

- An immediately repeated run (no pause between calls) hit the endpoint's throttle: **8 of its 10**
  calls returned `http_429` and only 2 were served. The table above is the run with the calls spaced
  (8 s), which is how a reader arrives at them. A burst is not a valid way to ask this model.
- The repair round was **never exercised live** in this sample: all seven failures across runs were
  `malformed` or `http_429`, never a violation. Its behaviour is pinned by the two fakes, not by this
  measurement, and that is stated so the number is not read as proof of it.

### Cost model

    cost = tokens_in x price_in + tokens_out x price_out

The tool measures tokens and prints no currency. No price is read or recorded by this build.

    ASSUMPTION: price_in  = $0.14 per 1M input tokens   (unverified; TESTOPS-88's placeholder)
    ASSUMPTION: price_out = $0.28 per 1M output tokens  (unverified; TESTOPS-88's placeholder)

With those assumptions: this ten-case run cost about **$0.0028**, i.e. **$0.00028 per case** and
**$0.0004 per accepted explanation**. Replace the two prices with the Azure Foundry list price for the
deployed model before quoting money to anyone.

## AC5 — nothing weakened

- The four TESTOPS-88 lies still reject, with the same violations (`the verb PATCH`, `the line 99`,
  `the number four`, `the sentence 1, which cites nothing`).
- The uncited sentence still rejects.
- `agent=off` is byte-identical: the golden-digest test over 226 case pages and 49 run pages re-ran
  green, 0 mismatched.
- Full suite 1338 passed, 2 skipped; contracts included.

## Files

| file | change |
|---|---|
| `testops/judgement/agent.py` | `_CITATION_ID` mask in the number scan; prompt rule + `PROMPT_VERSION` 3; `repair_prompt` and one repair round in `explain_case`; `Outcome.repairs` |
| `testops/web/app.py` | `/agent-report`: the unlinked-calls sentence also names a replaced first attempt |
| `tests/test_agent_case.py` | 6 new tests (AC1 ×3, AC2, AC3 ×2); one ledger-arithmetic expectation updated for the repair call |
| `factory/reports/2026-11-24/tes90_measure.py` | the measurement, reproducible |
| `factory/reports/2026-11-24/tes90-measurement.json` | the ten-case result, raw replies included |
