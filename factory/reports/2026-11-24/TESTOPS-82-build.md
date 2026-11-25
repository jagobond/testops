# TESTOPS-82 build — a quoted entity is not display copy

2026-11-24, branch `factory/testops-82-quoted-entity`, worktree
`C:/Users/<name>/Projects/testops-t82`. `level_fitness` 0.13 → **0.14**. No store schema change.

Suite, from the project `.venv` with `PYTHONPATH`/`PYTHONHOME`/`VIRTUAL_ENV`/`CONDA_PREFIX`
stripped and `PYTHONNOUSERSITE=1`: **1252 passed, 2 skipped** (180.7 s). Contract suite alone
(`pytest tests/contracts`): **37 passed, 2 skipped** (13.6 s). `tests/test_product_evidence.py` is
now 31 tests (was 27); four are new. Goldens: **14 pages, all byte-identical** — `index.html`,
`runs.html`, `case-page-01.html` … `case-page-12.html`. No golden file changed on disk.

## The rule

TESTOPS-79 read every quoted run as copy, which refused the assertions a person would trust most.
Quoting is how well-written Gherkin names its subject, so v0.14 requires a **second mark** beside
the quotes. A quoted run is display copy only when one of these holds:

- the run holds **more than one word** (`"Booking created"`);
- a **display verb stands immediately in front** of it — `shows`, `sees`, `displays`, `reads`,
  `gets`, `receives`, `says` (and their inflections, plus the existing `renders`);
- **banner punctuation sits inside it** (`!`), e.g. `"Success!"`.

A single quoted word with none of those marks is the sentence naming its subject, and stays a
candidate shared word. The unquoted banner-phrase rule from TESTOPS-79 (`Visitor will get Booking
Successful! message`) is unchanged, so the eight real-corpus refusals keep their ground.

## What changed

| file | change |
|---|---|
| `testops/analysers/level_fitness.py` | `_quoted_copy_runs()` — the second-mark test for quoted runs; `_display_runs()` now takes copy runs from it and still uses every quoted literal as a banner boundary; `_quoted_subject_words()` — the nouns a non-copy quoted run names; `product_match()` ranks a quoted subject noun ahead of every word outside the quotes and records `word_quoted`; the no-intent and verb-differs reasons append *"The word is quoted because the assertion quotes its own subject; quoting is not why it is refused"* when the word is the subject. `_DISPLAY_VERBS` gains `read`, `receive`, `say` and inflections. Version 0.14. |
| `tests/test_product_evidence.py` | Four new tests: the five probes with every verdict (AC1), the quoted-noun ranking (AC2), the three second marks (AC1), and the two refusal wordings (AC4). |

## Criterion by criterion

| id | what was done, and the evidence |
|----|--------------------------------|
| AC1 | `test_a_single_quoted_word_is_the_subject_and_not_display_copy` pins all five probes. **Verdicts:** <br>1. `the "booking" record is shown` → **review** (the word `record` places it as stored data, I1); the rule's match is real: `product_match` names word `booking` on `GET /booking/{id}`, `verb_agrees: true`, `display_copy: false` — judged on merits, not quoting. <br>2. `a "booking" is created` → **repeats_product**, word `booking`, route `POST /booking`. <br>3. `the "booking" exists` → **distinct**, near miss `no_intent`, word `booking`. <br>4. `search for "room" returns results` → **distinct**, near miss `no_intent`, word `room`. <br>5. `verify the "room" type appears in the list` → **repeats_product**, word `room`, route `GET /room/{id}` (never `list`). |
| AC2 | `test_a_quoted_noun_outranks_an_incidental_word_outside_the_quotes`: on a corpus where `list` is a *route* word and rarer than `room`, the record names `room` and `GET /room/{id}`; `"list"` appears nowhere in the reason. `_quoted_subject_words` returns `{room}` and the ranking puts it first, so a weaker incidental word cannot justify a match. |
| AC3 | `test_a_quoted_run_is_copy_only_when_a_second_mark_says_so` pins all three marks, including each of the seven display verbs immediately in front of a one-word quoted run. The eight `message` refusals are unchanged: `Booking Successful! message` still carries banner punctuation and a display verb (`get`), and `Thanks for getting in touch message` still reads as a capitalised banner. Offline replay of the stored snapshot (below) keeps all eight as `display_copy`. |
| AC4 | `test_the_refusal_distinguishes_copy_from_a_quoted_subject_refused_for_another_reason`: the copy refusal says *"text a person is shown rather than the subject of the check"*; the quoted-entity refusal says *"quoting is not why it is refused"* and contains neither copy phrase — in the stored reason and in `app.near_miss_sentence`. No path can apply the copy wording to a word that is the subject. |
| AC5 | Full suite **1252 passed, 2 skipped**; contracts **37 passed, 2 skipped**; **14 goldens byte-identical**; offline replay quoted below. No network, no live store, no port 8791 — `scripts/replay_levels.py` reads the snapshot and nothing else. |

