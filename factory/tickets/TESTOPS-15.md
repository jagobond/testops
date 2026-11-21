---
id: TESTOPS-15
title: Make the floor real — the suite runs on 3.11 in CI
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-14
---

# TESTOPS-15 — Continuous integration

## Why

TESTOPS-13 fixed an f-string that made the app unimportable on the interpreter that serves it, and
added a guard. The reviewer then showed what the guard does not cover: `from itertools import batched`
compiles cleanly on 3.11 and dies at runtime, past both sides of the guard. The guard protects the
construct, not the floor.

Meanwhile the suite only runs on 3.11 when a person remembers to point pytest at a scratch venv. That is
not a property of the repository; it is a property of the Lead's memory.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A GitHub Actions workflow runs on every push and pull request to `main` and `feature/*`, with a matrix over Python 3.11 and 3.12. |
| AC2 | It installs the package with dev extras and runs the same command a developer runs locally; a green CI run means the suites are green on both interpreters, not that a subset passed. |
| AC3 | The 3.11 job imports the app and serves one real case page from the store fixture — the runtime check the compile guard cannot give — and fails if the page does not render. |
| AC4 | A failure in CI is visible without opening the Actions tab: the PR body or a status line names the failing interpreter. |
| AC5 | The workflow is written so a private repository does not burn minutes silently: it runs once per push (not per commit) with `concurrency` cancelling superseded runs, and the report states the minutes a typical run costs. |
| AC6 | No product code changes. If a workflow cannot express something, say so rather than weakening a test. |
| AC7 | The report includes the real run URL and the actual output of the first green run on both interpreters. |

## Notes

- Actions is free for private repos up to the monthly minute allowance; a 2-job matrix at ~1 minute each
  is negligible. State the number anyway — the Lead is cost-conscious and will ask.
- If secrets are needed for anything (they should not be), do not commit any. Never print a token.
