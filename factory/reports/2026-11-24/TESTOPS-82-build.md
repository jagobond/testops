# TESTOPS-82 build — a quoted entity is not display copy

2026-11-24, branch `factory/testops-82-quoted-entity`, worktree
`C:/Users/Chester/Projects/testops-t82`. `level_fitness` 0.13 → **0.14**. No store schema change.

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

`scripts/replay_levels.py --snapshot restfulbooker-levels-20261124-fe8537db` (test arm
`m-pujic-levi9-com/cypress-cucumber-e2e-tests@fe8537db`, product arm
`mwinteringham/restful-booker-platform@efe2deb8`), rebuilt twice: once from the TESTOPS-79 tree
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
