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

## Amendment 1 - the review's required fix, and its two notes

The review (`TESTOPS-60-review.md`) approved the build with one required fix and two smaller
notes. This amendment records what changed in response; the acceptance-criteria table above is
left as the record of the first pass.

**Required fix - the legacy ordinal anchors are removed, deliberately.** The review showed that
`#unplaced-<n>` was still positional: deleting the **first** claim of a group re-rendered the
ordinals one position earlier, so `#unplaced-25` silently came to mean what had been claim 26 -
the exact failure AC4 exists to prevent, surviving in the legacy form. The fix is removal, not
repair: no `id="unplaced-<n>"` and no `anchor-legacy` link is rendered any more. The feature is
hours old and nothing outside our own testing has cited an ordinal anchor, so no working link is
lost; a link whose meaning moves with position is worse than a link that no longer exists. This
deliberately supersedes AC4's "the old ordinal form must either keep working or redirect": a
redirect that could not change meaning would need the original ordinal frozen per run, which is
more state than the feature has earned. The structural anchor `#unplaced-claim-<claim_id>` is now
the only anchor. `tests/test_unplaced_section.py` deletes the **first** claim of a group (the
review's case, not the middle-delete the first pass tested), proves every surviving structural
anchor resolves to the same words, and asserts that no ordinal id or legacy link is rendered at
all.

**Note 2 - app.py's opening docstring corrected.** It said the page had "nothing behind a
disclosure" while the unplaced section folds up to 331 rows. It now states what the page does:
the one disclosure is a fold, an over-long list is collapsed behind a stated count, never
silently truncated, and every folded entry keeps a permalink that reveals it.

**Note 3 - contract P20 now asserts the promise the fold creates.** The previous edit was
selector-only. P20 now counts the rendered entries in two halves - rows outside every `<details>`
and rows inside one - and asserts the section's stated total equals their sum, so a count that
agreed only with the visible rows cannot pass. It also asserts a disclosure is actually present
(so the contract cannot silently stop exercising the fold), and that each fold sentence and each
disclosure summary state a number equal to the rows the disclosure holds. Every rendered entry,
folded or shown, must carry the soft tone.

Verification: `tests/test_unplaced_section.py` 16 passed; P20 passed against the contract suite's
own disposable server (69 unplaced claims in the seed, 26 on the run P20 reads, folded); full
suite `846 passed, 2 skipped`. No case-page golden was touched, the live store was never opened
and port 8791 was never contacted.

