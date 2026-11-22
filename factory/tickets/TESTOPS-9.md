---
id: TESTOPS-9
title: Stale claim vocabulary — the schema and the docstrings describe verdicts that were abandoned
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-2
---

# TESTOPS-9 — Stop the code from lying in comments

## Finding (found by the TESTOPS-2 builder, present ever since)

Three places describe verdicts the analyser no longer produces:

- `testops/store/schema.sql` — column comments and a CHECK mentioning `optimal` / `overbuilt` / `necessary`.
- The `Claim` dataclass docstring.
- `testops/analysers/base.py` — the verdict enumeration's prose.

The analyser writes `distinct`, `gap`, `review`, `unplaced`, `duplicate`. A reader who trusts the schema will build
against verdicts that never appear, and a future builder will code a branch for `overbuilt` that can never fire.
Schema comments that lie mislead every reader of the store — including the next agent.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Every verdict name in `schema.sql`, the `Claim` docstring and `analysers/base.py` matches what the analysers emit. A test reads the code for the emitted set and fails if a documented name is not in it. |
| AC2 | The test fails in both directions: a documented verdict that is never emitted, and an emitted verdict that is never documented. |
| AC3 | No behaviour change: verdict counts stay 94/90/1/1/2 on CotW levels and 17/17 on ReqOverflow duplication. |
| AC4 | Stored rows are untouched — this ticket changes words, not data. |

## Notes

- Cheap and overdue; the Product Owner explicitly unblocked it ("I'll accept your recommendation here").
