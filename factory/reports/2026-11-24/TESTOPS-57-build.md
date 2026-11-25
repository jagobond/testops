# TESTOPS-57 build — the claims the tool could not place have a section of their own

Worktree: `C:/Users/<name>/Projects/testops-t57`, branch `factory/testops-57-unplaced-section`.
Store used: the copy in `data/`, opened read-only. The live store was not written and port 8791 was
not contacted.

## What changed

| File | Change |
|------|--------|
| `testops/queries.py` | `unplaced_claims(conn, run_id)` returns the run's `unplaced` claim rows in claim-id order, each with the two nearest declared patterns. `_declared_patterns` reads the snapshot's own `binding:*` observations; `_nearest_patterns` ranks them with the same `difflib.SequenceMatcher` ratio the cucumber-js `explain_unmatched` already uses. |
| `testops/web/app.py` | `unplaced_block(conn, run)` renders the per-run section. It is appended to the run page after the placement summary. The placement summary's cross-reference changed from "each unplaced case" to "each unplaced claim is listed below", because there are no per-claim cases. |
| `tests/test_unplaced_section.py` | New unit tests over a temporary store: anchors and words, count/entry agreement, soft tone, honest wording and banned phrases, and no section when there are no unplaced claims. |
| `tests/contracts/test_page_contracts.py` | P20's skip is replaced by a real assertion against the contract server's own disposable store. |

## Acceptance criteria

| id | result |
|----|--------|
| AC1 | Met. The run page has `<h2>What this run could not place</h2>` and one `<li id="unplaced-<n>">` per claim, each listing the step's words and the two nearest declared patterns. The anchor is the run page's own fragment: `/run/<id>#unplaced-<n>`. Ordering by claim id keeps existing anchors stable when a new claim is appended. |
| AC2 | Met. Every entry renders `verdict_badge({"verdict": "unplaced"})`, which produces `class="badge verdict soft"` (the dashed, dimmed CSS at `app.py:136`). A test asserts the class is present and `badge verdict hot` is absent. This is the first served page that renders the soft tone. |
| AC3 | Met. The sentence's count and the list are both `len(entries)` from the same query result. A test renders 3 then 4 claims on one run and asserts both numbers move together. |
| AC4 | Met. No case-page path changed. `test_every_case_page_and_the_indexes_are_byte_identical_after_the_migration` passed; `test_the_corpus_still_carries_the_verdicts_the_ticket_pins` (94/90/1/1/2) and the ReqOverflow duplication tests (17/17) passed. |
| AC5 | Met. The section says the steps "were not assessed ... not absent from the run", states that "no binding matches these words", and when nearest patterns exist says "none of them matches these words, so no binding places the step". No banned phrases; no resolution or action is invented. |
| AC6 | Met. Contract suite: 37 passed, 2 skipped (the two pre-existing skips); P20 passes. Full suite: **806 passed, 2 skipped** with `PYTHONPATH`, `PYTHONHOME`, `VIRTUAL_ENV` and `CONDA_PREFIX` stripped and `PYTHONNOUSERSITE=1`. |

## Evidence from the store copy

Rendered `run_response` for `restfulbooker-levels-20261123T132456` against `data/testops.db` opened
`mode=ro`:

- 26 `<li id="unplaced-N">` entries, 26 `class="badge verdict soft"` badges, no `hot`.
- The section's count sentence says 26; the placement summary above it also says 26.
- The store still holds 351 `unplaced` claims in total; no rows were written.

## Notes

- `_declared_patterns` reads every `binding:*` observation in the snapshot. That is the same
  population the ecosystem's `explain_unmatched` ranks, so the nearest patterns a page shows months
  later are the ones the run actually came closest to.
- The section is omitted entirely when a run has no unplaced claims; a run with nothing to say gets
  no empty heading.
