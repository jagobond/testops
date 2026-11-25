---
id: TESTOPS-36
title: Two analysers, one step, two pages that never mention each other
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-35
---

# TESTOPS-36 — Say how the two findings relate

## Finding (Product Owner)

> "case/rev-duplicate has the same issues as case-demo-product-levels-...-03 … are these the duplicate claims of each
> other? If not, then much more information is needed on both cases; if so, then this should be a single claim
> evidencing both tests."

The `rev-duplicate` case turned out to be a review fixture (TESTOPS-35), so the specific pair is not a pair. The
question underneath is real and will recur: the level-fitness analyser and the duplication analyser both examine
the same step, produce separate claims, and their pages give **different, competing instructions** —

- level fitness: "Rewrite this step to call the HTTP client instead of the browser."
- duplication: "Raise this with the team: keep one."

A reader who opens both cannot tell whether to rewrite the step or delete the copy, and nothing on either page
mentions that the other exists.

## Decision

Keep them as separate claims, and say so on the page. They are separate judgements with separate decisions: a
team may keep a duplicated pair and fix the level of one, or delete the duplicate and never touch its level.
Merging them into one case forces one decision over two independent questions, and the one-case-per-claim rule
exists precisely to keep decisions granular.

What is missing is the relationship, stated plainly on both pages.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Where another analyser raised a claim about the same asserting step in the same snapshot, each case page carries a short section: "Also reported by <analyser>: <one line>" with a link to that case. |
| AC2 | Where both findings apply, the page states the relationship in one sentence a reader can act on — for example: "This step is also reported as duplicating `<file:line>`; fixing the level here does not remove the duplication." Never two instructions with no link between them. |
| AC3 | The relationship is derived from stored claims (same `assertion_path`+`assertion_line`+`assertion_commit`), not from re-analysis at render time; a missing counterpart renders nothing rather than a guess. |
| AC4 | Cases with no counterpart are unchanged, byte for byte. |
| AC5 | A test builds a step reported by both analysers and asserts each page names the other, and that a step reported once still renders without the section. |
| AC6 | Verdicts unchanged. |

## Notes

- The section is a cross-reference, not a summary. It should be two lines at most; the reader came for one claim.
- If the relationship sentence ever needs more than one clause, that is a sign the two findings should be read
  together, and the design question returns — raise it rather than writing a paragraph.
