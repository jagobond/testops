# TESTOPS-4 review — 2026-11-21

## Verdict — PASS

The analyser now produces one claim per asserting step, classified by the step's own words, in
statements a developer can read and act on; all nine criteria hold on evidence I ran myself, with
only keyword-brittleness worth a follow-up ticket.

## Criteria

- AC1 HOLDS — my own three-asserting-step fixture produced three claims with `assertion_text`
  verbatim per step and `assertion_line` 5/6/7; `test_claim_per_assertion.py` covers the same.
- AC2 HOLDS — a Given/When/And-context feature yields zero claims (`CONTEXT_ONLY_TEXT` test); an
  `And` and a `But` after a `Then` both yielded claims in my probe.
- AC3 HOLDS — `test_classification_follows_step.py` proves both directions with deliberately
  contradictory titles, and asserts `classify_step(title)` disagrees with the claim, so the step
  genuinely wins.
- AC4 HOLDS — I grepped statement + label + action for `\b(I[1-4]|KP)\b` on my fixtures and the
  standard fixture: zero leaks, including the trap test where the step text itself contains "I4"
  and "KP".
- AC5 HOLDS — every verdict branch produces a distinct action naming the quoted step to change
  (move / rewrite to HTTP / rewrite the wording / bind / no-change); tests pin gap vs review.
- AC6 HOLDS — `sources_missing=[]` present on every claim even with no caller input; pipeline
  supplies jira/ado via `_missing_sources`, and the store refuses a v2 row without coordinates.
- AC7 HOLDS — store-level tests: two actionable claims → two cases, one finding each; an
  all-distinct run → zero cases, zero findings, empty `case_ids`. Verified directly below.
- AC8 HOLDS — two runs over identical fixtures returned identical (statement, verdict, line)
  tuples; statement text contains no timestamp or run id.
- AC9 HOLDS — 84 passed with the mandated stripped environment (7.7s); diff touches only
  `analysers/level_fitness.py`, `pipeline.py`, tests, fixtures and the review prompt; `web/`
  untouched.

## Readability

My own probe (fixture written for this review: basket/checkout feature, api + ui bindings):

- gap — "This test asserts that each fact's citation sits inside an element an assistive technology
  can name. Only a browser works that out, and this test only reads the responses the server sends
  instead, so nothing checks it." Action: move the step into a browser test or delete it.
- distinct (I2) — "This test asserts that the response status is not an error. This test only reads
  the responses the server sends, which settles that, so the assertion is checked."
- unplaced — "This step says "every basket line shows the price the store charged", which does not
  name data, a response, a page or anything a person sees, so nothing can be said about whether it
  is checked."

A developer who has never heard of TestOps could act on the first two without help: the statement
says what is asserted, what is missing, and the action names the exact step to move. The unplaced
statement is honest but its action ("say whether it is about the data, the response, the page, or
what a person sees") is the one place the internal ontology peeks through — still actionable, just
the weakest of the set. No machine output anywhere; no statement merely restates the assertion.

## Three sharpest concerns

1. Keyword-brittle classification: my natural business sentence "every basket line shows the price
   the store charged" lands `unplaced` because "price"/"shows" are not in CONTENT. Common-sense
   assertions will misroute to U until the vocabulary grows. Follow-up ticket, not a fix here.
2. The builder's mutation explanation is slightly wrong in a way that matters for the record: there
   is no "empty case deleted" for distinct claims — the RAISES filter removes them *before* case
   creation; the DELETE path is for suppressed claims. The property is nonetheless genuinely
   enforced (see below), so the verdict stands.
3. `_for_reader` deletes code tokens from step text before quoting it, so a step literally about
   "the I4 claim" is quoted in the statement with the token surgically removed — the statement
   paraphrases evidence it elsewhere presents verbatim. Cosmetic; the verbatim text is preserved in
   `assertion_text`.

## Uncaught-mutation check

I called `pipeline._emit` directly with a `distinct` claim against a fresh store: returned False
(refused), no finding row. Combined with the store-level test that an all-distinct run writes zero
cases and zero findings, the property "distinct raises no case and no finding" is genuinely
enforced at two independent points (the RAISES filter and _emit's guard), not merely unobserved.

## Fixture-edit check

`tests/test_level_fitness.py` now binds "the save button has an accessible name" as the Then step
over the api suite instead of asserting it only via the scenario title. The guarantee is unchanged
— a browser-needed claim asserted over HTTP is still a gap: the test still asserts
`verdict == "gap"`, `uses_browser is False`, `needs_browser is True`, and the evidence URI. It was
not loosened; it is stricter, because the gap now arises from the step's own words rather than the
title.

## Demo

- The problem: one claim per scenario, classified from title + concatenated steps, stated in codes.
- What changed: `classify_step`/`asserting_steps`/`_statement`/`_proposed_action` in
  `analysers/level_fitness.py`; per-claim cases and v2 claim rows with coordinates in
  `pipeline.py`; `sources_missing` plumbed from the caller.
- How we know it works: 84 tests pass in the stripped env; my own probe reproduced gap/distinct/
  unplaced statements readable end to end; determinism and code-leak checks clean.
- What it does not solve: keyword coverage for unseen phrasings (concern 1); the UI (TESTOPS-6).
- Where to look: `testops/analysers/level_fitness.py` (statements), `testops/pipeline.py`
  (`_fingerprint`, case loop), `tests/test_case_per_claim.py` (store-level proof).
