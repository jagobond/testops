---
phase: 6
title: The daily loop and the drift check
prereqs: [WO-1..WO-5 complete]
deliverables: [.vscode/tasks.json, scripts/factory_drift.py, docs/port/DAILY-LOOP.md]
gate: one ticket taken from written to merged without leaving VS Code
stop-if: nothing — this phase is small; if it needs a credential you have gone outside scope
---

# WO-6 — The daily loop and the drift check

## Scope

Two small automation files and one page of instructions. This phase closes the port: after it, the workflow is the one in the plan and you stop being the pipeline.

## Do this

**1. `.vscode/tasks.json`** — the local button, so the loop can run in your terminal without a CLI agent:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "factory: build next ticket",
      "type": "shell",
      "command": "python factory/coordinator.py --once",
      "problemMatcher": [],
      "presentation": { "reveal": "always", "panel": "dedicated" }
    },
    {
      "label": "factory: dry run",
      "type": "shell",
      "command": "python factory/coordinator.py --dry-run",
      "problemMatcher": []
    },
    {
      "label": "verify",
      "type": "shell",
      "command": "./scripts/verify.sh",
      "problemMatcher": []
    }
  ]
}
```

**2. `scripts/factory_drift.py`** — plain Python, no model. It answers two questions and exits non-zero when either is bad, so it can run in a weekly job:

- How many commits reached the protected branch in the last 7 days **without** arriving through a `factory/` PR? Any non-zero number means either the division of labour slipped or the factory is being routed around.
- How many days had a `ready` ticket and no factory run? A starving queue and an abandoned factory look identical from the outputs and completely different from here.

Print a short table and a one-line verdict. Use `git log` for the first and the PR list from the API for the second; do not infer either from file timestamps.

**3. `docs/port/DAILY-LOOP.md`** — one page, written for the person doing it:

- Write a ticket with the **Lead** agent. Commit and push.
- Dispatch: leave it to the schedule, or *Run workflow* with the ticket id (Actions panel in VS Code, or the browser, or the phone).
- Read in VS Code: `git fetch`, check out `factory/<ID>`, read the build and review reports. You should not need github.com.
- Judge: merge, or amend on the branch, or close and set the ticket back to `ready` with a note.
- Weekly: run the drift check and read its verdict.

Include the one rule that makes the loop safe: **never rebase a pull request that a human is currently reviewing.** Rebase when the coordinator picks a ticket up, not while someone is reading the diff.

## Acceptance

Paste the raw output:

```bash
python scripts/factory_drift.py; echo "exit=$?"
python factory/coordinator.py --dry-run | head -5
```

Pass requires: the drift script runs, prints both numbers, and exits 0 or 1 with a stated reason — not a traceback. And one real ticket has gone from written to merged with no terminal outside VS Code, which you record in `PROGRESS.md` as the closure evidence.

## When done

Append the final row to `docs/port/PROGRESS.md`, mark the port complete, and state the one thing you would fix first with hindsight.
