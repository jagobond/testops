---
id: TESTOPS-45
title: The store will accept any verdict string, and 128 rows still carry retired names
feature: F2
status: done
autonomy: build
depends_on: TESTOPS-9
---

# TESTOPS-45 — Nothing at the storage layer knows what a verdict is

## Finding (TESTOPS-9 review)

TESTOPS-9 was written on the premise that `schema.sql` carried a `CHECK` listing `optimal`, `overbuilt`, `necessary`.
It does not: **there is no verdict CHECK at all**. The reviewer inserted `verdict = 'total_nonsense'` into a copy of
the live store and SQLite accepted it. The only CHECKs on `claim` are provenance and sources-assessed pairing.

Two facts make this awkward:

- 128 stored rows still carry the retired names. A retroactive CHECK would reject them, and rewriting them would
  violate the invariant that evidence is immutable.
- The web layer renders whatever string it finds, so an unknown verdict is not merely stored — it is displayed with
  whatever the template falls back to.

## Decision taken here (Lead's call, open to reversal)

**A trigger, not a rewritten table.** `BEFORE INSERT` and `BEFORE UPDATE OF verdict` refuse a verdict not in the
emitted set, naming the value and the set. Existing rows keep their names; history is not rewritten. The retired names
are documented as historical in the schema comment, with the ticket that retired each one.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Inserting an unknown verdict fails at the store with a message naming the value and the allowed set — regardless of which code path writes it (analyser, fixture, CLI, a future connector). Prove by direct SQL, not through the repository layer. |
| AC2 | Updating an existing row's verdict to an unknown value fails the same way. |
| AC3 | The 128 rows with retired names remain readable and render exactly as today; the migration does not touch them. |
| AC4 | The allowed set lives in one place. A test asserts the trigger's set, the analysers' emitted set and the documented set are identical — the same both-directions test as TESTOPS-9, now anchored in the store. |
| AC5 | A row whose verdict is unknown *today* (if any exists outside the 128) is reported by a `testops check-store` command rather than crashing a page, so a legacy store can be inspected honestly. |
| AC6 | No behaviour change for existing runs: Demo Product 94/90/1/1/2, DemoService 17/17, pages unchanged. |

## Notes

- Triggers are SQLite-specific; keep the validation in one function the trigger calls conceptually, so a future
  Postgres move is a re-implementation, not a rediscovery.
- If AC3 turns out impossible without rewriting rows, stop and report — do not normalise history to satisfy a
  constraint.
