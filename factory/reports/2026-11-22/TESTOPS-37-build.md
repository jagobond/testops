# TESTOPS-37 — build report

Verdict: **decisions are safe to use.** A resolved or false-positive decision stops the next run
over the same evidence from raising the same finding, and reopening puts it back. Both directions
are now proven end to end over the real pipeline, on both analysers, and each of the three
suppression gates is covered by a test that fails when that gate is deleted.

One criterion did not hold as written and is reported, not fixed: AC4 says a moved line should yield
a different fingerprint. The product deliberately does the opposite. Details under "AC4".

No product code changed. The commit adds one test module and this report.

## What changed

| File | Change |
|------|--------|
| `tests/test_decision_survives.py` | 8 tests: the end-to-end decide/rerun/reopen/rerun cycle, one test per suppression gate, the fingerprint contract, and the case page's reopening promise checked against the store. |
| `factory/reports/2026-11-22/TESTOPS-37-build.md` | This report. |

## AC1 and AC2 — the decision survives, and reopening undoes it

`test_a_decided_finding_is_not_raised_by_the_next_run_and_reopening_brings_it_back` drives
`pipeline.run_level_fitness` over the fixture repository and a throwaway store:

1. run one raises two cases, one per actionable assertion;
2. the first case is resolved ("checked by hand; covered elsewhere") through `cases.set_state`,
   exactly as the Decision control does;
3. run two, over the same commit: the claim is still analysed, still `gap`, and its fingerprint is
   still the one the decision named — and it raised no case and no finding. The quiet is the
   suppression, not a changed verdict, because a changed verdict would have moved the fingerprint
   too and the test asserts that it did not;
4. the case is reopened; the suppression row is gone;
5. run three: the same fingerprint is raised again, and the run has two cases again.

The other case in each run is deliberately left undecided, so the test also proves a decision
affects one case and not its neighbour.

## AC3 — all three gates, proven by deleting each one

Each gate has its own test. `pipeline.py` was edited to delete exactly one gate at a time, the
module was run, and the file restored (both gates 2 and 3 leave the gate at line 101 as a backstop,
so an end-to-end test alone cannot see them — that is why the two case-loop tests assert on the
attempted write: the case row is never even inserted).

| Gate deleted | Tests failed |
|---|---|
| `_emit` (`pipeline.py:101`) | `test_the_emit_gate_refuses_a_suppressed_fingerprint` — and only that test |
| duplication case loop (`pipeline.py:246`) | `test_the_duplication_case_gate_never_even_writes_the_suppressed_case` — and only that test |
| level-fitness case loop (`pipeline.py:405`) | `test_the_levels_case_gate_never_even_writes_the_suppressed_case` — and only that test |

All three restorations were byte-identical (`git status` showed only the new test file). Each gate
is live and each is individually observed.

Worth stating plainly: the three gates are defence in depth, and the end-to-end cycle passes with
either case-loop gate removed because `_emit` catches the finding. That redundancy is not a defect,
but it is why "the end-to-end test is green" would have been too weak a proof on its own.

## AC4 — the fingerprint: what actually holds

Two facts are now pinned:

- the same assertion, in the same file, at the same commit, gets the same fingerprint across runs
  (`test_the_same_assertion_at_the_same_commit_gets_the_same_fingerprint_across_runs`), and it is
  the fingerprint stored on the finding row the decision was recorded against;
- the same assertion words in a different scenario are a different fingerprint
  (`test_the_same_words_in_another_scenario_are_a_different_fingerprint`).

**The deviation.** AC4 also asks that "a moved line yields a different one". It does not, and the
product does this on purpose: `level_fitness.py:674` builds the identity from the scenario
reference, the interaction and the assertion's words, and comments "never its line, so reformatting
the file does not resurrect a judged case." The duplication analyser is the same — its evidence key
is scenario name plus normalised signature, neither of which contains a line. Deleting or adding a
line above an assertion leaves the fingerprint untouched. The test
`test_moving_the_assertion_down_the_file_keeps_its_fingerprint` demonstrates the line really moved
and the fingerprint did not, so this is recorded behaviour rather than an assumption.

Which one is right is a product decision, and per AC6 I have not made it in this ticket. What I can
say is that the behaviour as implemented is the one the Decision control needs: a fingerprint that
moved with the line would resurrect every decision about a file whenever anyone reformatted it, and
would make the Product Owner re-decide the same finding over a whitespace change. The ticket's
words, taken literally, would make decisions less durable. If the Lead wants line identity instead,
that is a change to the analysers and a new ticket.

Also worth knowing before the Product Owner relies on this: the subject is the file path plus the
scenario name, so moving an assertion to a *different feature file* (or renaming the scenario) does
produce a new fingerprint and the old decision will not cover it. Move-within-a-scenario is safe;
move-across-files is a new case.

## AC5 — the case page's claim, checked

The decided case page says: "Reopening deletes the suppression for this case, so the next run raises
it again. No other case is affected." `test_the_case_page_promise_that_reopening_makes_it_report_again_holds`
reads that sentence from the rendered page, reopens the case, checks the page no longer says the
finding is hidden from future runs, re-runs, and asserts the finding is back — while the undecided
case was raised throughout. The page's sentence and the store's behaviour agree.

## AC6 — no behaviour change

`testops/` is untouched. `git diff --stat` on product code is empty.

## Test suite

```
env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1 .venv/Scripts/python.exe -m pytest -q
417 passed in 66.94s
```

Eight new tests; the previously passing 409 still pass.

## Are decisions safe to use?

Yes, on the evidence above, for both analysers: a decision recorded on a case stops the next run
re-raising that finding over the same evidence, and reopening reverses it. The one limit is the
fingerprint's subject — a finding whose scenario is renamed or moved to another feature file will
come back as a new case, which is the conservative direction (you are asked again) rather than the
dangerous one (silence you did not ask for).
