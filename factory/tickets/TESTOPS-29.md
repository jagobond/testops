---
id: TESTOPS-29
title: The analyser's action strings repeat the argument, and the reader now sees it
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-28
---

# TESTOPS-29 — One instruction, stated once

## Why

TESTOPS-28 stopped the renderer from cutting the action at a semicolon, because a dropped clause is invisible
and a kept clause is merely wordy. It is now visible:

> **What to do** — Rewrite this step to call the HTTP client instead of the browser. **The response decides
> everything the browser is being used for.**

The second sentence is the argument from the paragraph above, restated as if it were an instruction. The
renderer is doing the right thing; the analyser wrote two sentences when it had one instruction and one reason,
and the reason belongs in the argument, not in the action.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Every `proposed_action` the level-fitness analyser writes is one instruction and at most two sentences, containing no clause that restates the reason already stated in the claim statement. A corpus test over a real run enforces it. |
| AC2 | Where an action previously carried a trailing reason, the reason stays in the statement (section 1's argument) — the information is relocated, not deleted. A test asserts the reason's content words still appear on the page somewhere. |
| AC3 | The count of actions repeating content from their own block, reported by the TESTOPS-28 review, drops to zero; the review's own repetition count is the acceptance measure. |
| AC4 | Duplication-analyser actions follow the same rule ("…keep one." stays; a trailing restatement goes), and the T26 no-repeat lint passes over the whole corpus with no exemptions. |
| AC5 | Verdicts unchanged: 94/90/1/1/2. Suite green. |

## Notes

- This is the ticket the TESTOPS-28 reviewer's repetition count sizes. If that count is large, the rewrite is a
  vocabulary job on `level_fitness.py` and should be done in one pass, not per-case.
- The rule for a new action string: state the change, not the reason for it. The reason is already one paragraph
  above, and a reader who wants it can look up.
