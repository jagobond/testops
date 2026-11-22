# TESTOPS-37 review

Reviewer, 2026-11-22. Branch `factory/testops-37-decision-survives`, tree clean. Full suite:
`env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1 .venv/Scripts/python.exe -m pytest -q`
→ **417 passed in 67.62s**. My own six-edit and gate-deletion experiments are reproduced below
from live runs, not taken from the build report.

## Verdict — PASS

The Decision control now has real proof behind it: a decided finding stays silent through the
edits that should not count (whitespace, comments, data tables, new commits) and comes back loudly
through the edits that do (wording, rename, move), and every one of the three pipeline gates is
individually observed by a test that fails when that gate is deleted.

## Criteria

- **AC1 — HOLDS.** `test_a_decided_finding_is_not_raised_by_the_next_run...` runs the real
  `run_level_fitness` three times over an unchanged commit and, critically, guards the *reason*:
  it asserts the claim was still analysed (same `assertion_text` found in run two's claims), the
  verdict is still `gap`, and `pipeline._fingerprint(...)` still equals the fingerprint the
  decision named (tests/test_decision_survives.py:139-145). A changed verdict or a moved
  fingerprint would fail the test, so silence cannot be explained away.
- **AC2 — HOLDS.** The same test reopens via `cases.set_state(..., "open", ...)`, asserts the
  suppression row is gone, and run three re-raises the same fingerprint with two cases again.
  Reversibility is exercised, not asserted.
- **AC3 — HOLDS.** I deleted each gate myself (see below); each deletion failed exactly one test
  and it was the right one. The two case-gate tests assert on the attempted `INSERT INTO case_`
  via a SQL trace, which is the right observation: the `_emit` backstop would otherwise mask a
  deleted case gate at the row level.
- **AC4 — HOLDS with a reported, deliberate deviation.** The build refuted the criterion as
  written rather than quietly meeting it: the fingerprint deliberately excludes the line
  (`level_fitness.py:674`). Two tests pin what *does* hold: same assertion → same fingerprint
  across runs (and equal to the stored finding's fingerprint), same words in another scenario →
  different fingerprint, and a line really moved in a fixture while the fingerprint stayed put.
- **AC5 — HOLDS.** The test reads the page's exact sentence ("Reopening deletes the suppression
  for this case, so the next run raises it again. No other case is affected."), performs the
  reopen, and proves both halves against the store: the finding returns, the other case was
  raised throughout.
- **AC6 — HOLDS.** `testops/` untouched; the only diff vs `main` is the test module, the build
  report, and this review prompt. The AC4 conflict was reported, not fixed, as AC6 requires.

## What keeps a decision — the six edits

Decided the first raised case (the "citation sits inside a nameable element" assertion in
`the fact sheet is usable with a screen reader`), applied the edit, re-ran over the same stubbed
pipeline. "SILENT" = the decided fingerprint raised nothing AND no new case replaced it;
"CAME BACK" = the old fingerprint stays silent but a new case with a new fingerprint is raised,
which is the loud, acceptable outcome.

| # | Edit (as a user would do it) | Result |
|---|------------------------------|--------|
| 0 | none (baseline) | SILENT — decision held, 1 case |
| 1 | comment + blank lines added above the assertion (line shifted) | SILENT — decision held, 1 case |
| 2 | assertion wording changed by one word ("sits inside" → "sits within", feature + stepdef) | CAME BACK — old fp silent, 2 cases; the reworded assertion raises a new case |
| 3 | data table added under the scenario's Given | SILENT — decision held, 1 case |
| 4 | scenario renamed | CAME BACK — old fp silent, 2 cases |
| 5 | scenario moved to another feature file | CAME BACK — old fp silent, 2 cases |
| 6 | analysed a different commit | SILENT — decision held, 1 case (see concern 1) |

This is the right shape: edits that do not change the evidence identity keep the decision quiet;
edits that change the identity bring the finding back as a fresh case you must judge again.
No edit made a decision fail *silently in the dangerous direction* (evidence changed but stayed
quiet) — except the two cases named under concerns.

## Gate deletion

Each deletion was made in `testops/pipeline.py`, the module run alone, then restored with
`git checkout -- testops/pipeline.py`. `git status --porcelain` was empty after every
restoration — all three restorations byte-identical.

| Gate deleted | Tests failed |
|---|---|
| `_emit` (line 101) | `test_the_emit_gate_refuses_a_suppressed_fingerprint` (line 225) only |
| duplication case loop (line 246) | `test_the_duplication_case_gate_never_even_writes_the_suppressed_case` (line 267) only |
| level-fitness case loop (line 405) | `test_the_levels_case_gate_never_even_writes_the_suppressed_case` (line 302) only |

Exactly one failure per deletion, always the right test. Note the redundancy is real: deleting
either case-loop gate leaves the end-to-end cycle green because `_emit` still catches the finding.
That is defence in depth working as designed, and it is exactly why the build added the
trace-based tests instead of relying on the end-to-end test.

## Three sharpest concerns

1. **A decision ignores the commit entirely.** Edit 6: the same assertion in the same scenario,
   analysed against a different commit, stays silent. Nothing in the fingerprint or the store keys
   on the commit, and no test documents this. It may be the intended product meaning (the finding
   is about the test, not the code) — but today the Product Owner could decide a finding on last
   month's snapshot and unknowingly silence it against today's. At minimum this behaviour should
   be pinned by a test and stated on the case page, so it is a known contract rather than an
   accident.
2. **Duplicate identical assertions in one scenario are disambiguated by occurrence order, not
   line.** `level_fitness` builds the evidence key as `interaction|words#n`, where `n` counts
   identical assertions within the scenario. Two identical assertions therefore get *different*
   fingerprints (good — a decision on one does not silence its twin), but the disambiguation is
   positional: if the first of two identical assertions is deleted, the survivor's index shifts
   from `#2` to `#1` and the decision recorded against it stops covering it — silently. This is
   the one place where the ticket's line-insensitivity intuition would actually have been the
   safer key, and it is the counter-example the build report's "reformatting is safe" claim does
   not cover.
3. **Data-table content is invisible to the identity.** Edit 3: adding or changing a scenario's
   test data table leaves the fingerprint untouched, so a decided finding stays silent even
   though the scenario's inputs changed underneath the decision. Defensible (the assertion itself
   did not change) but the same "silently held" direction as concern 1, and likewise undocumented.
   A sentence on the case page telling the Product Owner what a decision covers — same scenario,
   same interaction, same assertion words, any commit, any data — would close concerns 1 and 3.

## Bottom line

Decisions are safe to use. The promise the Product Owner cares about — judge once, not asked
again — is now proven over the real pipeline on both analysers, and it reverses. The concerns
above are contract-documentation issues, not broken gates; none of them silences a finding that
changed in a way the Product Owner would expect to be re-asked about, except in the two narrow
cases (new commit, changed test data) which should be written down before he relies on them.
