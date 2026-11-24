# TESTOPS-60 - The unplaced section: grouped, folded, and structurally anchored

Worktree: `C:/Users/Chester/Projects/testops-t60`, branch
`factory/testops-60-unplaced-volume`. TESTOPS-57's review (`## Zero and many`, `## Three sharpest
concerns`) was read from the `testops-t57` worktree; it is not present in this one. Store copy
built under `tmp_path` in tests; the live store was never opened and port 8791 never contacted.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Met. `queries.unplaced_claims` classifies every claim into `no-binding-match`, `no-patterns` or `other`; `queries.unplaced_groups` buckets them in that fixed order and drops empty groups. The page renders one `<h3 class="unplaced-group">` per group with its count, then a `<p class="unplaced-common">` sentence saying what its steps share. At 351 claims the reader sees two headings and two counts before any row. |
| AC2 | Met. `UNPLACED_PREVIEW = 20` per group, stated on the page. Up to 20 entries render; the rest go into a collapsed `<details>` whose summary and a preceding line both give the exact number folded ("20 of 351 shown in this group; the other 331 are folded below"), plus how to reach any entry (`#unplaced-claim-<id>`). Nothing is dropped. Tested at 0, 1, 19, 20, 21 and 500. |
| AC3 | Met. The reason clause "Why they were not assessed: no binding matches these words." appears exactly once per group; entries carry only the step's words and its nearest patterns. A uniform "other" reason is likewise stated once per group; only a genuinely mixed group states reasons per entry. |
| AC4 | Met. Entries are `<li id="unplaced-claim-<claim_id>">`. A test renders five claims, deletes the second from the store copy, re-renders, and proves every surviving anchor still resolves to the same words. The old ordinal form survives as `<a class="anchor-legacy" id="unplaced-<n>" href="#unplaced-claim-<id>">`, so an old fragment still lands on its entry. |
| AC5 | Met and pinned. A snapshot with no binding observations puts every claim in the `no-patterns` group: the page says the run declared no patterns and that no nearest patterns are claimed, and the test asserts the nearest-pattern phrases are absent. |
| AC6 | Met. `846 passed, 2 skipped` (full suite). Contract P20 updated to the new entry marker, same promise: section exists, count equals entries, soft badge present, hot absent, banned phrases absent. Case-page goldens byte-identical (golden tests green). |

## Changed files

- `testops/queries.py` - group constants, `group`/`reason` on each entry, `unplaced_groups`.
- `testops/web/app.py` - grouped renderer, per-group copy, disclosure at 20, structural anchors.
- `tests/test_unplaced_section.py` - rewritten and extended: AC1-AC6 coverage, threshold
  parametrisation, pruning test, empty-patterns test, per-group count agreement.
- `tests/contracts/test_page_contracts.py` - P20 entry selector follows the structural id.

## Notes

- Group counts come from the same list that renders the entries, and the total count from
  `len(entries)`, so a group or total count cannot drift from its rows.
- The `other` group exists for claims whose recorded `established_by` is neither of the two known
  reasons; its common sentence says only that the reason differs from the other groups.
