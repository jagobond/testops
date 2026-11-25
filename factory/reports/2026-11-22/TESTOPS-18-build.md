# TESTOPS-18 build report — 2026-11-22

Branch `factory/testops-12-labels`. Two wording defects from the TESTOPS-12 NEEDS-FIX review.
No verdict moves: 94 claims, 90 distinct, 1 unplaced, 1 gap, 2 review.

## What changed

Defect 1 — the pass note no longer interpolates a label. `queries.pass_note_from_rows` asked
`_ASKS` by interaction code, and its fallback was `f"one is about {label}"`. Any row carrying a
label without a code produced "one is about settled by the response the server sends". The fallback
is gone: `_asks` reads every clause from `_ASKS` by code and returns `None` when any label has no
code, in which case the note still says why one run carries two answers and says nothing it cannot
stand behind. The list also now joins like English - "X and Y" for two, "X, Y, and Z" for three -
instead of the old semicolon-plus-dash construction.

Defect 2 — the response is evidence about the store, not the store. `_second` for an I1 claim read
over HTTP said "that answer says what is stored", which grants a handler's return value authority
over the disk it may never touch. It now reads:

  "The run only reads the responses the server sends, and takes that answer as the report of what
  is stored, so the assertion is checked as far as that answer speaks for the store."

The same discipline is applied where the ticket requires it (AC4): KP says the answer is taken as
the page the server sends and the check reaches as far as that answer speaks for the page; I2 says
the response "is exactly the answer the assertion asks about" and borrows no store authority. I
used "that answer speaks for the store" rather than the reviewer's "the response speaks for the
store" so the controller branch does not tell a reader about a response that was never sent.

Analyser version 0.10.0 -> 0.10.1; the module docstring records the change. No schema change, no
migration, no stored artefact rewritten.

## Tests added

`tests/test_pass_labels.py`
- `test_no_statement_contains_a_label_value` — AC1, over the real analyser's fact-sheet corpus and
  every label value `_label` can produce.
- `test_every_statement_shape_leaves_the_labels_out` — the same guarantee over all four verdicts,
  all six interactions and all six instruments, including the shapes the fixture does not reach.
- `test_a_pass_note_with_two_labels_reads_as_one_sentence` — AC2 two-label grammar: no
  "about settled by", no doubled preposition, no stray spacing.
- `test_a_pass_note_with_three_labels_reads_as_a_list` — AC2 three-label grammar.
- `test_a_label_with_no_code_is_never_used_to_build_the_sentence` — the regression that reproduces
  the reviewer's broken note: label present, code absent, label confined to its quoted slot.

`tests/test_level_fitness.py`
- `test_an_i1_claim_read_over_http_names_the_inference_as_an_inference` — AC3/AC5: the inference
  marker is present and the store-authority phrasing is absent.
- `test_no_statement_confers_store_authority_on_the_response` — AC5 regression over three I1
  claims; a drift back to "says what is stored" fails here.
- `test_the_kp_and_i2_sentences_say_where_their_inference_stops` — AC4.

## Evidence

Suite, clean invocation (`env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX
PYTHONNOUSERSITE=1`):
- 3.12.5 (.venv): 198 passed, 16.54s. 190 before this ticket, 8 added.
- 3.11.15 (uv interpreter): 194 passed, 4 skipped, 16.23s. The four skips are the pre-3.12 checks
  that were already skipped on this interpreter.

Corpus replay, snapshot `demo-product-levels-20261122-a3f19853-r4`, `scripts/replay_levels.py
--acceptance`: 94 claims, 90 distinct, 1 unplaced, 1 gap, 2 review, 41 scenarios, 2 explaining more
than one label — PASS. Label values found verbatim in any statement: 0 (checked against every label
`_label` can produce).

## Six statements from the corpus

1. (distinct, I1 over HTTP) "The assertion is about the data as stored: each fact on the sheet is
   admitted through the admission gate. The run only reads the responses the server sends, and
   takes that answer as the report of what is stored, so the assertion is checked as far as that
   answer speaks for the store."

2. (unplaced, judgement with no comparison) "The step reads \"that count is correct for the store
   it was run against\". Those words judge something right without saying what it is compared
   with, so nothing can be said about whether it is checked."

3. (gap, needs a browser) "The assertion is about what only a browser works out: each fact's
   citation is in an element reachable by an accessible name. Nothing short of a browser can decide
   it, and the run only reads the responses the server sends instead, so nothing checks it."

4. (review, page as served) "The assertion is about the page as served: every rendered fact sits in
   an element carrying a data-fact-id. The page the server sends settles it, yet the run drives a
   browser, so it pays for a browser that decides nothing extra."

5. (distinct, KP over HTTP) "The assertion is about the page as served: the sheet for \"Keegan\"
   shows every proposed fact for \"Keegan\". The run only reads the responses the server sends, and
   takes that answer as the page the server sends, so the assertion is checked as far as that answer
   speaks for the page."

6. (distinct, I2 over HTTP) "The assertion is about the response itself: there is one sheet per
   entity. The run only reads the responses the server sends, which is exactly the answer the
   assertion asks about, so the assertion is checked."

Pass notes, both multi-label scenarios, after the fix:

- "The audit counts what rests on a batch decision": "This scenario carries 2 answers to one run:
  \"settled by the response the server sends\" for 1 assertion, and \"unclear what would settle it\"
  for 1 assertion. The run is one: one is about a guarantee on the data as stored and one names
  nothing that could settle it, so the answers differ in what the assertions ask, not in which
  instrument read them."
- "The character page is server-rendered with stable fact anchors": "This scenario carries 2
  answers to one run: \"settled by the response the server sends\" for 2 assertions, and \"needs a
  browser\" for 1 assertion. The run is one: one is about the page the response carries and one is
  about what only a browser works out, so the answers differ in what the assertions ask, not in
  which instrument read them."

## What this does not solve

The engine sentence still says "whose own answer about the stored data settles it". It is outside
AC3/AC4, which name I1, KP and I2, and the engine's answer is the component that reads the store by
design - but the same "evidence about, not the thing itself" argument could be made about a cached
engine result. Left for a ticket if the reviewer wants it.

The reviewer's third sharp concern - "The assertion is about the data as stored: the pass fails."
reading like a template hiccup - is not in this ticket's acceptance criteria and is unchanged.

## Where to look

`testops/queries.py` (`pass_note_from_rows`, `_asks`), `testops/analysers/level_fitness.py`
(`_second`, `_statement`, version and module docstring), `tests/test_pass_labels.py`,
`tests/test_level_fitness.py`.
