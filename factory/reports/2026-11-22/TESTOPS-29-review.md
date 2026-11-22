# TESTOPS-29 review — 2026-11-22

Reviewer: independent re-measurement over the pinned run `cotw-levels-20261122T011316` (94 claims,
snapshot `cotw-levels-20261122-a3f19853-r6`), suite run stripped per AGENTS.md.

## Verdict — PASS

The build did exactly what the ticket asked by its own acceptance measure: the analyser's actions are
now instructions, the review's repetition count is 0 of 94 by my own re-implementation of the
measure, nothing was deleted to win, the lint still bites, and the verdicts are unchanged.

## Criteria

- **AC1 HOLDS.** All 94 rebuilt actions are one instruction of one sentence (the distinct action's
  fold-in keeps it at one). My within-action measure found 0 actions carrying more than two
  sentences and 0 sharing a content word between their own sentences.
- **AC2 HOLDS.** For both review-verdict claims, section 1 as rendered still reads "the page the
  server sends settles it, and the test drives a browser to read it" — "browser" and "settles" both
  on the page, verified by rendering the argument block myself. Spot-checked five more rebuilt
  claims (3 distinct, 1 unplaced, 1 gap): every content word of each new action appears on the
  page — nothing moved out of existence.
- **AC3 HOLDS.** Measured myself (see Repetition): 2 of 94 before, 0 of 94 after, matching the
  build's number. My stricter action-vs-statement cross-check gives 8 → 5 of 94; all five
  survivors share only an instrument word the instruction needs ("browser" — you cannot say "call
  the HTTP client instead of it" without naming it) or the functional word "step". No restatement.
- **AC4 HOLDS.** Duplication actions are `Raise this with the team: keep one.` in both branches of
  `_claim`; the restated clause is gone and "keep one" survives. The T26 lint still bites: I seeded
  a repeated 6-word clause into `repeated_clause` and it returned the clause; clean text returns
  None. The corpus tests run it over all 94 pages unexempted.
- **AC5 HOLDS.** Suite green: 337 passed in 78s, stripped environment. Rebuild prints
  `{'distinct': 90, 'unplaced': 1, 'gap': 1, 'review': 2}` = 94/90/1/1/2.

## Repetition — what I measured and how

I did not trust the build's script; I wrote my own. For each of the 94 claims I took the action as
the page writes it (quoted step referred to as "this step", the substitution TESTOPS-28's review
used so the quoted step's words are not charged to the action's prose), split at sentence ends and
semicolons, and counted actions whose first sentence shares a stopword-free content word with the
rest. Result: **before (stored 0.10.1 rows) 2 of 94** — both review claims, repeating "browser";
**after (rebuilt by the working tree) 0 of 94**. Without the step-substitution the within-action
count is 0 both ways (the substitution matters only for the old long actions). I also measured
action-vs-own-statement overlap directly: 8 of 94 before, 5 of 94 after, all five survivors
instrument-naming, not restating. The build's claim of zero is verified.

## Before and after — three actions

1. **review** — before: `Rewrite this step to call the HTTP client instead of the browser; the
   response decides everything the browser is being used for.` / after: `Rewrite this step to call
   the HTTP client instead of the browser.` The instruction survived; the tail was the argument,
   and it is still in section 1 ("the page the server sends settles it").
2. **gap** — before: `…into a test that drives a browser, or delete it; at this level nothing
   establishes what it asserts.` / after: `…into a test that drives a browser, or delete it.`
   Instruction survived; the reason is on the page ("nothing short of a browser settles it").
3. **unplaced** — before: `…then re-run; a judgement with no comparison in it cannot be checked at
   any level.` / after: `…to say what it is compared with - the value, the row or the report it
   should agree with - then re-run.` Instruction survived and got more specific, not less.

The distinct action (`No change: keep this step at the cheapest level that establishes it.`) is the
argued exception: one sentence, the "cheapest level" fact folded in as a disposition because it
appears nowhere else on the page. I checked a rendered distinct claim — "cheapest" is indeed in the
action alone. The fold-in is legitimate under AC2; the Lead may still want to overturn it at the
ticket, as the build report itself flags.

## Three sharpest concerns

1. **The duplication action is now terse to the point of anonymity.** `Raise this with the team:
   keep one.` names no copy, no file, no level. The statement one line above names both, so nothing
   was lost, but a reader who exports the action field alone gets a sentence that could attach to
   any of the 18 duplication claims. If the action is meant to be acted on in isolation, this went
   one word too far.
2. **The distinct exception is a policy decision embedded in an action string.** "At the cheapest
   level that establishes it" is a reason-shaped clause living in an action, exempted by argument
   rather than by rule. It is defensible (the fact exists nowhere else), but it means AC1's "no
   clause that restates the reason" now has a hand-maintained exception, and the next analyser
   author will cite it as precedent.
3. **The corpus renderer tests still pin the old run's stored rows.** That is deliberate and argued
   (they are the only evidence the renderer keeps legacy two-clause actions whole), but it means
   the store must retain `cotw-levels-20261122T011316` indefinitely; a future prune of old runs
   will silently weaken those tests rather than fail them.
