---
id: TESTOPS-17
title: A clean bill requires having looked
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-5
---

# TESTOPS-17 — No registry, no verdict

## Why

TESTOPS-5's review found the one remaining path where never looking reads as a clean bill. A claim
written with the analyser's default `sources_missing = []`, on a snapshot whose meta records no registry,
renders:

> "Every source needed for this claim was available."

That sentence is a guarantee, produced by absence of information. It requires bypassing the pipeline —
every product call site derives the list from the registry — but it is the exact failure this product
exists to prevent, and a default should not be able to produce it.

`None` and `[]` already mean different things elsewhere in this codebase: TESTOPS-16 separated "this run
recorded nothing" from "nothing bears on this claim" for evidence. Sources have the same need.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A claim records whether sources were *assessed* at all, distinctly from which were missing. `not assessed` (no registry consulted) is representable and is not the same value as "assessed, none missing". |
| AC2 | A claim that was never assessed renders "nothing was checked against any source for this claim" — never a clean bill, never a blank, never an exception. |
| AC3 | A claim that was assessed and found nothing missing keeps its current sentence and is distinguishable at a glance from AC2's. |
| AC4 | The storage default cannot produce a clean bill: writing a claim without an assessment record must yield the not-assessed state, and a CHECK constraint or writer rule enforces it. |
| AC5 | Tests cover all three states (not assessed / assessed-none-missing / assessed-some-missing) from stored rows, and a test asserts the exact sentence for each. |
| AC6 | Existing claims in the store migrate to a state that is honest about what they recorded; the migration does not invent an assessment for a run whose snapshot has no registry meta. |
| AC7 | Corpus verdicts unchanged: 94 claims, 90 distinct, 1 unplaced, 1 gap, 2 review. |
| AC8 | Suite green on both interpreters. |

## Notes

- The reviewer's probe concern is adjacent but out of scope here: a probe that swallows its own exception
  can lie about its state, and no API can audit that. Record it in the ticket's report as a known limit
  rather than pretending to solve it.
