# TESTOPS-82 review — a quoted entity is not display copy

2026-11-24, reviewer. Worktree `C:/Users/<name>/Projects/testops-t82`, branch
`factory/testops-82-quoted-entity`, head `c8973fc`. Everything below was derived offline from the
stored snapshot `demo-booking-levels-20261124-fe8537db-r2` and from direct calls into
`testops/analysers/level_fitness.py` v0.14 with a Demo-booking-shaped surface corpus. No live
store, no port 8791, no network.

## Verdict

**Return.** The corpus work is genuine and the over-refusal the ticket exists to kill is really
dead: all five probes now give their sensible verdicts, 43 claims / 1 repeat / 12 near misses
reproduce offline with 0 verdicts moved, 1252 + 37 pass, 14 goldens untouched. But the second-mark
rule is a one-way gate and the review asked to attack it in both directions: copy now walks through
it as an entity whenever the sentence carries an intent verb or ends the quoted string with a
period, and where two quoted runs compete the record can accuse the *wrong* surface outright.
These are the same failure class the ticket was written to remove, mirrored. AC1-AC5 hold as
written; the rule behind them does not survive the attacks below. One more pass, then merge.

## The five probes, re-run

| probe | verdict | record |
|---|---|---|
| `the "booking" record is shown` | review | word `booking`, `GET /booking/{id}`, show/GET agree, `word_quoted` |
| `a "booking" is created` | repeats_product | word `booking`, `POST /booking`, create/POST agree |
| `the "booking" exists` | distinct, near miss `no_intent` | word `booking`, refused for the act, not the quoting |
| `search for "room" returns results` | distinct, near miss `no_intent` | word `room` |
| `verify the "room" type appears in the list` | repeats_product | word `room`, `GET /room/{id}` — `list` nowhere in the record |

All five match the build report. On probe 1: the outcome (`review`, not a copy refusal and not a
repeat) is right in substance — the record names the entity, the method agrees, and a browser was
spent on a stored-data claim. But it is reached by an accident of vocabulary: the incidental word
`record` matches the `STORE` regex in `_place`, so the claim is classified I1 and the assertion's
real shape (a record *shown*, presentation wording after the quotes) is overridden. The quoting
rule no longer decides this sentence, but the interaction classifier quietly does, by the same
kind of incidental word TESTOPS-82 just removed from the product side. The verdict survives; the
reasoning path is fragile, and it should be named in the next ticket rather than left as a
coincidence that lands well.

## Copy passing as entity, attacked

Seven probes plus the trailing-period case, against a corpus whose surfaces carry the copy words,
so a refusal-by-copy is distinguishable from a refusal-by-no-match:

| assertion | outcome | right? |
|---|---|---|
| `the user sees "Booking"` | refused, `display_copy` | right — the verb mark catches the single word |
| `the "Booking Successful" banner` | refused, `display_copy` | right — multi-word mark |
| `the banner shows "Thanks"` | refused (no surface shares `thanks`) | refused, but by absence, not by the copy rule; the verb mark would have caught it |
| `assert "Welcome" appears` | **accepted as entity** — near miss `no_intent` on word `welcome` | wrong — it is copy, and the only thing that saves the record is that `assert` names no act |
| `the page displays "Ooops"` | refused (no surface shares `ooops`) | the verb mark catches it; right where a route shares the word |
| `the modal says "Saved"` | refused (no surface shares `saved`) | as above |
| `the page shows "Booking created."` | refused, `display_copy` | right — trailing period inside a multi-word run |
| copy whose only mark is a trailing period: `the "Booking." dialog appears` | **accepted as entity** — `no_intent` on `booking` | wrong — a period is not one of the three marks, so single-word copy passes |

And the sharpest form, found while pressing `assert`: a single quoted copy word plus an intent
verb anywhere in the sentence is not merely tolerated, it accuses. `the response contains "Booking"
once it is created` → **repeats_product** on `POST /booking`; `a "Welcome" message is created` →
**repeats_product** on `POST /message`. The display-verb list is closed (`_DISPLAY_VERBS`) and
nothing after the quote is ever consulted, so any copy the author did not put behind
shows/sees/displays/gets/receives/says/reads is treated as the assertion's subject, and the intent
table then does the accusing. This is over-refusal's mirror image and it produces false findings,
not merely wrong reasons.

## Two quoted runs

