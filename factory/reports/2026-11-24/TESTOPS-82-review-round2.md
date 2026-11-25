# TESTOPS-82 review, round 2 — the second mark reads both ways

2026-11-24, reviewer. Worktree `C:/Users/<name>/Projects/testops-t82`, branch
`factory/testops-82-quoted-entity`, head `f2fc2f8` (the amendment). Everything below was derived
offline from direct calls into `testops/analysers/level_fitness.py` v0.15 with the review corpora
(the round-1 fixtures in `tests/test_product_evidence.py`) and from the stored snapshot
`restfulbooker-levels-20261124-fe8537db-r2`. No live store, no port 8791, no network.

## Verdict

**Accept.** Every attack that produced a *false finding* in round 1 now refuses. The two
accusations the review surfaced are dead, the backward-reading rule keeps the genuine
quoted-entity assertions the ticket exists to protect, punctuation inside a one-word run is
finally a mark, and the two-run case names the sentence's subject or refuses as
`ambiguous_quotes`. Corpus, suites, goldens and the five original probes all reproduce exactly.
Three defects remain, all in the **refusing** direction — a compound-noun misread, a word-blind
copy refusal, and a reason string that does not name the copy it refuses — and one punctuation
gap. None of them can publish a finding, which is the standard this amendment was written to.
They should be the next ticket, not a third round on this one.

## The two accusations, re-run

Both re-run through the real analyser (round 1 caught them as `repeats_product`; both were
reproduced then, so their refusal now is a real change, not a fixture change).

1. `a "Welcome" message is created` (corpus with `GET/POST /message` + `POST /booking`):
   **distinct, not a repeat.** word `message`, route `POST /message` recorded, `verb_agrees:
   True`, near miss `quoted_copy`, state `zero`. The quoted `Welcome` is read as the caption of
   the noun `message` the product names, and the agreeing act is explicitly *not* counted as
   evidence. The reason says the shared word "says nothing" and ends "not counted as a repeat".
2. `the response contains "Booking" once it is created` (six-surface booking corpus):
   **distinct, not a repeat.** word `booking`, route `POST /booking` recorded, near miss
   `display_copy`, state `zero`, `display_text: "Booking"`. `contains` takes the quoted text as
   its object; the run is copy and the `is created` after the sentence's "it" never rescues it.
   No `POST /booking` repeat.

Both verdicts are pinned by `test_a_quoted_display_string_can_never_become_a_repeat_finding`
(8 cases, every one asserted never to reach `PRODUCT_FOUND`) and by
`test_a_quoted_word_modifying_a_product_noun_is_copy_not_the_subject`.

## Reading backwards, attacked

| probe | outcome | judged |
|---|---|---|
| `a "booking" message is created` | refused, `quoted_copy` (word `message`, `POST /message`) | right in the refusing direction — with `message` a product noun, the dominant reading is a caption/value in front of the noun |
| `the "booking" is created as a message` | **repeat**, word `booking`, `POST /booking` | right — "as a message" is instrumental; `message` does not stand immediately after the quotes, so the run stays the subject |
| `a "room" booking exists` | refused, `quoted_copy` | **wrong refusal** — see below |
| `the "message" from the booking form is shown` | **repeat**, word `message`, `GET /message/{id}`, show/GET agree | right — the message is the sentence's subject; `booking form` is incidental |
| `the "booking" booking` | refused, `quoted_copy` | **wrong refusal, word-blind** — see below |

Two wrong refusals, both real:

1. **Compound domain nouns.** `a "room" booking exists` is an entity claim — a room booking, of
   which existence is asserted — and should be a `no_intent` near miss on the word `booking`.
   Instead the "quoted word followed by a product noun" mark fires and refuses on `room` as
   copy. The mark cannot tell a caption (`"Welcome" message`) from a compound noun whose first
   element is itself a domain word (`"room" booking`). The distinguisher is sitting right there:
   the quoted word is a domain word too. A false accusation is out of reach here, but the ticket
   was opened because refusals cost, and this one costs a sensible sentence.
2. **The copy refusal is run-level, not word-level.** `the "booking" booking` refuses the whole
   claim because *a* quoted copy run exists, even though the same word also occurs unquoted and
   is the only candidate subject. The word-level `_display_copy()` gets this right (it returns
   `{}` — every-occurrence logic), but the span-level `quoted_copy` check on the record
   overrides it and hides the noun entirely. Worse, the stored `reason` prints
   `the assertion quotes display copy ""` — an empty pair: `display_text` is `"booking"`, the
   record has it, and the reason template drops it. The page
   (`app.near_miss_sentence`) renders the copy correctly, so a reader on the page is fine; the
   reason stored in the case is not. (The round-1 `Welcome` case shows the same empty pair in
   the stored reason; the page sentence names `Welcome`.)

## Punctuation

- `the "Saved." banner` → copy (`'Saved.'`), refused `display_copy`, word `saved` withheld even
  against a `GET /saved` surface; the reason names the copy text. Right.
- `the "Booking." dialog appears` → copy (`'Booking.'`), refused `display_copy` on the booking
  corpus. Right.
- `Room's availability` → an apostrophe is not a quote pair; no run is formed, no copy, nothing
  misfires. Right.
- `the "room", "booking" pair` → `room` is read as copy (it stands before the product noun
  `booking`) and `booking` as the entity. Refusing-direction and defensible for the compound
  reading, but the asymmetry inside one sentence is worth naming: the same mark logic that
  wrongly refuses `a "room" booking exists` decided this, by luck of word order.
