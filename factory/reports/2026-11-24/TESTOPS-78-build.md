# TESTOPS-78 build — no intent, no accusation; no page, no honesty

2026-11-24, branch `factory/testops-78-near-miss`, worktree
`C:/Users/<name>/Projects/testops-t78`. `level_fitness` 0.11 → **0.12**. No store schema change;
no verdict moved except the ones this ticket was written to refuse.

The ticket's review source is `factory/reports/2026-11-24/TESTOPS-72-review-round2.md`. It is not in
this worktree (the TESTOPS-72 branch carries it); it was read at
`C:/Users/<name>/Projects/testops-t72/factory/reports/2026-11-24/TESTOPS-72-review-round2.md`, and
its two concerns are the two holes this build closes.

Suite, from the project `.venv` with `PYTHONPATH`/`PYTHONHOME`/`VIRTUAL_ENV`/`CONDA_PREFIX` stripped
and `PYTHONNOUSERSITE=1`: **1234 passed, 2 skipped** (179.5 s). Contract suite alone
(`pytest tests/contracts`): **37 passed, 2 skipped** (14.0 s). `tests/test_product_evidence.py` is
now 22 tests (was 17); five are new. No golden changed (see AC7).

## What changed

| file | change |
|---|---|
| `testops/analysers/level_fitness.py` | `_INTENT_FORMS` is a pinned literal table of English forms (73 entries, 19 verbs); `_INTENT_METHODS`, `_intent_forms` and `_intent_forms_by_word` are gone, so `getted`/`readed` cannot exist. `product_match` returns `intent_known`; `verb_agrees` is false when no act is recognised. `_product_record` refuses a bare-noun match with no intent as a near miss (`near_miss_kind: "no_intent"`) and records route, shared word and an actionable reason; every record carries `near_miss_kind` and `intent_known`. Version 0.12. |
| `testops/queries.py` | `product_evidence` now counts near misses, split `verb differs` / `no intent`, never folded into repeats or unconsulted. New `near_miss_claims(conn, run_id, scenarios=None)` and `case_for_scenario(conn, run_id)` read the refusals and the case page of their scenario from stored rows. |
| `testops/web/app.py` | `near_miss_sentence()` — one wording for route + shared word + why it is not a repeat, used by the claim block and the new pages. `product_block` prints the AC3 count line. New `near_miss_block` (run page) lists every refusal with its sentence and links to its scenario's case page where one exists; new `near_miss_case_block` shows the refusals of a case's own scenarios on that case page. |
| `testops/pipeline.py` | The run's stats record `product_near_miss`, so the store says the rule looked even before a page is rendered. |
| `tests/test_product_evidence.py` | Five new tests: the pinned table, the reviewer's verb-less probe, the precision pin, the run-page count line, and run-page + case-page reachability. |

## Criterion by criterion

| id | what was done, and the evidence |
|----|--------------------------------|
| AC1 | `test_a_verb_less_assertion_shares_a_noun_and_is_refused_not_counted`: `booking details present` against `GET /booking/{id}` and `DELETE /booking/{id}` (six surfaces, as in the review) → verdict `distinct`, state `zero`, `near_miss: true`, `near_miss_kind: "no_intent"`, `assertion_verb: ""`, `verb_agrees: false`, route `DELETE /booking/{id}`, word `booking`. The record's reason: *"…the assertion names no act this rule recognises (none of get, create, update or delete), so a shared noun alone is not evidence that the product already does this - it is not counted as a repeat. Name the act the assertion checks, or check this one by hand"*. Pinned. |
| AC2 | `test_the_intent_table_is_an_explicit_list_and_holds_no_generated_form` compares `level_fitness._INTENT_FORMS` to a literal in the test, and asserts `getted`, `readed`, `seed`, `newed` are absent. The generator is deleted, not backed by a list. |
| AC3 | `test_the_run_page_counts_the_claims_it_refused_separately`: a real pipeline run with one repeat and one verb-less near miss renders, in the product section and separate from the other two counts: **"1 claim shares a noun with a product route but was not counted (verb differs 0 / no intent 1)."** The same test asserts the section does not say "could not be consulted". |
| AC4 | `test_a_near_miss_is_reachable_from_its_run_page_and_from_its_scenarios_case_page`: the run page carries "What the product refused", the claim's words, `DELETE /booking/{id}`, the no-intent reason, an anchor `<li id="near-miss-claim-N">`, and a link `/case/<case>#near-miss-claim-N`. That case page (the sibling finding's) renders the same section and sentence. The count line links to the section on the run page for claims whose scenario raised nothing. |
| AC5 | `test_precision_is_unchanged_on_the_round_2_fixtures`: `New room will be created` against the POST corpus is still `repeats_product`; `A room is created and then the room is displayed` still `repeats_product`; the GET-only creation is still a near miss; the verb-less probe refuses. The existing flip, matched-surface, generic-word, common-share and no-browser tests pass unchanged apart from the flip fixture's wording (below). |
| AC6 | **No snapshot with a `.java` product arm exists in this worktree's store**, so AC7's real-corpus proof cannot be re-established here. `data/testops.db` holds **30 snapshots** (16 cotw, 9 reqoverflow, 5 restfulbooker); `SELECT … FROM artefact WHERE uri LIKE '%.java'` returns **0 rows**, in every role. No download was made and the live store was not opened. The first run whose product arm holds `.java` still owes this three quoted matches and a count; this report states the absence rather than letting the ticket close silently. |
| AC7 | Full suite **1234 passed, 2 skipped**; contracts **37 passed, 2 skipped**. Goldens regenerated deliberately from `tests/fixtures/projects_services/before_v3.db` (copied, migrated v3→v7, `app.age` frozen to "a fixed time ago", exactly as `test_projects_services.py` renders them): **14 pages, all byte-identical** — `index.html`, `runs.html`, `case-page-01.html` … `case-page-12.html`. They are identical because that fixture store predates TESTOPS-72 and carries **no product records**, so there is no near-miss block to add to it; the block is rendered and asserted through the real pipeline by the two new page tests above. |

## The flip fixture, changed deliberately

The flip test's assertion was `the booking confirmation is announced with an accessible name` against
`POST /booking`. Under AC1 that sentence names no act the table knows, so it must now refuse, and the
test would prove nothing. The fixture is now `the booking confirmation is **shown** with an accessible
name` against `GET /booking` / claim `show booking`; the test's property is unchanged — one suite,
two products, the same assertion, and only the product's declaration differs. The round-2 verb-rule
fixtures (`create` → POST) are untouched and still repeat.

## What this does not do

- **An explicit table has a fixed recall.** A sentence using an act nobody listed (`submit`, `post`,
  `publish`) is now a near miss, not a repeat. That is the ticket's rule, and the pinned table makes
  the omission visible rather than generating a plausible-looking form.
- **A near-miss claim still raises no finding.** It is reachable on the run page always, and on the
  case page of its scenario when that scenario raised one; a scenario whose only browser claim is a
  near miss has no case page and is reachable from the run page only.
- **The near-miss count is a count of refusals, not of mistakes.** It says the rule looked and
  declined; it does not say the product has no such route, only that no declared surface settles the
  act the assertion names.
- **AC6 remains outstanding.** 30 snapshots, 0 `.java`; the corpus proof needs a fresh snapshot of a
  Java product, which this build did not fetch.
