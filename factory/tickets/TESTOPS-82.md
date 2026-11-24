---
id: TESTOPS-82
title: A quoted entity is not display copy - copy needs a second mark
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-79
---

# TESTOPS-82 - The rule now refuses the best-written assertions

## Why this exists

TESTOPS-79 stopped eight false accusations by refusing any shared word that sits only inside quoted text. Its review ran
the obvious attack and it worked:

| assertion | now |
|-----------|-----|
| `the "booking" record is shown` | refused as display copy - but `booking` is the entity |
| `a "booking" is created` | refused - though the verb `create` agrees with `POST /booking` |
| `the "booking" exists` | refused - `booking` is the entity |
| `search for "room" returns results` | refused - `room` is the entity |
| `verify the "room" type appears in the list` | **accused on the word `list`** - a weaker, incidental word |

Quoting is not a reliable signal of copy. Well-written Gherkin quotes its subject *to be unambiguous*, so the rule
refuses exactly the assertions a person would trust most - the failure mode this rule exists to prevent, mirrored.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A **single quoted word** that is the sentence's **only naming of its subject** stays a candidate shared word. Display copy needs a **second mark**: a multi-word quoted run, a display verb in front of it (`shows`, `sees`, `displays`, `reads`, `gets`, `receives`), or banner punctuation (`!` inside the run). Pinned with all five probes above, four accepted and `the "booking" record is shown` judged on its merits rather than by quoting alone. |
| AC2 | `verify the "room" type appears in the list` never accuses on an incidental word: when a quoted run holds the strongest shared noun, the record must use that noun (or refuse naming both words), never justify a repeat with a weaker word. Pinned. |
| AC3 | The eight `message` refusals from the real corpus still refuse, for the right reason: `Booking Successful! message` carries banner punctuation and a display verb in front, so it is copy under the second-mark rule. The corpus count stays at **1 repeat / 12 near misses**, and if it moves, the report must explain each move. |
| AC4 | The near-miss reason distinguishes the two cases in words: copy ("text a person is shown") versus a quoted entity that was refused for another reason. No reason string may assert "rather than the subject of the check" when the word is the subject. |
| AC5 | Full suite green; contract suite green; goldens listed; re-run over the stored snapshot offline (no network, no live store, no port 8791) with the counts quoted. |
