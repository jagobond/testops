# TESTOPS-73 build — the case page names what it examined

Worktree `C:/Users/Chester/Projects/testops-t73`, branch `factory/testops-73-source-tags`.
Ticket: `factory/tickets/TESTOPS-73.md`. All work is on that branch; nothing was pushed to `main`.

## What changed

| file | change |
|------|--------|
| `testops/queries.py` | `source_band(conn, row, claims)` — a read model built only from the case's own snapshot: arms, per-role reads, artefact versions, recorded service states, ecosystem record, and any links a claim recorded. No live source and no today's configuration. |
| `testops/web/app.py` | `source_band_block()` renders the band directly after the heading/state line, before the run link and before the claim's scan block. New CSS for tags; dimmed tags are dashed **and** say "not consulted" in words. |
| `tests/test_case_source_band.py` | 10 new tests. |
| `tests/fixtures/projects_services/*.html` | 14 goldens regenerated (12 case pages, index, runs). |

The tag set:

- **Test repository** — links to the assertion's file at the claim's own commit, with the line
  (`.../blob/<claim commit>/<path>#L<line>`). The repository is resolved from the claim's
  coordinates, then from the run's recorded test arm, never from the snapshot tip.
- **Product repository** — link to the repository at the run's recorded product commit
  (`/tree/<commit>`). When an older snapshot recorded the arm but not a commit, the tag links the
  repository and says "the run did not record its commit" instead of inventing one.
- **Jira issue / Azure DevOps work item / Pipeline run / Requirements document** — rendered only
  when a claim records a link for it (`detail["links"]`, `{"kind", "name", "url"}`). A kind with no
  link is not a tag.
- **Unconsulted sources** — a source the analysis *needed* and could not consult is a dimmed tag
  reading "not consulted" with the reason from the snapshot's service state, project assessment or
  registry fallback. A source only *consulted* by the analyser (requirements) is not called a blind
  spot.
- **Product routes** — when the product repository was read but its ecosystem was not recognised,
  a dimmed tag says so with the recorded reason, beside the product tag rather than in a banner.
- One line says an absent tag means the source was not linked to the case, so it was not part of
  the evidence.

## AC evidence

| AC | evidence |
|----|----------|
| AC1 | `test_the_band_opens_the_page_and_links_the_test_file_at_the_claims_commit` asserts the band precedes `<p class="wrong">`; each tag carries kind and source. |
| AC2 | File-at-commit link and product `/tree/<commit>` link pinned; all four linkable kinds rendered in `test_linked_issues_work_items_runs_and_documents_are_tags_with_their_links`; unlinked kind absent and the absence line asserted in `test_a_kind_that_is_not_linked_is_not_a_tag_and_the_band_says_what_an_absence_means`. |
| AC3 | `test_a_needed_source_that_could_not_be_consulted_is_dimmed_with_its_reason`; product-routes blind spot pinned separately; a non-needed source is not named (`test_a_source_the_analysis_did_not_need_is_not_named_as_a_blind_spot`). |
| AC4 | `test_a_case_that_rests_on_test_code_alone_says_so_in_words`: "Assessed against test code only: the product’s routes could not be consulted, because <reason>." — plain prose, no warning class. |
| AC5 | `test_tags_are_keyboard_reachable_and_their_accessible_names_carry_the_kind`: consulted tags are anchors, unconsulted tags are focusable notes (`tabindex="0"`, `role="note"`), accessible names begin with the kind, and "not consulted" is visible text, not colour. |
| AC6 | Contract suite green (37 passed, 2 skipped), including P15 (the case page's opening claim) and P17 (file/commit/line). Goldens regenerated deliberately — see below. |
| AC7 | Full suite green (1142 passed, 2 skipped) and contract suite green. |

## Goldens — what changed

All 14 were regenerated from the same migrated fixture store with the frozen `age()` clock. For
every file, stripping the stylesheet and the `<section class="sources">` element leaves bytes
identical to `HEAD` (checked programmatically for all 14). So:

- `index.html` and `runs.html`: **stylesheet only** — 21 added lines, nothing else.
- `case-page-01` … `case-page-12`: stylesheet plus the band (one long line between the state line
  and the run link). No wording, count, verdict or other markup moved.
- `case-page-06` (reqoverflow, test arm only) is the golden that shows AC4: the dimmed product tag
  and the "assessed against test code only" sentence.
- `case-page-01` shows both repositories as consulted tags.

This is the first ticket whose CSS is shared by every page, so index/runs goldens necessarily
change even though their content did not.

## Test runs

```
env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
  C:/Users/Chester/Projects/testops/.venv/Scripts/python.exe -m pytest -q
1142 passed, 2 skipped in 193.25s

... -m pytest -q tests/contracts
37 passed, 2 skipped
```

Baseline before this ticket in this worktree: 1132 passed, 2 skipped. The 10 new tests are the
band's.

## Isolation

Every test and every regeneration ran against a **copied** store under the pytest/temp directory.
Nothing opened `data/testops.db`, wrote to the live store, or connected to port 8791; the contract
harness built its own seed store and bound port 0 as before.

## Stated limits

- `detail["links"]` is a new, documented seam: no analyser in this build emits a linked issue, work
  item, pipeline run or requirements document yet, so those four tags are pinned by fixture tests
  only. The corpus has no such links, and inventing them from an issue board would be a guess.
- The old golden fixture store records the product arm but no product commit, so its product tags
  link the repository and say the commit was not recorded. The contract seed (restful-booker) does
  record the commit, and its band shows the `/tree/<commit>` link.
- The band links one test file per repository — the first claim that carries coordinates. A case
  whose findings span several files still gets one repository tag, because the unit AC1 names is
  the source, not the file.
