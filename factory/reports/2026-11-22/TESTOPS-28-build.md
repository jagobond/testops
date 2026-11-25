# TESTOPS-28 build report — 2026-11-22

Branch `factory/testops-27-action-line`, based on `ab3c436`. Ticket: `factory/tickets/TESTOPS-28.md`
(supersedes TESTOPS-27). Feature F1.

## Verdict — build complete

The classification is gone. `action_line` returns the whole stored action, split at its semicolons
into sentences, and removes nothing. The instruction vocabulary, the continuation openers and
`second_half_is_instruction` are deleted with the rest of that apparatus — not left dormant. The 94
real actions render in full, the page is visibly wordier, no T26 lint fires, and the verdicts are
unchanged.

## What changed

- `testops/web/app.py` — deleted `INSTRUCTION_VERBS`, `ORDER_CUES`, `CONTINUATION_OPENERS`,
  `IRREGULAR_FORMS`, `_BE`, `_VOWELS`, `_WORD`, `_inflections`, `INSTRUCTION_FORMS`, `_words`,
  `_passive_without_obligation`, `instruction_hits`, `descriptive_participles`, `order_cues` and
  `second_half_is_instruction`. Added `_sentences` (split at `;` only) and rewrote `action_line`
  as: refer to the step, split, capitalise each clause, one full stop each, join. The comment above
  it now records the decision and the three leaks that forced it, so the next person does not
  rebuild a word list.
- `tests/test_action_line.py` — rewritten for the new contract. The property test over the
  reviewer's 15 probes (and 8 further shapes both passes recorded) asserts every content word of
  the stored action appears in the rendered line, in order, for all 23.
- `tests/test_case_scan.py` — the corpus floor (`≥40 characters kept`) is replaced by the stronger
  statement it was approximating: every stored action on the real run renders *whole* (94/94), the
  step reference being the only shortening. The TESTOPS-27 drop-count test is deleted with the rule
  it measured; the verdict-count check stays, pinned to the run id the ticket names rather than
  picked by `ORDER BY COUNT(*) DESC` (the fragility the first review flagged: a re-run of the
  analyser had already added newer 94-claim runs to the store).

## Acceptance criteria

| id | result |
|----|--------|
| AC1 | Met. `action_line` returns the full stored action, sentence-split, nothing removed. `tests/test_action_line.py::test_every_content_word_of_the_stored_action_reaches_the_page` runs the property over 23 hand-written actions: the reviewer's 15 probes plus 8 more shapes from the two passes. Asserts no content word missing and that the input's content words are a *subsequence* of the output, so nothing is reordered or dropped. |
| AC2 | Met in product and test code: `git grep -n 'INSTRUCTION_VERBS\|CONTINUATION_OPENERS\|second_half_is_instruction' -- testops tests scripts` returns nothing (exit 1). See "For the Lead" below for the two historical report files that still name them. |
| AC3 | Met, and deliberately visible. Every one of the 94 actions grew; total rendered action text went from 3,733 to 8,659 characters (+132%). Median action 38 → 90 characters. No action lost a character it had. Examples and the requested scan block below. |
| AC4 | No firings. The T26 no-repeat lint (`lint.repeated_clause`, 6-word clause) fires 0 times across the 94 scan blocks of `demo-product-levels-20261122T011316`, as does the plain-English lint. Nothing to record as a follow-up finding; the lint is untouched, and no cut was reintroduced to appease it (it had nothing to complain about). Measured directly against the block `argument_block` builds, and again through the page in `test_the_stored_demo-product_corpus_keeps_its_verdicts_and_passes_the_lint`, which passes. |
| AC5 | Met. Sentence-splitting, capitalisation and full stops only. Two sentences with one full stop each, never a run-on; three-clause actions become three sentences. `action_line` with no semicolon returns the stored string unchanged. |
| AC6 | Met. Verdicts on the pinned run: 94 claims — 90 distinct, 1 unplaced, 1 gap, 2 review. Suite green on both interpreters (below). |

## The property, and the wordiness it buys

The property test's corpus:

- 8 probes from the first review pass
- 7 more from the second pass, including the three the word list dropped:
  `the duplicate is deletable`, `the second one can go`,
  `the copy would be deleted by whoever owns it`
- 8 further shapes the second pass recorded (`there is no need for this copy`,
  `both copies are unnecessary`, `one of the copies should go`,
  `getting rid of the duplicate is advisable`, `it requires deleting`,
  `is supposed to be removed`, `had better be merged`, `is bound to merge`)

