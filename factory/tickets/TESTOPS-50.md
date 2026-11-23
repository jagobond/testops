---
id: TESTOPS-50
title: Two numbers in the inventory cannot be reproduced, and the document's selling point is its numbers
feature: F2
status: ready
autonomy: build
depends_on: TESTOPS-42A
---

# TESTOPS-50 — A count nobody can derive is worse than an estimate

## Finding (TESTOPS-42A review, concern 1)

Five headline counts in `docs/ecosystem-inventory-cucumber-js.md` were independently confirmed by the reviewer's own
scanner. Three items in §2 and §5 were not:

1. **"steps that match a declared pattern: 46 of 76"** — the reviewer gets 38 with `{int}` = `\d+`, or 48 with `{int}`
   fully permissive. No stated rule gives 46.
2. **"Given/When steps that match: 29 of 33"** — likewise 21 or 31, never 29.
3. **"patterns mentioning `{string}`: 29"** — 28 distinct patterns; 29 holds only if the duplicated pattern is counted per
   declaration, which the table does not say.

The headline 17/43 and 26/43 are solid under a stated rule. The document exists so Harry can cost T42-C from counts
rather than optimism, so a number that cannot be derived undermines the whole method.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Every number in the document is reproducible from the stored blobs by a **stated rule**, and the rule is written beside the table that uses it (placeholder treatment, scenario-vs-step counting, Background exclusion, duplicate-pattern treatment). |
| AC2 | The three suspect numbers are corrected or given the rule that produces them. If the original figure was wrong, say so plainly in a short "corrections" note at the end rather than editing history away - the document's credibility is the point. |
| AC3 | A script in the repo (`docs/` is not the place - use `scripts/` or `tools/`) recomputes the document's tables from the store and prints them, so the next reader can re-derive rather than trust. It must run against a store copy and touch nothing. |
| AC4 | Running that script reproduces every number in the final document exactly; any mismatch is fixed before the ticket closes. |
| AC5 | No product code touched, no behaviour change, suite green. |

## Notes

- Do not "fix" a number by choosing a rule that makes the original right. State the rule first, then count.
- The estimate section is not in scope; the review's judgement (quote 7.5-8, not 6.25) is recorded in the merge and in
  this ticket.
