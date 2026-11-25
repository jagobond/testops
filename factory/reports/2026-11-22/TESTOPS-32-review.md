# TESTOPS-32 review — 2026-11-22

Reviewer's verification against the real store (`data/testops.db` copied read-write to a scratch
home; the product tree was never touched). Full suite: 353 passed, 7 skipped; 29 more passed for
the duplication corpus arms (`test_duplication_v2.py`, `test_duplication_tables.py`,
`test_duplicate_counterpart.py`).

## Verdict — PASS. The duplicate page for the ticket's own case now shows exactly the copy the claim names, at the right scenario, with the right lines marked, and every lie I tried produced the sentence the ticket asks for instead of a blank or a wrong scenario.

## Criteria

- **AC1 — HOLDS.** Rendered `case-demo-service-dup-20261122T115216-18`: section 3, "The copy this
  claim names", opens with `QuestionSuggestions.feature:17`, names the scenario, shows its steps
  verbatim, and renders "The step definition that runs the copy's step there:". Order on the page:
  1 asserted / 2 step / **3 copy** / 4 context / 5 unchecked / 6 decision.
- **AC2 — HOLDS.** The copy's excerpt carries its data: the Given table (`What is Reqnroll?`,
  `What is Cucumber?`), the When table (`<asked question>`), the Then table and the outline's
  four Examples rows. Nothing is elided.
- **AC3 — HOLDS.** The counterpart is resolved from `established_by`'s recorded `file:line` and
  the stored blob at the claim's own snapshot — I patched `established_by` to a path the snapshot
  does hold and a line it does not, and the page still resolved honestly (probe 2 below). No
  corpus re-parse at read time.
- **AC4 — HOLDS.** Both sections present, copy first (`html.index` check, and on the live page).
  A distinct-verdict case (`case-demo-product-levels-20261121T165925`) rendered under the old branch
  (`factory/testops-31-tables`) and the new tree is **byte-identical**.
- **AC5 — HOLDS.** `tests/test_duplicate_counterpart.py` renders a real corpus run and asserts the
  copy's file:line, its row inside the copy's own figure, the marked line, and the copy-before-context
  order. 3 tests, all pass.
- **AC6 — HOLDS.** Level fitness re-run `demo-product-levels-20261122T120603`: 94 claims = 90 distinct /
  1 gap / 2 review / 1 unplaced — exactly 94/90/1/1/2. Duplication on demo-service is pinned at
  17 claims / 17 cases / 17 findings by the TESTOPS-31 corpus tests, which still pass; the 18-claim
  run in the store is the pre-31 run this ticket was raised against, untouched.

## Is it the right scenario — how I checked, what you found

I opened the store, took the claim the ticket names (`id` 1959, `QuestionSuggestions.feature:17`
in `established_by`), and rendered the counterpart the new read model produces against the stored
blob. The copy shown is the **Scenario Outline "There is a question with common words of the one
being asked"** starting at line 8 — the outline whose `Then` sits at line 17. The claim's own
assertion is at line 39, in the scenario starting at line 29; that scenario is nowhere in the copy
section. So the page shows the neighbouring (earlier) scenario the claim really names, not the
claim's own, not the one after.

Marking: inside the copy's excerpt, line 17 is the only marked line, and it is the asserting step
(`Then the suggestions list should be`) — the step analogous to the claim's own assertion — with
its table following unmarked. The step definition block marks line 22 of
`QuestionSuggestionsStepDefinitions.cs`, which is `[Then("the suggestions list should be")]` — the
attribute binding that step — and the body ends at the blank line after the method. Both marks are
the truth, not the nearest line.

## Lies attempted

1. **Missing blob.** Deleted the counterpart's feature-file blob from a scratch copy of the store.
   Counterpart state became `not_stored`; the page rendered "The source was recorded but its
   content is not in this store: `QuestionSuggestions.feature:17`." No blank, no crash.
2. **Line past the end.** Pointed `established_by` at a file that exists in the same snapshot
   (`Authentication.feature`, 10 lines) with line 99999. State `past_end`; the page rendered "The
   source was recorded at `...:99999`, but the stored file holds only 10 lines, so there is nothing
   at that line to show." The recorded coordinates are named on the page, so the reader can see the
   claim's own words.
3. **Non-duplicate regression.** Rendered a distinct-verdict case under both the old branch and the
   new tree: byte-identical, so no page gains the copy section that should not have one.

## Three sharpest concerns

1. **A duplicate whose `established_by` does not parse renders nothing at all.**
   `counterpart_coordinates` is a regex over today's rule's wording; a duplicate claim that names
   its copy in any other shape gets no copy section *and no sentence saying a copy was named* —
   the one case where the page silently withholds the evidence again. The "not recorded" state
   exists for v1 rows but is unreachable for a v2 duplicate with an unparseable string.
2. **The copy's commit is borrowed from the claim's own `assertion_commit`.** `established_by`
   records no commit, so the counterpart renders from the claim's commit. True for every duplicate
   produced today (both sides come from one snapshot), but it is an assumption the analyser could
   silently break by comparing across revisions; nothing in the store would catch it.
3. **Branch ancestry.** This branch predates the Lead's later commits on the primary tree, so the
   range diff shows `TESTOPS-31-review.md` and `review-TESTOPS-32.txt` as deletions. No commit here
   removed them; merge rather than force-push and they come back. Not a build defect, but merge
   carelessness would destroy review history.
