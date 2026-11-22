---
id: TESTOPS-27
title: The action line drops anything after a semicolon, and trusts that it was redundant
feature: F1
status: superseded
autonomy: build
depends_on: TESTOPS-26
---

# TESTOPS-27 — Do not silently drop half an instruction

## Finding (reviewer, TESTOPS-23/26)

> "`action_line` is lossy by design. It keeps only the clause before the first "; ". Today every stored tail is a
> restatement, so the cut is right — but if an analyser ever writes two instructions in one action string, the
> second is dropped without a trace."

The page shows the action, and the action is the thing a reader acts on. Truncating it silently is the one
failure this product cannot afford: the reader believes they have the whole instruction.

Second, smaller: "The test asserts Then each fact's …" — the Gherkin keyword reads as a second verb. The
reviewer re-read that sentence in all four verdicts.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The tail after the first "; " is kept when it carries an instruction, and dropped only when it restates: decide by a stated rule (for example, keep the tail if it contains an imperative verb whose object is not already in the head), not by assumption. |
| AC2 | When the tail is dropped, a test proves it was a restatement — the assertion names the two strings and shows the overlap — so a future analyser cannot lose an instruction quietly. |
| AC3 | When the tail is kept, the action renders as two sentences or two clauses, not as a run-on; a test covers both shapes. |
| AC4 | A corpus test over a real run asserts no action is truncated to fewer than 40 characters unless the whole action was shorter. |
| AC5 | The assertion sentence names the Gherkin keyword as a keyword: "The test asserts the step `Then …`" or an em-dash before the quote, consistently across all four verdicts. |
| AC6 | Verdicts unchanged: 94/90/1/1/2. Suite green on both interpreters. |

## Notes

- The rule in AC1 must be written down in the code where it is applied, so the next person can disagree with it
  on the evidence rather than by guessing.

## Addendum — the reviewer's probes found the hole this ticket exists to close

The reviewer ran eight smuggling probes. Six tails survived; two vanished:

| probe | result |
|---|---|
| `…; this should be split into two steps and the second deleted` | KEPT |
| `…; move it and rename it` | KEPT |
| `…; one copy to keep` | KEPT — fails open |
| `…; keep it if the page does not need it` | KEPT |
| `…; you should delete the second one` | KEPT — fails open |
| `…; instead, delete the duplicate` | KEPT — fails open |
| **`…; the second copy should be deleted`** | **DROPPED — a passive-voice order, silently lost** |
| **`…; it is worth keeping one copy`** | **DROPPED — an inflected verb evades the stem list** |

Both losses are morphology, not structure: the rule matches bare stems, so *deleted*, *keeping*,
*removing*, *merged* walk past it. That is precisely the failure this ticket exists to prevent, so the
ticket is not done until it passes its own probes.

| id | criterion |
|----|-----------|
| AC7 | The eight probes above are tests, and every one is kept. Matching handles inflected forms (stems plus `-s`, `-ed`, `-ing`, `-es`, and irregulars the vocabulary actually contains) and passive constructions (`should be deleted`, `needs deleting`, `must be removed`, `worth keeping`) as instructions. |
| AC8 | A tail is dropped only when the drop is proved: the clause opens with a word whose subject is the head clause AND contains no verb from the instruction vocabulary in any inflection, AND no modal or passive marker. The proof is in the test, not in the comment. |
| AC9 | The 94 real tails that currently drop still drop — the fix must not turn every tail into a kept clause, or the corpus becomes noisy and the reader stops reading the second sentence. Report the before/after counts. |

## Superseded

See TESTOPS-28. Two review passes leaked three orders between them; the classification is removed and the
whole action is kept. The evidence is in `factory/reports/2026-11-22/TESTOPS-27-review.md` and
`TESTOPS-27-review-2.md`.
