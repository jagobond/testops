---
id: TESTOPS-37
title: Nothing proves a recorded decision stops the next run reporting the same thing
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-36
---

# TESTOPS-37 — A decision has to survive the next run

## Finding

The Product Owner asked, before using the Decision control on the live pages:

> "It's going to be important to test that to make sure that decisions do actually get recorded and prevent
> future claims. Do we have tests like that for TestOps already?"

**No.** What exists tests the *writing* of a decision, not its *effect*:

- `tests/test_case_page.py` proves the page records a decision, writes a suppression row, and that reopening
  deletes it.
- `tests/test_retention.py` proves pruning will not delete a snapshot a decision rests on.
- `pipeline.py` consults `cases.suppressed(conn, fingerprint)` at three points — and **no test exercises any of
  them**. `git grep suppressed( tests/` returns nothing.

So the store could record decisions faithfully and still re-report every one of them on the next analysis run,
and the suite would stay green. That is the exact failure the Product Owner is holding back to avoid: he believes
he gets one shot at each case, so a decision that silently fails to stick costs him the case.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | An end-to-end test runs an analysis, records a decision on a case, re-runs the analysis over the same commit, and asserts the decided finding is **not** raised as a new case — and that the reason is the suppression, not a changed analyser verdict. |
| AC2 | The same test then reopens the case and re-runs a third time, and asserts the finding **is** raised again. Reversibility is proven, not asserted. |
| AC3 | All three `pipeline.py` suppression gates (lines ~101, ~246, ~405) are covered: one test per gate, or a parametrised test that fails if any gate is removed. Prove the coverage by deleting a gate and watching a test fail. |
| AC4 | Fingerprint stability is pinned: the same assertion in the same file at the same commit yields the same finding fingerprint across runs, and a moved line yields a different one. Suppression depends on it and nothing states it. |
| AC5 | The case page's claim about this is checked against behaviour: whatever the page says reopening does ("the next run reports it again"), a test asserts the store actually does it. |
| AC6 | No behaviour change is expected. If a gate is found broken, report it rather than fixing it silently in this ticket. |

## Notes

- This is the ticket that lets the Product Owner use the Decision control. Until it passes, any decision he records
  is an untested promise.
- Tell him plainly in the build report whether decisions are safe to use yet.
