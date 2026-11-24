---
id: TESTOPS-79
title: Eight of nine repeats are homonyms - a word in quoted UI copy is not an entity
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-72
---

# TESTOPS-79 - The first real corpus run accuses the wrong eight

## Why this exists

On 2026-11-24 the live store got its first restful-booker run with a readable product arm (142 `.java` parsed, 25
surfaces) - the first time product evidence reached a real paired corpus. It produced nine `repeats product` claims.
Read as a sceptic, **one is defensible and eight are wrong**, and the wrongness has a single shape.

| assertion | matched | verdict |
|-----------|---------|---------|
| `New '<room_type>' ... room ... will be created` | `POST /` *create room* | **defensible** - the route creates a room |
| `Visitor will get Booking Successful! message` | `GET /{id}` *get message* | **wrong** - the route returns a *contact* message, the assertion checks a banner |
| `Visitor 'John Doe' will get Thanks for getting in touch message ...` (x7 across contact feature) | `GET /{id}` *get message* | **wrong**, same shape |

The shared word is `message`, and it is shared between a **UI sentence about displayed copy** and a **domain entity in
another service**. The tool then advises "call `GET /{id}` and check the response" - advice that would fail, because that
route returns a contact message, not a booking confirmation.

The fix is a rule, not a stop-list: a word that appears **inside the assertion's quoted UI copy** is display text, not the
subject of the claim, and cannot be the shared word on its own. `message` also reaches three surfaces, so the observation
half of this is that rarity alone cannot tell an entity from a common noun.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A word that occurs **only inside the assertion's quoted literals** is not a candidate shared word. The eight `message` claims above become near misses whose reason says the overlap was quoted display copy. Pinned. |
| AC2 | The defensible case survives: the room-creation assertion matches `POST /` *create room* on `room`, which is not quoted copy (it is `<room_name>` a slot, not a literal). Pinned both ways, so the rule cannot be satisifed by refusing everything. |
| AC3 | The near-miss reason is a sentence a reader can act on and names the quoted word, e.g. "the only word these share is "message", which appears only inside the assertion's quoted text, so it is display copy rather than the subject of the check". |
| AC4 | Re-run the live corpus from the stored snapshot (`restfulbooker-levels-20261124-fe8537db`) and report the new counts: how many of the 43 claims are `repeats product`, how many near misses, and the three strongest matches quoted with route, word and surface claim. Say plainly if the number is lower than 9. |
| AC5 | Precision, stated honestly: of the previous nine, which survive. The expected answer is one, and if it is not one, the report must argue why each survivor is defensible. |
| AC6 | A quoted string's own verb must not become the assertion's intent: `Visitor sees "Booking created"` records the sentence's verb, not `create` from the quoted copy, and cannot outrank it. This is the same fault as AC1 in a different place - display copy driving the verdict. Pinned. |
| AC7 | The interaction classifier bypass: `the room list is shown` is classified KP ("settled by the page the server sends") and never reaches the product rule. Either such a claim is assessed by the product rule, or the page states why a browser claim is exempt. Decide which, write the reason, and pin it - a whole class of browser claims cannot be silently outside the question the tool exists to ask. |
| AC8 | Full suite green; contract suite green; case-page goldens unchanged except where a verdict changed, each listed. |
