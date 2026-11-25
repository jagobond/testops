# TESTOPS-40 — build report

Verdict: **a decision now says what it covers, and a shifted twin asks again instead of going quiet.**

The case page states the contract in one sentence: one assertion in one scenario, the same
interaction and the same words, in any commit and with any test data; renaming or moving the
scenario, or adding or removing an identical assertion in it, asks you again.

The behavioural fix is in the identity, not in a line: two identical assertions in one scenario now
carry their occurrence count as well as their position (`interaction|words#n@total`), so a scenario
that gains or loses an identical assertion re-keys every occurrence and the decision comes back as a
case to judge. One of these changes product code — `testops/analysers/level_fitness.py`, v0.10.2 →
v0.10.3 — and this ticket is the authorisation for it.

## What changed

| File | Change |
|------|--------|
| `testops/analysers/level_fitness.py` | v0.10.3. Occurrences are counted before the claims are built; the count joins the evidence key only when the words repeat in the scenario. No line, no commit, no data — the three things the key deliberately ignores are unchanged. |
| `testops/web/app.py` | `COVER_SENTENCE`, shown beside the Decision on every case that has a finding, decided or not. |
| `tests/test_decision_cover.py` | 8 tests: the page sentence and the prose lint, the single-sentence rule, commit-insensitivity, data-insensitivity, the twin identity, the ticket's twin case, the mirror case that used to be silent, and a reformat guard. |
| `tests/level_fixtures.py` | `stub_pipeline` takes a `stepdef` so a test can edit the feature between two runs over one store. |
| `tests/fixtures/projects_services/case-page-*.html` | 11 goldens regenerated — see "The byte-identical pages" below. |
| `factory/reports/2026-11-22/TESTOPS-40-build.md` | This report. |

## AC1 / AC4 — the sentence

`COVER_SENTENCE`, on the page in `<p class="quiet">` beside the Decision:

> A decision covers one assertion in one scenario: the same interaction and the same words, in any
> commit and with any test data; renaming or moving the scenario, or adding or removing an identical
> assertion in it, asks you again.

One sentence, 40 words, under the lint's 45. It names the three components of the identity
(scenario, interaction, words), the two things the identity does not hold (commit, test data), the
two edits that re-ask by changing the subject (rename, move) — and, in the same sentence, the twin
resolution AC4 requires. It is shown before a decision as well as after one, because the reader who
decides is the reader who needs the contract.

`test_the_case_page_states_what_a_decision_covers_and_the_page_passes_the_lint` renders a real case
page from the pipeline, reads the sentence off the HTML (not off the module), checks each clause is
present, and runs `testops.web.lint.lint` over the whole page with the assertion text passed as the
quoted step: **no problems**. `test_the_cover_sentence_is_one_sentence` pins one full stop and the
word budget.

## AC2 — the commit and the data are ignored, pinned by tests that fail if that changes

| Test | Pins | Mutation that fails it |
|------|------|------------------------|
| `test_a_decision_is_keyed_on_the_test_not_the_commit` | same words at two commits → equal fingerprints | putting `commit` in `base_key` — tried, fails |
| `test_a_decision_is_keyed_on_the_words_not_the_test_data` | a table added under the Given **and** under the assertion → equal fingerprints | putting `step.data` in `base_key` — tried, fails |

The commit is not in the fingerprint and the ticket forbids putting it there: a decision would
re-ask on every deploy. The data table is not in it either, and that is now a stated contract rather
than an accident.

## AC3 — the twin stops being silent

Identity for a scenario with two identical assertions: `I4|…visible label#1@2` and `#2@2`. Alone:
`I4|…visible label`.

- `test_deleting_the_first_twin_asks_again_about_the_second` — the ticket's own case. Decide the
  second (`#2@2`), delete the first, re-run: the survivor is `I4|…visible label`, its fingerprint is
  not the decided one, it is not suppressed, and the run raises a case. The reader is asked again.
- `test_deleting_the_first_twin_never_moves_the_decision_onto_the_survivor` — the silent direction,
  decided first and deleted first. Old key: the survivor inherited `#1` and the decision silently
  covered an assertion nobody judged; the run went quiet. New key: the survivor is `#1@1` while the
  decision names `#1@2`, so the finding returns as a case.

Mutation check: with `level_fitness.py` reverted to the old key, exactly these two tests fail
(`test_two_identical_assertions_carry_their_occurrence_and_the_count` and the mirror case); the other
six pass. With the new key, all eight pass.

`test_reformatting_a_scenario_with_twins_keeps_their_occurrence_keys` adds a comment above both
twins: the lines move, the keys and fingerprints do not. This is the guard against the tempting
line-based fix.

**Honest limit.** The count closes the case the ticket names. A scenario that loses one twin and
gains another in the same edit keeps its count, so the keys are unchanged and a decision still
covers the same position. This follows the ticket's trigger ("when the count changes") and is not
closed here; closing it would need a stable per-assertion identity the source does not carry.

## AC5 — no verdict or claim counts move

The analyser's verdict logic is untouched; only `evidence_key` changed, and only in scenarios with
repeat words. Corpus tests that pin the counts pass unchanged: CotW **94 claims / 90 distinct / 1
unplaced / 1 gap / 2 review**, ReqOverflow **17/17**. Existing runs and snapshots are untouched.

## The byte-identical pages

`tests/test_projects_services.py::test_every_case_page_and_the_indexes_are_byte_identical_after_the_migration`
compared 12 golden case pages with the rendered ones. Every page with a finding now carries the new
sentence, so 11 of 12 goldens changed (`case-page-09` has no finding and no Decision, so it is byte
identical). I regenerated them from the same migrated store and frozen clock; the diff on each file
is the single added `<p>` and nothing else (`git diff --word-diff` reviewed on page 01). The index
and runs pages did not change. The test still proves what it can — the migration leaves the pages
alone — but its baseline is now post-TESTOPS-40 by construction. Recorded here because a regenerated
golden is a weaker proof than a captured-before one, and the reviewer should know.

## Test suite

```
env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1 \
  C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe -m pytest -q
540 passed in 102.14s
```

Run against a copy of the CotW build store in this worktree's gitignored `data/`, so the corpus
tests that need it ran rather than skipped — including the pin for **94 claims / 90 distinct / 1
unplaced / 1 gap / 2 review**, and the ReqOverflow **17/17** assertions. Without that store present
the same tree gives **529 passed, 11 skipped**; the 11 are exactly the corpus tests that read it.

Before this ticket in this worktree: 528 passed, 1 failed (the golden pages), 11 skipped. Eight new
tests. Only the project `.venv` (CPython 3.12.5) was available here; nothing added is version-specific,
and `test_python_floor` still parses the package at the 3.11 floor.

## What the Product Owner should know

- A decision holds across deploys and across changed test data, on purpose. It does not hold across
  a renamed or moved scenario, or when the number of identical assertions in a scenario changes —
  then you are asked again.
- Being asked again is the safe direction; the dangerous direction (silence when the evidence moved)
  now has a test that fails if it returns.
