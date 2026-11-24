# TESTOPS-85 build — refusing costs too

2026-11-24, branch `factory/testops-85-refusals`, worktree
`C:/Users/Chester/Projects/testops-t85`. `level_fitness` 0.15 → **0.16**. No store schema change.

Suite, from the project `.venv` with `PYTHONPATH`/`PYTHONHOME`/`VIRTUAL_ENV`/`CONDA_PREFIX`
stripped and `PYTHONNOUSERSITE=1`: **1282 passed, 2 skipped** (174.0 s). Contract suite alone
(`pytest tests/contracts`): **37 passed, 2 skipped** (18.6 s). `tests/test_product_evidence.py`
is now **41 tests** (was 37); four are new.

## The four refusals, before and after

| # | assertion | before | after |
|---|---|---|---|
| 1 | `a "room" booking exists` | `quoted_copy`, word `booking`, reason `quotes display copy ""` | `no_intent`, word `booking`, route recorded, no copy run |
| 2 | `the "booking" booking` | `quoted_copy`, reason `quotes display copy ""` | `no_intent` on the unquoted `booking`; no copy run |
| 3 | `a "Welcome" message is created` | `quoted_copy`, reason `quotes display copy ""` | `quoted_copy`, reason names `"Welcome"` |
| 4 | `a "room" gets booked` | `found` / repeat on `GET /room` (read recorded) | `passive_voice`, `zero`, declared not assessed |

**The rule.** A quoted single word in front of a noun the product carries is a **compound entity**
when the quoted word is itself a word the product carries *and* an existence or intent verb governs
the noun phrase (past any copula or auxiliary): `a "room" booking exists` is about the `booking`,
and `a "room" booking is created` is create/`POST /booking`. A caption's quoted word is not a
product word (`"Welcome" message`), so it stays copy. The domain-word bit is required by the
ticket's own pair: `is created` governs the noun phrase in both sentences, so the verb alone cannot
tell them apart; the review names the same distinguisher ("the quoted word is a domain word too").

**The word-awareness.** A quoted caption suppresses the words inside it and the product noun it
modifies, **per occurrence**. `the "booking" booking` is the same word quoted and unquoted, so the
unquoted occurrence is the subject. The T82 guard is untouched: if *any* quoted copy remains, the
claim is still refused, so copy can never become a finding.

**The empty reason.** The `quoted_copy` branch interpolated `match["display_text"]`, which is only
populated for unquoted display copy, so every such record stored `quotes display copy ""`. The
record now carries `quoted_copy_text` - the caption that hides the matched word - and the reason
quotes it. `app.near_miss_sentence` names the same text.

## The passive: declared, not assessed

**Choice: declared.** `a "room" gets booked` is recognised as a passive whose auxiliary (`gets`) is
also an intent form. The auxiliary no longer supplies the act, so the record cannot agree with
`GET /room`. Because the participle `booked` is not in the intent table, the record says in words
that a passive claim was **not assessed and why** (`near_miss_kind: "passive_voice"`, reason and
page sentence both carry "does not assess what a passive claim asks the product to do"). The
control `a "room" gets created` still reads create/`POST /room`.

Assessing it as create/`POST /room` would need a word list mapping `booked` to creation. This
analyser's copy rule is deliberately typographic, not a list of nouns, and a product-specific verb
list is exactly the kind of guess that produces a confident wrong answer. Declaring is the option
AC4 allows and the one that removes the false `GET` repeat without inventing a verb.

Only auxiliaries that are also intent forms (`get`, `gets`, `getting`, `got`, `gotten`) are treated
as this passive. `is redirected` never supplied an intent, so the real corpus keeps its
`no_intent` refusal and no near-miss kind moves.

## Criterion by criterion

