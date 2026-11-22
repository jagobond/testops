---
id: TESTOPS-34
title: A run with no findings is listed as an open case awaiting a decision
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-33
---

# TESTOPS-34 — A case is a finding

## Finding (Product Owner)

> "case-cotw-dup-20261120T194032: I don't know what this is doing here? An open case to tell me there are no
> findings? This seems like a defect."

It is. TESTOPS-22 fixed the *wording* of a quiet run. The structure is still wrong: every analysis run creates a
case, even when it raised nothing, so the case list is padded with things nobody can act on. There are four such
cases in the store now — `case-cotw-dup-20261120T153507`, `case-cotw-dup-20261120T194032`,
`case-cotw-levels-20261121T173120`, `case-cotw-levels-20261121T173223`.

A case exists to carry a decision about a finding. No finding, no case.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A run that raises no findings creates no case. The run itself remains in the store and is visible in a runs view with its counts, commit and what it could not consult. |
| AC2 | The case list shows only cases that carry at least one finding; the four existing empty cases stop appearing, and a test asserts the list query cannot return a case with zero findings. |
| AC3 | The existing empty cases are not deleted from the store: their rows remain (evidence is not destroyed), they are simply not cases. State in the report how a reader reaches the run instead (runs list, or the run id in the URL). |
| AC4 | The quiet-run page TESTOPS-22 built survives as the run's page: same honest text, reached by run id, and a test keeps it. |
| AC5 | Verdicts and claim counts unchanged. |

## Notes

- Do not solve this by hiding rows in the template. The list query is where the rule belongs, so every caller gets
  it.
- If a run has findings but all are suppressed by decisions, that is a case that exists and is closed — different
  from a run that raised nothing. Keep them distinct.
