# TESTOPS-31 review — 2026-11-22

Reviewer: reviewer agent. Suite: 357 passed in 57.40s (per the mandated env-stripped command). All
probes below were run against the working tree by this reviewer, not taken from the build report.

## Verdict — PASS

The signature now carries tables, doc strings and Examples rows so the false positive the Product
Owner found is gone, the claim states its rows in checkable words, a genuinely identical pair still
yields a duplicate, and the corpus counts did not move; every probe I designed to break it behaved
as the ticket requires.

## Criteria

- AC1 — HOLDS. Probe: two scenarios with step tables differing by one row → 0 claims;
  Examples-only-differing outlines → 0 claims; doc strings pinned by the new tests. The corpus
  re-run reports exactly the QuestionSuggestions pair resolved (18 → 17 claims).
- AC2 — HOLDS. The resolved scenario's rendered assertion is
  `the suggestions list should be: What is Reqnroll?, Question 2, Question 3` (verified by rendering
  `Step.assertion_text` from the corpus fixture, line 29). No claim text ends at "should be"; the
  table is in the sentence, not behind a count. Pinned by two tests including a corpus-wide guard.
- AC3 — HOLDS. Before 18 / after 17, one pair resolved, the build report names the differing rows
  (`:8` vs `:29`: Given 2 rows vs 3×3; Then 1 row vs 3 rows). I re-ran the corpus myself and got 17.
- AC4 — HOLDS. Probe: two genuinely identical scenarios (same words, same table) → 1 duplicate
  claim with the data quoted. The exact PO pair yields 0. Both directions pinned by tests. Silence
  cannot satisfy the guarantee.
- AC5 — HOLDS. `test_an_older_run_keeps_its_stored_text` passes; version moved 2.1.0 → 2.2.0, no
  rewrite path touches stored claims.
- AC6 — HOLDS. `test_the_corpus_still_carries_the_verdicts_the_ticket_pins` passes: 90 distinct,
  1 unplaced, 1 gap, 2 review (= 94).

## Table probes — each pair I built, its tables, what the analyser said

| probe | tables | result |
|---|---|---|
| 3 identical scenarios, same 1-row table (`title: What is Reqnroll?`) | identical | 2 claims — both copies called duplicates, assertion quoted with the row |
| 2 scenarios, tables differ by ONE row (`Question 2` vs `Question 3`) | 1-col, 3 rows vs 3 rows | 0 claims — not duplicates |
| 2 scenarios, same rows in different ORDER (`Reqnroll?, Question 2` vs `Question 2, Reqnroll?`) | 1-col | 0 claims — NOT reported. See below. |
| 2 outlines, Examples differ (`| a |` rows 1,2 vs 1,3), step text identical | Examples only | 0 claims — distinguished |
| 2 outlines, Examples differ by one digit (`12` vs `3`) | Examples only | 0 claims — digits are no longer parameterised |
| 2 scenarios, step text differs by a digit (`Given 12 questions` vs `Given 3 questions`), same table | step text | 0 claims — digit in step words also distinguishes |

## The resolved claim — quoted text as rendered

From the corpus (QuestionSuggestions.feature, scenario at line 29):

    detail.assertion_text: the suggestions list should be: What is Reqnroll?, Question 2, Question 3

And the duplicate-style statement a reader now gets for a true repeat, so the claim is checkable on
both sides of the fix:

    The scenario "B" at probe.feature:9 asserts "the suggestions list should be: What is Reqnroll?",
    which probe.feature:4 already asserts at an unidentified level.

A reader sees the rows. The multi-column render (`votes: 0; asked at: now; asked by: Marvin`) keeps
column names so values stay labelled.

## False negatives — did the fix go too far?

No new false positives were observed and the corpus lost exactly one claim, so the fix was
proportionate. The residual false-negative surface is:

1. Row order is significant. Two scenarios whose tables are permutations of each other are now
   silent. Defensible for the motivating case (a "suggestions list should be in this order" table
   is genuinely order-sensitive; asserting a list implies asserting its order), and it errs in the
   safe direction — silence never fabricates a duplicate. But it is a silent miss for set-like
   tables and nothing in the code says that was a choice. A one-line note in the `signature_part`
   or `render_table` docstring would make it defensible instead of accidental. Not blocking.
2. Cell normalisation strips punctuation, so two tables differing only in punctuation normalise to
   the same signature — the same tolerance step wording already has, and declared in the build
   report's residual. Acceptable.
3. Doc strings delimited with backtick fences (which Gherkin also allows) are not read — only `"""`
   is. A pair differing only in a backtick-fenced doc string would still be called a duplicate.
   Narrow, and the ticket's wording named doc strings generally; worth a follow-up ticket, not a
   NEEDS-FIX.

## Three sharpest concerns

1. Row-order significance is undocumented (above). If a later reviewer assumes "rows are a set",
   they will "fix" the signature and reintroduce false positives. Record the decision where the
   signature is built.
2. Backtick-fenced doc strings fall through to the generic branch and are silently dropped, so the
   TESTOPS-31 false positive survives in that one syntactic corner. Same class of bug, different
   fence — worth a small follow-up ticket rather than stretching this one.
3. `web/app.py` now matches when the stored text merely *starts with* the file line. That is right
   for tables, but it also swallows a stored text that has drifted from the file (a file edited
   after the run would still quote as matched). Cheap to tighten later by comparing only the words
   before the first `:`; not a defect today because AC5 only demands old runs keep their stored
   text, which they do.
