# TESTOPS-78 review

Recorded by the lead from the reviewer's reply. The reviewer reached its tool-call limit before writing this file, so the
findings below are its own words, transcribed verbatim where they are verdicts. Nothing here was added.

## Verdict

PASS on the two holes it was written for. The verb-less probe now refuses; the near-miss record is rendered on a run page
and reachable from a case page. But the re-count shows the build does **not** improve the real corpus, and two new holes
were found while testing it.

## The verb-less probe

- `booking details present` → **refused** (distinct, `near_miss: no_intent`, DELETE route named, actionable reason).
- `booking details present and the confirmation is displayed` → **repeats_product** (display → GET, correct).
- `details` alone → distinct, no shared noun, correctly no near miss.
- `Visitor sees "Booking created"` → **refused** (verb_differs) — but the quoted string's `create` became the recorded
  intent. See concern 2.

## The rewritten fixture, judged

The property is intact: same fields in both arms, the verdict moves only with the route, and it fails without the route.
But the assertion was rewritten from "announced" (verb-less, would now refuse) to "shown"/GET, so it proves AC2 on a
pairing the table likes; the harder pairing is pinned separately. **Not a tautology, but weaker than stated.**

## The intent table

Pinned as a literal dict with a whole-table equality test; `getted`/`readed` are gone (only comments mention them).
Adding a verb now means editing a human-readable list plus the test literal — which is the intent.

## Near misses a reader can see

They render: run page line "verb differs 0 / no intent 1", the block showing route, shared word and reason, a case-page
anchor (`#near-miss-claim-2`) and a back-link. **But the eight `message` claims do not read as near misses under this
branch** — `will get … message` maps to verb `get`, GET agrees, so all eight still count as `repeats_product`. That is
TESTOPS-79's job, and this is the honest statement that T78 does not do it.

## The real corpus, re-counted

The worktree store holds 0 `.java` (the build's statement is true there); the copied live store holds
`demo-booking-levels-20261124-fe8537db` with 142 `.java`, so AC7 is re-established here: **9 of 43 claims are
`repeats_product`, unchanged.** Quoted matches, all `GET /{id:[0-9]*}` with verb `get` agreeing:

- "Visitor will get Booking Successful! message"
- "Visitor 'John Doe' will get Thanks for getting in touch message"
- one true positive: "New '<room_type>' type… will be created" (POST /, create)

Suites: 1234 passed + 2 skipped; contracts 37 + 2 skipped. Fourteen goldens byte-identical.

## Three sharpest concerns

1. **`the room list is shown` is classified KP** ("settled by the page the server sends") and never reaches the product
   rule at all — the verb rule is bypassed by the interaction classifier. A whole class of browser claims is therefore
   exempt from the question the tool exists to ask.
2. **A quoted string's verb is read as the assertion's intent** ("Booking created" made `create` outrank the sentence's
   real verb), so display copy can drive the verdict. This is the same fault as TESTOPS-79 in a different place.
3. **The precision pin measures nothing about the real corpus.** The re-count is unchanged at 9, so AC5's "precision
   unchanged" is true but vacuous here, and the live store's own run (analysed 11:46) predates this branch, so the page a
   person opens still shows the old verdicts.