The outranking rule itself works where it was tested: on the ticket's corpus `verify the "room"
type appears in the list` records `room` and never `list`; `_quoted_subject_words` returns
`{room}` and the rank-0 slot is real. But confirm what "outranks" means: every word in *any*
non-copy quoted run becomes a subject word. With two quoted runs the rule degenerates — both words
sit in rank 0, and the old ranking decides:

- `search for "room" in the "list" view` → word `room`, `GET /room`. The right answer, but by the
  rarity tie-break (`room` in 3 surfaces, `list` in 1), not by subjecthood. A rarer incidental
  quoted word would have won instead.
- `the "booking" is shown in the "message" panel` → **word `message`, `GET /message`, show/GET
  agree, counted as a repeat.** The sentence's subject is the booking; `message` is the incidental
  one, and it is rarer, so the record accuses the contact-message route of publishing the booking
  display. That is a false finding on an ordinary sentence shape, and the choice is not
  defensible — it is the rarity tie-break wearing the outranking rule's authority.

## Passive and other voices

- `the "booking" was created` → repeat on `POST /booking`, create/POST agree. Right intent, right
  method; the passive records correctly.
- `a "room" gets booked` → repeat on `GET /room`, verb recorded as `get`. Wrong: `gets` here is the
  passive auxiliary ("gets booked" = becomes booked), not the reading verb the intent table sees.
  The method "agrees" only because `gets` happens to be spelled like GET — the agreement is
  coincidental with the misreading, which makes it look correct on the page. (`a "room" gets
  created` records create/POST correctly, which shows the misread is specific to `get`.) A passive
  with `gets` records a read where the sentence asserts a change of state.

## Corpus

Re-derived offline, twice, from `demo-booking-levels-20261124-fe8537db-r2`: once from the
TESTOPS-79 merge (`a1adec4`, rebuilt in a temporary worktree against the same self-contained
snapshot — the earlier snapshot cannot be rebuilt offline and is not used) and once from this
tree. Keyed on (scenario, assertion text, line): 43 claims in both, **0 verdicts moved**, and 0
near-miss kinds, matched words or routes differ. After: 1 `repeats_product`, 12 near misses
(8 `display_copy` / 4 `no_intent`), 12 distinct, 4 review, 26 unplaced. The one survivor is the
room-creation claim `New '<room_type>' ... will be created` → **`POST /`, word `room`** — still
the right claim, still refused by nothing. The build report's numbers are reproduced exactly.

Suites, from the project `.venv` with the environment stripped: **1252 passed, 2 skipped**;
contracts **37 passed, 2 skipped**. The 14 goldens (`tests/fixtures/projects_services/index.html`,
`runs.html`, `case-page-01.html` … `case-page-12.html`) are byte-identical — `git status` clean,
no fixture modified.

## Three sharpest concerns

1. **Copy is over-accepted, and can become a false finding.** The second-mark rule only ever looks
   *before* the quote and only at a closed verb list. Single-word copy behind any other verb
   (`assert "Welcome" appears`, `the response contains "Booking"`) is accepted as the subject, and
   with an intent verb anywhere in the sentence it escalates to a repeat — `a "Welcome" message is
   created` accuses `POST /message`. A trailing period is likewise not a mark. The fix is
   directional: the rule must also read *after* the run (an intent or existence verb following a
   quoted word means the quotes named the subject; but a quoted word with nothing but articles and
   verbs of appearance around it, and punctuation inside the run, is copy) — or, more honestly,
   treat punctuation inside a one-word run (`"Saved."`, `"Booking."`) as the banner mark it is.
2. **Two quoted runs: the rarest quoted word wins, and it can accuse the wrong surface.**
   `the "booking" is shown in the "message" panel` records a repeat on `GET /message`. When more
   than one quoted run is present, the record must name the sentence's subject (the run the
   sentence's verb is about), and if it cannot tell which that is, it must refuse the match rather
   than let the rarity tie-break invent one. An accusation on an incidental word is worse than the
   over-refusal this ticket fixed, because it publishes a finding.
3. **The verb table mis-reads passives whose auxiliary collides with a display verb.** `a "room"
   gets booked` records intent `get` and agrees with `GET /room` on a coincidence of spelling. The
   intent reader should not take `gets` as the assertion's act when a content verb follows it
   (`gets booked`, `gets created`); it should read the following participle or refuse the intent
   and return a near miss.

Both new defects are inside `product_match`'s ranking and `_quoted_copy_runs`'s mark test; the
corpus is unaffected (no single-word quoted runs outside placeholders), so a fix can be made with
the same 0-movement guarantee the build already demonstrates.