- One-word run ending in a question mark: **the rule does not catch it.** `the "room?" appears`
  is treated as a quoted entity (no_intent on `room`); `?` is not among the punctuation marks
  (`!` anywhere; trailing `.` `,` `)` `]` `}` `…`). A caption is exactly as likely to end in a
  question mark as in a full stop (`"Who are you?"`), so this is the `"Saved."` hole one
  character to the right.

## Two and three runs

- `the "booking" is shown in the "message" panel` (corpus with `GET /message/{id}` present, so
  `message` is matchable and rarer in the old ranking): word `booking`, `GET /booking/{id}`,
  show/GET agree, repeat. **`GET /message` is never accused** — the round-1 false finding is
  gone, by subjecthood, not by luck.
- `search for "room" in the "list" view` → `room`, `quotes_ambiguous: False`. Still right.
- Three runs in one sentence: `the "booking" is created in the "room" view of the "message"
  panel` → the verb-governed run is the subject (`booking`, `POST /booking`); the other two runs
  are correctly demoted. Right.
- Three runs as a compound subject (`the "booking", the "room" and the "message" are created`)
  → `ambiguous_quotes`, state `zero`, no repeat — but the record names only two of the three
  quoted runs (`room` and `message`; `booking` is dropped from `quoted_runs` and from the
  reason, which says "quotes two things"). The refusal is right; the reason undercounts what the
  sentence quotes. Same completeness defect, smaller dose.

## The passive case

`a "room" gets booked` → **unchanged**, exactly as the build admits: repeat on `GET /room`,
word `room`, `verb_agrees: True`, verb recorded `get`. `gets` is still read as the assertion's
act even though `booked` follows it, and the agreement with `GET /room` is the round-1
coincidence of spelling (control: `a "room" gets created` correctly records create/POST). The
method "agrees" only because the misread verb is spelled like the method — a read recorded
where the sentence asserts a change of state, and it looks correct on the page. Left for the
next ticket as declared.

## No weakening

- **Five original probes keep their verdicts**, re-run directly: `the "booking" record is
  shown` → `review`; `a "booking" is created` → `repeats_product`, `POST /booking`; `the
  "booking" exists` → `distinct`/`no_intent`, word `booking`, `word_quoted`; `search for "room"
  returns results` → `distinct`/`no_intent`, word `room`; `verify the "room" type appears in the
  list` → word `room`, `GET /room/{id}`, never `list`.
- **Corpus offline, rebuilt at both heads against the same snapshot copy.** I rebuilt the claim
  set twice from `restfulbooker-levels-20261124-fe8537db-r2` (a scratch copy of the store; no
  network, no live store): once with the tree at `c8973fc` in a temporary worktree, once at
  `f2fc2f8`. Keyed on (path, line, assertion text): **43 claims in both, 0 verdicts moved**, 0
  near-miss kinds, matched words or routes differ. After: **1 `repeats_product`**, **12 near
  misses (8 `display_copy` / 4 `no_intent`)**, 12 `distinct`, 4 `review`, 26 `unplaced` — the
  build report's numbers exactly. The one repeat is still the room-creation claim (`POST /`,
  word `room`).
- **Suites**, from the project `.venv` with the environment stripped and `PYTHONNOUSERSITE=1`:
  full suite **1258 passed, 2 skipped** (178 s); contracts **37 passed, 2 skipped**;
  `tests/test_product_evidence.py` **37 passed** (74 passed total with contracts).
- **Goldens byte-identical:** `git diff c8973fc f2fc2f8 -- tests/fixtures` is empty — none of
  the 14 rendered pages changed on disk.
- **The named test exists and holds:**
  `test_a_quoted_display_string_can_never_become_a_repeat_finding`
  (`tests/test_product_evidence.py:1041`) passes, and its eight cases are exactly the shapes
  that accused in round 1, so any regression of the copy rule fails it.

## Three sharpest concerns

1. **The "quoted word + product noun" mark over-fires on compound domain nouns.** `a "room"
   booking exists` is refused as copy when it is an entity claim about a booking. The mark is
   the right idea and the right direction, but it needs one more bit: when the quoted word is
   itself a word the product carries, quoted word + product noun is as likely to be a compound
   entity (`"room" booking`) as a caption (`"Welcome" message`), and existence/intent verbs
   after the noun phrase should rescue it the way they rescue a bare quoted subject. This is
   the only place the amendment is wrong in the refusing direction, and this ticket exists
   because refusals cost.
2. **The copy refusal is word-blind, and its stored reason is empty.** `the "booking" booking`
   refuses on the quoted run even though the same word occurs unquoted and is the real subject;
   the span-level `quoted_copy` check overrides the word-level every-occurrence logic. And for
   both this case and `a "Welcome" message is created`, the stored `reason` prints
   `quotes display copy ""` — `display_text` is populated but never interpolated, so the reason
   in the store refuses copy it does not name. The page renders it correctly; the record a
   query or an export reads does not. The refusal's honesty is the point of AC4; fix the
   template and make the span check defer to the word it would hide.
3. **`?` (and `:` `;`) inside a one-word run are not marks, and an ambiguous compound subject
   names only some of its runs.** `the "room?" appears` reads as a quoted entity today — the
   `"Saved."` hole one character right. And on the three-run compound subject the record says
   "quotes two things" where the sentence quotes three; an ambiguous refusal should name every
   run it refuses between, or the reader cannot see what was left undecided.

The passive-`gets` misread stands as round 1 described it, is still honestly declared, and
should be the next ticket's fourth item with the three above.
