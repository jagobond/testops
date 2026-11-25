---
id: TESTOPS-28
title: Stop classifying the tail; keep the whole action and fix redundancy at the source
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-27
supersedes: TESTOPS-27
---

# TESTOPS-28 — Keep the whole action

## The decision

Two review passes tried to decide, from the words, whether a clause after the semicolon is a second
instruction or a restatement. First pass: 6 of 8 probes kept, 2 lost. Second pass, after morphology work:
94/94 real restatements still dropped correctly, but *"the duplicate is deletable"*, *"the second one can go"*
and *"the copy would be deleted by whoever owns it"* vanished from the page.

That is three leaks in three attempts at the same boundary, each one a different grammatical shape. The
conclusion is not that the word list needs another arm. It is that **a renderer cannot decide what a reader is
allowed to read.** A dropped clause is invisible; a kept clause is merely wordy. The asymmetry decides it.

So the classification is removed. `action_line` returns the whole action, rendered as sentences, always.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | `action_line` returns the full stored action, split into sentences for the page, with no clause removed. A property test over a corpus of hand-written actions (the reviewer's 15 probes included) asserts every content word of the input appears in the output. |
| AC2 | The instruction vocabulary, the continuation openers and `second_half_is_instruction` are deleted, not left dormant. `git grep` for those names returns nothing. |
| AC3 | The 94 real actions on `demo-product-levels-20261122T011316` render in full. Where the tail duplicates the argument, the page may look repetitive — that is the intended trade, and it must be visible in the report, not tidied away. |
| AC4 | If the T26 no-repeat lint fires on the real corpus once tails are kept, the analyser is at fault, not the renderer: record each firing in the report as a TESTOPS-28 finding for a follow-up ticket that rewrites the analyser's `proposed_action` strings. Do **not** silence the lint, and do **not** reintroduce a cut. |
| AC5 | The action box still reads as one instruction: sentence-splitting, capitalisation and full stops only. Two sentences are acceptable; a run-on is not. |
| AC6 | Verdicts unchanged: 94 claims, 90 distinct, 1 unplaced, 1 gap, 2 review. Suite green on both interpreters. |

## Notes

- This is the second time on this project that a rule built to tidy output has been more dangerous than the
  untidiness it prevented. The first was hedging a verdict with a familiar word. Both times the fix was to
  report what is stored and keep the judgement in one place.
- Redundancy belongs to the analyser that writes the action. A ticket for that belongs in F1's follow-up, not in
  the renderer.
