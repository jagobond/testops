# PROGRESS — TestOps enterprise port

One row per work order. Written by whichever agent executed it, at the end of that session. A session that reads this file first must be able to resume without asking the operator what has already happened.

## Status

| WO | Title | Status | Date | Evidence |
|---|---|---|---|---|
| 0 | Decisions | not started | — | — |
| 1 | Repo and ground rules | not started | — | — |
| 2 | Devcontainer | not started | — | — |
| 3 | Agent files | not started | — | — |
| 4 | Coordinator | not started | — | — |
| 5 | Workflow | not started | — | — |
| 6 | Daily loop and drift | not started | — | — |

Status values: `not started`, `in progress`, `blocked`, `done`.

## Blocked

Nothing blocked.

## Baselines

The test counts recorded here are the only authority; no plan or work order carries a literal.

| When | Commit | Collected | Passed | Interpreter | Where |
|---|---|---|---|---|---|
| | | | | | |

## Notes carried forward

Append, do not overwrite. Most recent last.

---

## Rules for the agent writing here

**Append only.** Never rewrite an earlier row. A history that gets tidied is a history that cannot be trusted.

**Record commands and their output, not conclusions.** "P1-AC3 passed" is a claim; `./scripts/verify.sh | tail -1` → `1188 passed` is evidence.

**Record what you did not do.** If a check needed a credential you did not have, write that, and write the exact command the person with the credential should run. An unverified check reported as verified is worse than an unrun one.

**One row per session, not per action.** If you stopped halfway through a work order, say where, and set the status to `in progress` or `blocked` — do not mark it `done`.