For each: every content word of `head; probe.` is present in the rendered line, in order, with no
semicolon left and a full stop at the end. There is no rule left for a tail to walk past.

Wordiness, measured from the store's own rows (pinned run, 94 claims):

```
old length: min 38  median 38  max 120   total 3733
new length: min 90  median 90  max 189   total 8659
actions that grew: 94 of 94
```

The two shapes, on real claims:

```
OLD: No change: keep this step where it is.
NEW: No change: keep this step where it is. This level is the cheapest one that establishes it.
```

```
OLD: Move this step into a test that drives a browser, or delete it.
NEW: Move this step into a test that drives a browser, or delete it. At this level nothing
     establishes what it asserts.
```

This is the trade the ticket asks for: the analyser wrote the tail, so the reader sees the tail.
The fix belongs to the analyser's `proposed_action` strings in a follow-up ticket, not here.

## The rendered scan block, `case-demo-product-levels-20261122T011316-03`

Reader text (what the Lead sees on the page):

```
Checked, but over-tested for what it asserts

The test asserts the step "Then each fact's data-fact-id is the same on both loads", but the page
the server sends settles it, and the test drives a browser to read it.

What to do   Rewrite this step to call the HTTP client instead of the browser. The response decides
             everything the browser is being used for.
```

Raw block as served:

```html
<section class="scan"><p class="judgement"><strong class="verdict hot">Checked, but over-tested for what it asserts</strong></p><p class="wrong">The test asserts the step <code class="ident">Then each fact&#x27;s data-fact-id is the same on both loads</code>, but the page the server sends settles it, and the test drives a browser to read it.</p><p class="action"><span class="act">What to do</span> Rewrite this step to call the <code class="ident">HTTP client</code> instead of the browser. The response decides everything the browser is being used for.</p></section>
```

The action line is now two sentences: the instruction, then the analyser's restatement of why. It
reads as wordy and repetitive — that is intended, and it is the visible cost of never dropping a
clause.

## Verification

Both runs with `PYTHONPATH`, `PYTHONHOME`, `VIRTUAL_ENV` and `CONDA_PREFIX` stripped and
`PYTHONNOUSERSITE=1`:

```
.venv (Python 3.12.5)       315 passed
Python 3.11.15              311 passed, 4 skipped
```

The 3.11 run used a throwaway 3.11 venv with only `pytest` installed (the project has no runtime
dependencies); the 4 skips are the interpreter-specific cases in `test_python_floor.py` that only
apply above 3.11, not failures. The first 3.11 attempt borrowed the 3.12 `site-packages` via
`PYTHONPATH`; `test_collection_gate` failed there only because that test deliberately spawns a
clean-environment subprocess, so the borrowed pytest disappeared. The throwaway venv removes that
artefact.

Verdicts read from the store, not from test output: `demo-product-levels-20261122T011316` → 94 claims,
`{'distinct': 90, 'gap': 1, 'review': 2, 'unplaced': 1}`.

## For the Lead

1. **AC2's `git grep` is clean in code, not in history.** The only remaining mentions of the
   deleted names are `factory/reports/2026-11-22/TESTOPS-27-build.md` and
   `factory/reports/2026-11-22/TESTOPS-27-review.md`, which describe the design this ticket
   superseded. They are historical evidence of what was built and reviewed; I did not rewrite them,
   because falsifying a past report is worse than a grep hit. If the Lead reads AC2 literally, those
   two files are the gap, and deleting the sentences that explain the superseded rule is a Lead
   decision, not a builder's.
2. **Another ticket's work appeared and vanished in this worktree during the build.**
   `testops/cli.py`, `testops/retention.py`, `tests/test_retention.py` (TESTOPS-24's retention
   feature) were being written by another process while this ticket was built — `cli.py` changed
   under a suite run at 11:13, and one full-suite run flaked on `test_isolation.py` for exactly
   that reason. By the time this report was written that process had removed its own work: the
   files are gone and `cli.py` is clean, and `git status` shows only TESTOPS-28's files. The
   commit below contains only TESTOPS-28's files, and the test counts quoted above are from the
   final, clean tree. Nothing of TESTOPS-24 is staged, committed or lost here.
3. **Redundancy is now the analyser's problem.** The 90 `No change: keep … where it is. This level
   is the cheapest one that establishes it.` actions read twice-stated. A follow-up F1 ticket that
   rewrites the analyser's `proposed_action` strings so the head already carries the reason would
   halve the action text and leave this renderer untouched.
