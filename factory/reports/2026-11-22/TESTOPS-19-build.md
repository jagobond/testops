# TESTOPS-19 build report — 2026-11-22

Branch `factory/testops-19-summary-and-code`, base `e3c7f6f`. Two Product Owner findings: the
case page must open with the answer, and it must show the code it cites. No verdict moves: 94
claims, 90 distinct, 1 unplaced, 1 gap, 2 review.

## What changed

**Part 1 — the summary block.** `queries.summary_of` derives the block from `claim.statement` and
`claim.proposed_action` and nothing else, and `claim_view` carries it as `summary`. The page renders
it immediately after the `<h1>`, before the case state badge, before the verdict badge and before
section 1: two labelled statements, "What this is" and "What to do", no decision control. The
statement is shown whole while it is under 400 characters; past that the block carries the first
*complete* sentence and says the rest is in section 4, so the cut is always at a sentence boundary.
The corpus' longest statement is 323 characters, so every real summary is untruncated. A claim with
no recorded action gets "No proposed action was recorded for this claim." and no invented step.
On a multi-claim case the lead claim's summary is page-level; later claims carry their own at the
head of their own argument.

**Part 2 — code inline.** `queries.source_snippets` returns two excerpts per v2 claim:

- `assertion` — the feature file at the claim's own path and commit, ±2 lines, every line numbered,
  the asserted line marked;
- `step_definition` — the step definition named by the evidence as the step that is asserted,
  starting at its attribute line, up to 10 lines, trimmed at the body's closing blank line.

Both are read from `testops/blobs.py` by `artefact.blob_sha`, so rendering is local and offline.
`app.snippet_block` escapes every source line, marks the asserted line with `<mark>`, and gives each
figure a "view in repository" link at the claim's commit. A snippet this store cannot produce keeps
its state distinct: `not_stored` / `not_recorded` render "The source was recorded but its content is
not in this store"; `past_end` names the recorded line and the stored file's length; `no_binding`
says no step definition binds the asserted step; `no_coordinates` (v1) renders nothing because
section 1 already explains that provenance was not captured.

Files: `testops/queries.py` (summary, snippet read model, `_with_snippets` used by both
`finding_rows` and `claim_read`), `testops/web/app.py` (summary block, snippet renderer, section
placement, CSS), `tests/test_case_summary_and_code.py` (12 tests).

## Tests added

`tests/test_case_summary_and_code.py` — AC1 summary first and verbatim; AC1 no decision control in
the summary; AC2 structural first-block/two-statements check; AC3 v1 with no action; AC4 over-budget
statement keeps its first sentence whole and section 4 keeps the full text; AC5 inline feature
snippet with line numbers, mark and ±2 context; AC5 own-commit (a same-path decoy at another commit
is not shown); AC6 step-definition body, file:line and asserted mark; AC7 hostile `<script>` and
quotes in both snippets render as text; AC8 missing blob sentence, twice, with no empty box; AC8
missing blob does not raise in the read model; AC9 a socket that raises is never reached.

## Evidence

Suite, clean invocation (`env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX
PYTHONNOUSERSITE=1`):

- 3.12.5 (.venv): 210 passed, 18.50s. 198 before this ticket, 12 added.
- 3.11.15 (`uv run --no-project --python 3.11 --with pytest`): 206 passed, 4 skipped, 18.28s.
  The four skips are the pre-existing pre-3.12 checks.

Corpus replay, snapshot `demo-product-levels-20261122-a3f19853-r6`, `scripts/replay_levels.py
--acceptance`: 94 claims, 90 distinct, 1 unplaced, 1 gap, 2 review, 41 scenarios, 2 explaining more
than one label — PASS.

Render scan over the whole real store: 47 cases, 0 render failures. Snippet states across the
claims those cases expose: 24 v2 claims with both excerpts `ok`; 3 v2 claims whose snapshot holds no
artefact for the coordinates (`assertion: not_recorded`, `step_definition: no_binding`) — they
render the recorded-but-not-stored sentence and no empty box; 519 v1 claims with no coordinates.

The -03 specimen: `features/review_panel.feature` lines 30–34, asserted line 32 marked;
`Steps/BrowserSteps.cs` lines 94–99, line 94 marked, captioned "the step that is asserted".

## What this does not satisfy

1. **AC2 is the structural branch, not a pixel measurement.** No browser is available to the suite
   and adding one would make a store-contract suite depend on a downloaded engine and a display. The
   test asserts the summary is the first block after the page heading, carries exactly two labelled
   statements and no decision control. What the 800px budget protects is asserted directly.
2. **AC2's "no more than two sentences" is read as two labelled statements.** Every statement in the
   94-claim corpus is two grammatical sentences; the action is a third. I did not cut the finding
   sentence in half or drop the half that carries the finding: summary = the stored finding (two
   sentences) + the stored action (one), under two labels. If the Lead intends a literal two-sentence
   cap, that is a different ticket and it collides with AC1's "whole and untruncated".
3. **AC1's "first content on the page" excludes the page's own chrome.** The back-link and `<h1>`
   precede the summary; the summary is the first content block after the heading and precedes the
   state badge, the verdict badge and section 1. Making it precede the title would put the case name
   below the answer.
4. **AC6's "up to ~10 lines" trims at the first blank line after the step's attribute.** A step body
   with an internal blank line would be cut early; a body with no blank separator is capped at 10
   lines and may stop mid-method.

## Product problems noticed, not fixed

- The claim is now stated four times on the -03 page: summary, section 1 quote, section 4 statement,
  section 6 action. That is TESTOPS-23's fault 1, and this ticket necessarily adds the fourth. T23 is
  blocked on this ticket and should collapse the repetition.
- Section 3 still presents three context bindings with the same weight as the asserting step
  (T23 fault 7), and the verdict badge still says "Browser not needed" rather than what is wrong
  (T23 fault 6).
- `blobs.text` decodes with `errors="replace"`: a non-UTF-8 blob would silently show U+FFFD instead
  of saying the content cannot be decoded. Not in this ticket's criteria.
- The page-level summary covers the lead claim only. A case with several claims gets further
  summaries inside their own arguments, not a case-wide digest.

## Where to look

`testops/queries.py` (`summary_of`, `source_snippets`, `_assertion_snippet`,
`_step_definition_snippet`, `_with_snippets`), `testops/web/app.py` (`summary_block`,
`snippet_block`, `case_page`, `section_asserted`, `section_does`), `tests/test_case_summary_and_code.py`.