## The corpus, re-derived offline

`scripts/replay_levels.py --snapshot demo-booking-levels-20261124-fe8537db` (test arm
`m-pujic-levi9-com/cypress-cucumber-e2e-tests@fe8537db`, product arm
`example-org/demo-booking-platform@efe2deb8`), rebuilt twice: once from the TESTOPS-79 tree
(before) and once from this tree (after).

| | before (v0.13) | after (v0.14) |
|---|---|---|
| claims | 43 | 43 |
| `repeats_product` | 1 | **1** |
| near misses | 12 (display copy 8 / no intent 4 / verb differs 0) | **12 (display copy 8 / no intent 4 / verb differs 0)** |
| `distinct` | 12 | 12 |
| `review` | 4 | 4 |
| `unplaced` | 26 | 26 |

**Nothing moved.** Keyed on (scenario, assertion line), all 43 claims are present in both
reversals, **0 verdicts differ**, and **0 near-miss kinds or matched words differ**. No move needs
explaining because there is none: the corpus contains no single-word quoted run outside a
placeholder, and every quoted run it does contain (`'John Doe'`, `'Special Accommodation'`) is
multi-word, so the second mark reads them exactly as v0.13 did. The repeat remains the
room-creation claim (`POST /`, word `room`); the eight `message` claims remain display-copy near
misses on banner phrases.

## What this does not do

- **The one-word second mark is the display verb *in front***, as the ticket specifies. `the
  "booking" record is shown` is therefore a candidate even though `shown` follows it; a sentence
  that puts the verb after the quotes is naming its subject, not reproducing copy.
- **Banner phrases are unchanged.** A capitalised phrase after a display verb (`Booking Successful!
  message`) is still read as copy whether or not it is quoted.
- **A quoted noun outranks the method rule.** When the quoted noun shares a surface whose method
  disagrees while an unquoted word would have matched an agreeing route, the claim is refused on
  the noun rather than counted on the weaker word. That is the conservative direction AC2 asks for.
- **The stored run pages are untouched.** `data/testops.db` still holds earlier runs; replay
  re-derives the claims for this report but writes no artefact.

## Amendment — the review of 2026-11-24 returned this build

Review: `factory/reports/2026-11-24/TESTOPS-82-review.md`, section *Copy passing as entity,
attacked*, plus its three sharpest concerns. The review was right, and this amendment is the one
more pass it asked for. `level_fitness` 0.14 → **0.15**. No store schema change.

The review found that the second mark was a **one-way gate**: it looked only in front of the run and
only at the closed `_DISPLAY_VERBS` list. So copy walked through as an entity whenever the sentence
carried an intent verb elsewhere, and worse, escalated to a **false finding** — `a "Welcome" message
is created` accused `POST /message`, `the response contains "Booking" once it is created` accused
`POST /booking`. A false accusation is the one outcome this tool must never produce.

| review concern | what changed |
|---|---|
| 1. copy is over-accepted and can become a false finding | `_quoted_copy_runs()` now reads **after** the run: a quoted word followed by a noun the product itself names (`a "Welcome" MESSAGE`) modifies that noun and is copy or a value; a verb that takes a caption as its object in front (`contains`, `returns`, `includes`, …) is the same case; an intent or existence verb immediately after the quotes (`a "booking" is created`, `the "booking" exists`, `the "booking" is shown`) says the quotes named the subject and the gate stays open. A claim that quotes display copy at all is refused as `quoted_copy` — it can never be a repeat. |
| 2. punctuation inside a one-word run | a trailing period, comma, bracket or ellipsis inside the run (`"Saved."`, `"Booking."`, `"Booking,"`, `"Booking)"`, `"Booking..."`) is the banner mark it is; the run is copy. |
| 3. two quoted runs, the rarest word wins and can accuse the wrong surface | `_quoted_subject_runs()` names the run the sentence is about — the one an intent/existence verb follows, else the first run — and records it. Where the sentence genuinely names both (a compound subject, one run either side of the verb, two clauses with their own verbs) the record names **both** runs and refuses with `near_miss_kind: "ambiguous_quotes"` instead of letting the rarity tie-break invent a subject. |