| id | what was done, and the evidence |
|----|--------------------------------|
| AC1 | `_quoted_compound_heads()` finds a quoted domain word in front of a product noun governed by an existence/intent verb, and returns the head noun as the subject; `_quoted_copy_runs()` does not mark that run copy; `_quoted_subject_words()` returns the head. Pinned by `test_a_quoted_word_before_a_product_noun_is_an_entity_when_a_verb_governs_it`: `a "room" booking exists` → `no_intent`, word `booking`, `quoted_copy == []`, `word_quoted False`; `a "room" booking is created` → repeat `POST /booking`; `a "Welcome" message is created` → `quoted_copy`, word `message`, `display_text "Welcome"`; `the "room" booking` (no verb) stays a refusal. |
| AC2 | `_quoted_copy_suppressed()` suppresses a word only when **every** occurrence is inside a copy run or is the product noun it modifies. `the "booking" booking` has no copy run (the quoted word is the head's own word), so the unquoted `booking` is the candidate. Pinned by `test_the_copy_refusal_is_word_aware_and_cannot_hide_an_unquoted_subject`: `no_intent`, word `booking`, no empty pair, `_quoted_copy_suppressed('the user sees "booking" and a booking exists') == {}` while `a "Welcome" message` suppresses both words. |
| AC3 | The `quoted_copy` reason now interpolates `quoted_copy_text` (the caption that hides the word), and `near_miss_sentence` does the same. `test_every_near_miss_state_has_a_reason_a_reader_can_act_on` walks **all six** states the fixtures produce - `display_copy`, `no_intent`, `verb_differs`, `quoted_copy`, `ambiguous_quotes`, `passive_voice` - and asserts each stored reason is non-empty, long enough to be a sentence, carries an action ("check this one by hand" / "check whether"), contains no empty quote pair, and that the page sentence is non-empty and free of `I1`-`I4`/`KP`. |
| AC4 | Declared (above). Pinned by `test_a_passive_claim_is_declared_not_assessed`: `a "room" gets booked` → not `repeats_product`, `passive_voice`, `passive == "gets booked"`, `assertion_verb == ""`, reason and page both say "does not assess"; control `a "room" gets created` → repeat `POST /room`. |
| AC5 | Corpus, five probes and the named test below. **0 moves.** |
| AC6 | Full suite **1282 passed, 2 skipped**; contracts **37 passed, 2 skipped**; goldens below, none changed on disk. |

## No weakening

- **Corpus, rebuilt offline** from `restfulbooker-levels-20261124-fe8537db-r2` with
  `scripts/replay_levels.py`, twice: once from the branch head `21e3248` in a detached worktree,
  once from this tree (a scratch copy of the store; no network, no live store, no port 8791).
  Keyed on (subject, assertion text, line): **43 claims in both, 0 verdicts moved**, and **0
  near-miss kinds, matched words or routes differ**. After: **1 `repeats_product`**, **12 near
  misses (8 `display_copy` / 4 `no_intent`)**, 12 `distinct`, 4 `review`, 26 `unplaced`. No
  near-miss reason in the rebuilt corpus is empty.
- **The five T82 probes keep their verdicts** (pinned by
  `test_a_single_quoted_word_is_the_subject_and_not_display_copy`, passing):
  `the "booking" record is shown` → `review`; `a "booking" is created` → `repeats_product`,
  `POST /booking`; `the "booking" exists` → `distinct`/`no_intent`, word `booking`;
  `search for "room" returns results` → `distinct`/`no_intent`, word `room`;
  `verify the "room" type appears in the list` → word `room`, `GET /room/{id}`, never `list`.
- **`test_a_quoted_display_string_can_never_become_a_repeat_finding` passes**, all eight cases.
  Any change that let copy become a finding would fail it; none does.
- **Goldens, 16 pages, all byte-identical** (no fixture changed in `git diff`):
  `tests/fixtures/projects_services/index.html`, `runs.html`, `case-page-01.html` …
  `case-page-12.html`; `tests/fixtures/source_band/case-surfaces-band.html`;
  `tests/fixtures/product_line/case-product-line-missing.html`.

## One repository fix, outside the analyser

`tests/fixtures/product_line/case-product-line-missing.html` was checked out with CRLF while the
page renders with LF, so the byte-for-byte golden failed **at HEAD too** (verified in a detached
worktree before any change). `.gitattributes` already carries `-text` for the other two golden
directories for exactly this reason; the product-line rule was missing. Added
`tests/fixtures/product_line/*.html -text` and renormalised the working copy (index hash unchanged).
This makes the comparison measure the render, not the checkout.

## Files changed

| file | change |
|---|---|
| `testops/analysers/level_fitness.py` | v0.16: `_quoted_compound_heads`, `_quoted_copy_suppressed`, `_passive_phrase`, `_governed_by_verb`; compound rescue in `_quoted_copy_runs`/`_quoted_subject_runs`/`_quoted_subject_words`; word-aware suppression in `product_match`; `quoted_copy_text` and `passive` on the record; the two corrected reasons. |
| `testops/web/app.py` | `near_miss_sentence`: the copy refusal names the copy that hides the word; a `passive_voice` branch states the claim was not assessed and why. |
| `testops/queries.py` | docstring: a passive near miss is counted with `near_miss_no_intent` (it names no act the rule knows). |
| `tests/test_product_evidence.py` | four new tests (AC1, AC2, AC3, AC4). |
| `.gitattributes` | the product-line golden is `-text`, as the other byte-compared goldens already are. |
