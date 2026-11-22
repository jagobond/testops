---
id: TESTOPS-47
title: Each analyser states the cover of its own decision, and states identity rather than promising an event
feature: F2
status: ready
autonomy: build
depends_on: TESTOPS-40
---

# TESTOPS-47 — One sentence cannot describe two analysers

## Finding (TESTOPS-40 review)

TESTOPS-40 added one sentence describing what a decision covers. It is right for the level-fitness analyser and wrong
in two ways:

1. **It promises an event it cannot guarantee.** "adding or removing an identical assertion in it, asks you again" —
   delete one identical assertion and add another in the same edit, and the count is unchanged, the keys are identical,
   the decision holds silently, and the page has promised otherwise. The truthful contract is the *tuple*
   (scenario, interaction, words, count of identical assertions). A page should state the identity, not predict a
   re-ask.
2. **It is wrong for duplication cases.** A duplication decision's identity is `duplicate|scenario-name|signature` —
   nothing to do with "one assertion… same interaction and the same words". The sentence appears on every case with a
   finding, so on duplication pages the reader is told a contract that is not the one they are entering.
3. **An older decision can quietly resume cover after twin churn** — decide the lone assertion, add a twin (asked
   again, correctly), delete the twin, and the survivor's key is again the lone key, so the original decision covers it
   with no new case. Over identical words in the same scenario, so low risk, but "asks you again" is not guaranteed.

## Decision taken here (Lead's call)

**The analyser that raises a claim declares its own cover**, in the same place it declares its verdict and its action.
The page renders that analyser's sentence. One global sentence cannot describe two different identities, and the next
analyser would make it three.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Each registered analyser declares a cover sentence; the page renders the declaring analyser's sentence and never another's. A duplication case shows a duplication contract; a level-fitness case shows the level-fitness one. |
| AC2 | The level-fitness sentence states the **identity** (scenario, interaction, words, and that a count of identical assertions is part of it) rather than promising "asks you again". Test: the net-zero twin edit must leave the page's claim TRUE, because the claim is now about identity, not about events. |
| AC3 | The duplication sentence states its own identity (`scenario + signature`) and what does and does not disturb it. |
| AC4 | Concern 3 is stated wherever the reader would rely on it: a decision recorded before a twin was added can cover again after the twin is removed. Either surface it on the page or make the key carry enough history to prevent it — say which, and why. |
| AC5 | A test asserts every registered analyser has a cover sentence, so a new analyser cannot inherit another's wording by default. |
| AC6 | Goldens: whichever pages change, the diff contains only the sentence (verify programmatically, as TESTOPS-40's review did). Counts unchanged: CotW 94/90/1/1/2, ReqOverflow 17/17. |

## Notes

- AC5 is the point of the ticket: the failure was a default, not a mistake. Make the default impossible.
- Keep the sentences short. Two analysers × 40 words is already a lot of prose on a page.
