# TESTOPS-31 build report — 2026-11-22

Branch `factory/testops-31-tables`, based on `ddd6ccb` (HEAD on the branch before this work).
Ticket `factory/tickets/TESTOPS-31.md`, feature F1, autonomy `build`.

## Verdict — build complete

The Product Owner's complaint was real and the finding behind it was a false positive. Two scenarios
in `QuestionSuggestions.feature` assert different lists and were declared duplicates because the
analyser compared step *words* only. The signature now carries the data, `assertion_text` states
what the list is, and re-running on `demo-service` drops exactly that one claim: **18 → 17**. The nine
surviving pairs are identical down to their rows, so the fix is not "stop reporting duplicates".

## What changed

- `testops/extract/gherkin.py`
  - `Step` carries `table` and `doc_string`; `Step.assertion_text` renders the step's words with its
    data (`the suggestions list should be: What is Reqnroll?`), and `Step.signature_part` puts the
    same data in the scenario signature.
  - `Scenario.signature` uses `signature_part`, and includes an outline's `Examples` rows: they are
    test data for the same reason a step's table is.
  - `normalise()` no longer parameterises digits. `12 questions` and `3 questions` are different
    test data.
  - The parser reads tables and `"""` doc strings instead of skipping them. The old comment
    ("doc strings and tables inside steps carry no extra weight for this analysis") is replaced by
    the reason they are now read. Blank lines and `#` inside a doc string stay content.
  - `render_table()` renders one-column tables as their values and multi-column tables with their
    column names (`votes: 0; asked at: now; asked by: Marvin`); a ragged table falls back to every
    row so no cell is dropped.
- `testops/analysers/duplication.py` — 2.1.0 → **2.2.0**
  - `assertion_text` is `assertion.assertion_text`: a claim now states the table. No claim's
    assertion can end at "should be".
  - `_assertion_phrase` (the statement's quote) carries the data too.
  - `established_by` says the match includes tables and doc strings.
- `testops/web/app.py` — `quoted_assertion` accepts the stored assertion when the file line is a
  prefix of it, so a table-bearing paragraph still gets the file's `Then`/`And` keyword.
- `tests/test_duplication_tables.py` (new, 16 cases) — the pair pinned both ways, doc strings,
  digits, examples, an identical pair still a duplicate, old stored text, rendering guards.
- `tests/test_duplication_v2.py`, `tests/test_action_prose.py` — corpus counts 18 → 17, with the
  reason recorded in the module docstring. Nothing else in those tests moved.

## Re-run on demo-service (AC3)

Method: the real `run_duplication` writes 17 claims to a throwaway store
(`tests/test_duplication_v2.py`, `test_duplication_tables.py::test_rerun_counts_before_and_after_*`).
The before/after count below is the same corpus parsed twice: "before" is the 2.1.0 signature (step
words, digits parameterised), "after" is the working tree's.

| | duplicated signatures | scenarios in them | claims |
|---|---|---|---|
| before | 10 | 28 | **18** |
| after | 9 | 26 | **17** |

Per old group:

| pair | scenarios | survives? | what differed |
|---|---|---|---|
| Authentication | API:6, Controller:5, WebUI:6 | yes | nothing — no tables, same words |
| Home (welcome) | API:6, Controller:5, WebUI:6 | yes | nothing — no tables |
| Home (user name) | API:12, Controller:11, WebUI:12 | yes | nothing — no tables |
| Home (latest question) | API:19, Controller:18, WebUI:19 | yes | nothing — the `Given` table is identical in all three |
| Home (latest 10) | API:26, Controller:25, WebUI:26 | yes | nothing — no tables |
| AskingQuestions (posted) | API:6, Controller:5, WebUI:6 | yes | nothing — both tables identical in all three |
| AskingQuestions (anonymous) | API:18, Controller:17, WebUI:18 | yes | nothing — no tables |
| AskingQuestions (empty content) | API:25, WebUI:25 | yes | nothing — same step table and same `Examples` rows |
| Registration | API:12, Controller:11, WebUI:12 | yes | nothing — no tables |
| **QuestionSuggestions** | Controller:**8**, Controller:**29** | **no** | **Given table:** `:8` has 2 rows (`What is Reqnroll?`, `What is Cucumber?`); `:29` has 3 rows over 3 columns. **Then table:** `:8` asserts `What is Reqnroll?`; `:29` asserts `What is Reqnroll?`, `Question 2`, `Question 3` |

The resolved claim was the one the Product Owner read: `QuestionSuggestions.feature:39` (the `Then`
in the scenario at line 29), which had been told it repeated `:17` (the `Then` in the outline at
line 8). Its assertion now reads
`the suggestions list should be: What is Reqnroll?, Question 2, Question 3`.

Removing digit parameterisation flooded nothing: the only count change on the corpus is the one

above, and the level-fitness corpus is separately pinned at 94/90/1/1/2.

## Acceptance criteria

- AC1 — done. Table rows and doc-string text are in `Scenario.signature`; outline examples too.
  Pinned by `test_scenarios_that_differ_only_in_table_rows_are_not_duplicates`,
  `test_doc_strings_are_part_of_the_signature`,
  `test_outline_examples_are_part_of_the_signature`,
  `test_digits_in_step_text_are_not_parameterised`.
- AC2 — done. `assertion_text` is `step: data`; the statement quotes the same. Pinned by
  `test_the_assertion_carries_the_table_so_it_never_ends_at_should_be` and
  `test_the_demo-service_claims_never_stop_at_should_be`. For the `demo-service` claims, the one whose
  step already contains a colon (`the home page main message should be: "Welcome to DemoService!"`)
  is unchanged and still correct; no demo-service claim asserts a table, so the corpus half of AC2 is
  covered by the synthetic cases.
- AC3 — done, above. Pinned by `test_rerun_counts_before_and_after_and_names_what_resolved`.
- AC4 — done. `test_the_pair_the_product_owner_opened_now_asserts_differently` and
  `test_the_identical_pair_in_the_corpus_is_still_a_duplicate` (AskingQuestions: one claim per
  non-reference copy, 2 claims among 3 identical scenarios); `test_a_genuinely_identical_pair_is_still_a_duplicate`.
- AC5 — done. No migration or rewrite path touches stored claims; the analyser version moves to
  2.2.0 and only new runs carry it. `test_an_older_run_keeps_its_stored_text` stores a 2.1.0 claim
  with the old text and reads it back unchanged; `test_a_v1_duplication_case_...` still passes.
- AC6 — done. `test_the_corpus_still_carries_the_verdicts_the_ticket_pins`: 94 claims, 90 distinct,
  1 unplaced, 1 gap, 2 review.

## Verification

    env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
      .venv/Scripts/python.exe -m pytest -q
    => 357 passed

Baseline before the change was 341 passed; the 16 new cases are `tests/test_duplication_tables.py`.

## Residual (not defects, recorded so a reviewer can decide)

- A `Scenario Outline`'s `Examples` are now part of the signature. The ticket's AC1 names step tables
  and doc strings; examples are the same kind of test data and leaving them out would have kept the
  identical false positive alive for two outlines with different rows. The corpus counts above are
  with examples included.
- Step data is rendered, not parsed into structure: a cell whose text differs only in punctuation
  still normalises to the same signature. That is the same tolerance step wording already has.
