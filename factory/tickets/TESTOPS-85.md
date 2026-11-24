---
id: TESTOPS-85
title: Three refusals in the quoted-copy rule that should have been findings
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-82
---

# TESTOPS-85 - The cost of refusing, three times

## Why this exists

TESTOPS-82 stopped copy becoming a finding and was accepted. Its second review then pressed the remaining direction and
found three refusals that are wrong, plus one case the build deliberately left alone:

1. **A compound domain noun reads as a caption.** `a "room" booking exists` is refused as copy, when it is an entity claim
   about a booking. Quoted word plus product noun is as likely to be a compound entity (`"room" booking`) as a caption
   (`"Welcome" message`); an existence or intent verb after the noun phrase should rescue it, exactly as it rescues a bare
   quoted subject.
2. **The refusal is word-blind.** `the "booking" booking` refuses on the quoted run even though the same word occurs
   unquoted and is the real subject of the sentence.
3. **The stored reason is empty** for at least one copy refusal, so the page shows a refusal with no explanation - the fault
   TESTOPS-78 fixed for near misses, recurring here.
4. **The passive voice is unchanged**: `a "room" gets booked` records nothing useful, and every review since T72 has flagged
   it. Either handle it or state on the page that a passive claim was not assessed.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A quoted word followed by a product noun is copy **only** when no existence or intent verb governs the noun phrase; `a "room" booking exists` is a finding about the booking, while `a "Welcome" message is created` stays a refusal. Pinned both ways. |
| AC2 | The refusal is word-aware: when the same word occurs unquoted in the sentence and is the subject, the unquoted occurrence is the candidate and the quoted run cannot suppress it. `the "booking" booking` is assessed on the unquoted `booking`. Pinned. |
| AC3 | No refusal may carry an empty reason: a test iterates every near-miss state the fixture suite produces and asserts each has a non-empty sentence a reader could act on. |
| AC4 | The passive voice is either assessed (`a "room" gets booked` -> intent create, `POST /room`) or the record says in words that a passive claim was not assessed and why. Pinned, and the choice stated in the report. |
| AC5 | No weakening: the corpus stays 43 claims / 1 repeat / 12 near misses with 0 moves, reproduced offline; the five T82 probes keep their verdicts; `test_a_quoted_display_string_can_never_become_a_repeat_finding` still passes. |
| AC6 | Full suite green; contract suite green; goldens listed. |
