---
id: TESTOPS-10
title: Classification coverage — half the real corpus is unclassifiable
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-4
---

# TESTOPS-10 — Classification coverage

## Why

TESTOPS-4 shipped per-assertion claims. Run against the real CotW repository pair, the analyser
produced 94 claims from 41 scenarios:

| verdict | count |
|---|---|
| distinct | 43 |
| unplaced | 48 |
| review | 2 |
| gap | 1 |

**48 of 94 — 51% — are `unplaced`**, meaning the tool can say nothing about them. That is not a
rounding problem; it is the tool declining to work on half of the specimen. Until this is fixed, the
case page can only ever be half-useful, and any coverage or level report built on top of it will
understate what is actually wrong.

The cause is a keyword vocabulary applied to assertion text. A reviewer's probe already predicted
this: "every basket line shows the price the store charged" lands `unplaced` because "price" and
"shows" are not in the content vocabulary.

The unplaced claims are not vague. Real examples from the run:

- "there is one sheet per entity"
- "the sheet for \"Keegan\" shows every proposed fact for \"Keegan\""
- "each of those facts records review mode \"batch\""
- "admission is refused with an error naming the missing approver"
- "that fingerprint is not the claim text itself"
- "the audit reports that fact, named by its fact id"
- "the Tier 1 fact is refused for the missing approver"
- "no finding names the unapproved proposal"

A person classifies every one of these without hesitation. The analyser must too.

## What "fixed" means, numerically

The target is measured on the real run, not on fixtures:

1. **`unplaced` falls to 10 or fewer** of the ~94 claims (≤10%), and
2. **no more than 3 new `gap` verdicts appear** — broadening the vocabulary must not manufacture
   accusations, which is the failure mode that killed the v0.1 analyser (precision 0.118), and
3. **a hand-labelled sample of 20 assertions agrees at 85% or better**, with the builder recording
   its own labels before running the analyser.

If the target cannot be met, say so plainly with the funnel (how many of the 48 were reclassified,
how many stayed unplaced and why). Do not tune until the number looks acceptable; a
recorded miss is more useful than a tuned pass.

## Mechanism is yours, but the evidence is constrained

Words alone cannot carry this. Consider what is already available and currently unused:

- the assertion's matched **step binding** and its layer (a step that drives a browser is evidence
  about the instrument, not the intent)
- the **step definition's body** — whether it calls an HTTP client, a browser driver or the store
- the **scenario's other assertions** as context (not as a substitute: TESTOPS-4 forbids the title
  deciding the verdict, and the same reasoning applies here)

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The real CotW run has ≤10 `unplaced` claims out of ≥90, measured by re-running the analyser over the same snapshot, not by assertion. |
| AC2 | The run produces ≤3 more `gap` verdicts than the baseline (baseline: 1). Broadening may not invent findings. |
| AC3 | A hand-labelled sample of 20 real assertions — recorded in the repo as a fixture with the expected interaction for each — agrees with the analyser at ≥85%. |
| AC4 | Every reclassified claim names, in `established_by`, the rule that classified it, so a reader can see why. |
| AC5 | Statements and proposed actions keep the readability TESTOPS-4 achieved: no codes, no machine phrasing, action naming the step. A test asserts this on the newly classified claims. |
| AC6 | Classification remains deterministic: same snapshot, same claims (AC8 of TESTOPS-4 still holds). |
| AC7 | No regression in the existing 84 tests. |
| AC8 | The measured numbers — unplaced before and after, gap before and after, sample agreement — appear in the build report, unrounded. |

## Notes

- The baseline run id is `cotw-levels-20261121T215534`. Its claims are in the store; use them as the
  `before` side rather than re-deriving from memory.
- Do not widen `NEEDS_BROWSER` to reduce `unplaced`. If a claim needs a browser, it needs one; the
  cheap way to shrink the number is to call everything a browser claim, and that would turn a
  coverage problem into a false-accusation problem.
- The `U` ("not identifiable") verdict may still be right for a handful — "that count is correct for
  the store it was run against" is genuinely ambiguous. The target allows ten.