The third concern in the review's list — a passive whose auxiliary collides with a display verb
(`a "room" gets booked` reading `get`) — is **not** in this ticket's required fixes and is unchanged
here; it is named for the next ticket rather than half-fixed inside this one.

Two supporting changes keep the record honest where it is counted: `testops/queries.py` counts a
`quoted_copy` refusal in the display-copy total (it is the same reader-facing case) and gives
`ambiguous_quotes` its own total; `testops/web/app.py` names that fourth total only when a run holds
one, so no page that holds none changes by a byte.

### Pinned (six new tests, `tests/test_product_evidence.py` 31 → 37)

| test | pins |
|---|---|
| `test_a_quoted_word_modifying_a_product_noun_is_copy_not_the_subject` | `a "Welcome" message is created` → `quoted_copy`, word `message`, the act agreeing and still not evidence; `contains "Booking"` → `display_copy` |
| `test_a_verb_after_the_quotes_means_the_quotes_named_the_subject` | `a "booking" is created` still repeats `POST /booking`; `the "booking" is shown` / `exists` keep `booking` as the subject |
| `test_punctuation_inside_a_one_word_run_is_the_banner_mark_it_is` | all five trailing-punctuation forms are copy; an unpunctuated quoted entity is not |
| `test_with_two_quoted_runs_the_record_names_the_sentences_subject` | `the "booking" is shown in the "message" panel` → `booking`, `GET /booking/{id}` (never `GET /message`); `search for "room" in the "list" view` → `room` |
| `test_two_quoted_runs_the_sentence_does_not_choose_between_are_named_and_refused` | compound subject, run either side of the verb, two clauses → `ambiguous_quotes`, both runs named, state `zero` |
| `test_a_quoted_display_string_can_never_become_a_repeat_finding` | **the failure it prevents**: every assertion reproducing a caption in quotes is asserted never to reach `PRODUCT_FOUND` |

### No weakening — the five original probes, the corpus and the goldens

- **The five original probes keep their verdicts**: `the "booking" record is shown` → `review`,
  `a "booking" is created` → `repeats_product` (`POST /booking`), `the "booking" exists` →
  `distinct` / `no_intent`, `search for "room" returns results` → `distinct` / `no_intent`,
  `verify the "room" type appears in the list` → `repeats_product` (`GET /room/{id}`, word `room`).
  All five pinned by the existing tests, unchanged.
- **Corpus, rebuilt offline twice** from `demo-booking-levels-20261124-fe8537db-r2` (store copied
  to a scratch directory; no network, no live store, no port 8791): once from the TESTOPS-82 head
  `c8973fc` in a temporary detached worktree, once from this tree. Keyed on (scenario, assertion
  text, line): **43 claims in both, 0 verdicts moved**, and **0 near-miss kinds, matched words or
  routes differ**. After: **1 `repeats_product`**, **12 near misses (8 `display_copy` / 4
  `no_intent`)**, 12 `distinct`, 4 `review`, 26 `unplaced`. The one repeat is still the room-creation
  claim (`New '<room_type>' … will be created` → `POST /`, word `room`); the eight `message` claims
  keep their display-copy refusals. The only field that differs on any claim is the new
  `quotes_ambiguous` (absent → `False`).
- **Suites, from the project `.venv` with the environment stripped and `PYTHONNOUSERSITE=1`**:
  full suite **1258 passed, 2 skipped** (177.8 s); contracts alone **37 passed, 2 skipped** (12.2 s).
  `tests/test_product_evidence.py` alone: **37 passed**.
- **Goldens: 14 pages, all byte-identical** — `index.html`, `runs.html`, `case-page-01.html` …
  `case-page-12.html`. No fixture changed on disk (`git status` shows only the analyser, the web
  render helper and the test file).

