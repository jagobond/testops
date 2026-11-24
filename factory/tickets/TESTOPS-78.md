---
id: TESTOPS-78
title: A verb-less assertion still accuses, and the near miss is never shown
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-72
---

# TESTOPS-78 - The two holes left in the product verdict

## Why this exists

TESTOPS-72 made the product evidence and the verb a rule. Its second review passed it and then found that the rule has
one shape it does not cover and one whose honesty nobody can see.

1. **A verb-less assertion still accuses.** `booking details present` matched `DELETE /booking/{id}` on the bare noun -
   over a `GET /booking/{id}` that was also present - and emitted `repeats product` with `verb_agrees` vacuously true and
   an empty `assertion_verb`. Presence/absence sentences are among the commonest shapes in Gherkin, so this is not an
   edge: the rule protects sentences that name an act it recognises and reverts to round-1 behaviour for the rest.
2. **The near-miss is recorded and never shown.** A near-miss claim is always `distinct`, so it never becomes a finding,
   so it never gets a case page; where a case page exists for a sibling finding it renders as context without its product
   block; and the run page's counts say nothing about it. The refusal sentence is correct and renders - but no page in the
   build shows it for the claims that carry it, so the rule's honesty is invisible exactly where it matters.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A bare-noun match with no recognised intent is **not evidence**: a claim with no verb the intent table knows is refused as a near miss, never `repeats product`. `booking details present` against `GET` and `DELETE` on the same noun produces no repeat, and the record says why in words a reader can act on. Pinned. |
| AC2 | The intent table is a small **explicit** list of forms, not mechanically generated ones; `_intent_forms` either disappears or is backed by a pinned list. A generated form that is not English (`getted`) must not exist, and a test asserts the table's contents exactly, so a future change is a deliberate one. |
| AC3 | The run page counts near misses: "N claims share a noun with a product route but were not counted (verb differs) N (no intent N)", one line, separate from `repeats product` and from `product not consulted`. A reader can see that the rule looked and declined. |
| AC4 | A near-miss claim's record is reachable from a page: where a case page exists for its scenario, the claim shows the near-miss sentence (route, shared word, why it is not a repeat); and the run page links to those claims. "Recorded and invisible" is not acceptable. |
| AC5 | Precision unchanged or better on the fixture set: every `repeats product` in the round-2 tests still fires, and the verb-less fixtures now refuse. Pinned. |
| AC6 | AC7 evidence is re-established on the first snapshot whose product arm holds `.java` - record the snapshot id, the counts and three quoted matches, or state that no such snapshot exists yet. This is the outstanding real-corpus proof; the ticket may close on the statement, but it must not close silently. |
| AC7 | Full suite green; contract suite green; case-page goldens regenerated deliberately with the near-miss block and listed. |
