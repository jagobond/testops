# Prompts for running the port with a VS Code agent

## Setup, once

In the repository, create `docs/port/` and copy these files into it, keeping the names:

```
docs/port/PLAN.md              <- 2026-11-23-TestOps-Enterprise-Port-Plan.md
docs/port/WO-0-Decisions.md
docs/port/WO-1-Repo-and-ground-rules.md
docs/port/WO-2-Devcontainer.md
docs/port/WO-3-Agent-files.md
docs/port/WO-4-Coordinator.md
docs/port/WO-5-Workflow.md
docs/port/WO-6-Daily-loop-and-drift.md
docs/port/PROGRESS.md          <- 2026-11-23-TestOps-Port-PROGRESS-template.md
```

Commit them. `AGENTS.md` already gives `docs/**` to the Lead, so editing this folder needs no ticket.

**Setting.** Use Agent mode, not Ask. The role prompts below assume the agent has `read`, `search`, `edit` and `execute`. Without `execute` it can write files but cannot run an acceptance check, which turns every gate into an opinion.

## How to use these

One work order per session. Never "continue into the next phase" — that is how an agent produces three half-finished phases and a report that reads as complete.

Two habits make the difference:

- **Ask for raw output, not a summary.** Any gate answered with "passed" rather than a pasted command result is unverified, and you cannot tell the difference afterwards.
- **When it goes wrong, stop the session.** Do not correct it mid-run in the same thread. Write the correction into the work order file, then start fresh — a corrective message inside a long session is often ignored in favour of the plan the agent has already started executing.

---

## Prompt 0 — Calibration, before you give it anything

Run this first. It tells you whether the agent understood the document or is about to improvise.

```
Do not edit, create or delete any file. This is a comprehension check only.

Read docs/port/PLAN.md and docs/port/PROGRESS.md.

Reply with, and nothing else:
1. The six phases in one line each.
2. Which phase cannot start today, and the specific decision or precondition that blocks it.
3. Three things in this plan that you are not permitted to do, and why each one is forbidden.

Do not summarise the plan beyond that. Do not propose improvements. Do not begin any work.
```

If it lists phases it invented, or misses that Phase 0 gates everything, stop and re-read the plan with it in a narrower scope. If it answers cleanly, proceed.

---

## Prompt 1 — Start or resume a session

Use this at the top of every session, including ones where you know what is next.

```
Do not edit, create or delete any file yet.

Read docs/port/PROGRESS.md, then docs/port/DECISIONS.md.

Report:
1. The status of each work order, from the table only.
2. The next work order, by number.
3. Whether each of its preconditions is met — check by running the commands it lists, not by
   reading them.
4. Anything recorded as blocked.

Then stop and wait for me to confirm before you start.
```

The value is step 3. An agent that reads preconditions instead of running them will happily start Phase 2 on a machine without Docker.

---

## Prompt 2 — Run one work order

The main prompt. Change the number.

```
Execute docs/port/WO-1-Repo-and-ground-rules.md. That work order and nothing else.

Rules for this session:
- Run every precondition command first and paste the output. If one fails, stop and report which.
- Stay inside the "Files you may create or edit" list. If the work needs a file outside that list,
  stop and tell me rather than creating it.
- The "Stop list" is absolute. If you reach anything on it — a credential, a repository setting, an
  install, a permission — stop and tell me what you need. Do not find a workaround. A workaround on
  a security control is worse than an unfinished phase.
- Run the Acceptance section at the end and paste the raw output, including failures. Do not
  describe it as passing without the output.
- If you cannot finish, stop cleanly at a coherent point and say exactly where.

When you are done, append one row to docs/port/PROGRESS.md, then stop. Do not start the next work
order.
```

For Phase 4 only, add:

```
You will not have Azure credentials in this session. Do the offline acceptance checks only. For the
checks that need a live deployment, do not attempt them, do not mock them, and do not describe them
as verified — write the exact command I should run into PROGRESS.md instead.
```

---

## Prompt 3 — When it reports blocked

```
You are blocked. Do not change any code and do not attempt a workaround.

Write to docs/port/PROGRESS.md under "Blocked":
- the work order and step
- the exact command you ran
- its full output
- the single smallest thing a human must do to unblock it, as an instruction I can follow in under
  a minute

Then stop.
```

"Smallest thing a human must do" is the part that matters. Left to itself an agent writes "needs Azure credentials", which tells you nothing actionable.

---

## Prompt 4 — Verify without editing

Use this when a previous session claimed success and you are not convinced.

```
Do not edit, create or delete any file. Verification only.

Run the entire Acceptance section of docs/port/WO-2-Devcontainer.md exactly as written and paste
the raw output of every command.

Then compare each result with the pass condition the work order states, and answer for each one:
PASS, FAIL or COULD NOT RUN — with the reason.

Do not fix anything. If something fails, tell me what and stop.
```

---

## Prompt 5 — Close a session cleanly

```
Before you stop:
1. Re-read what you actually did this session, not what you planned.
2. Update your row in docs/port/PROGRESS.md: status, date, and evidence as commands with their output.
3. List anything you did not verify, and the command that would verify it.
4. State the next work order and what it will need from me.

Do not start it.
```

---

## Prompt 6 — When it has gone off the rails

Symptoms: it edited files outside its scope, it skipped the acceptance section, it "fixed" a failing test, it started a second phase.

```
Stop. Do not make any further changes.

Report, without fixing anything:
1. Every file you created, modified or deleted this session, and whether each was inside the
   permitted list in the work order.
2. Every check you did not run, or ran and did not report.
3. Anything you changed that a work order did not ask for, and why.

Then propose either "revert the following paths" or "keep the following paths", with reasons.
Wait for my decision before doing either.
```

Then, before resuming, fix the work order or the prompt — not the agent's behaviour in the moment.

---

## Prompt 7 — Recovery after a revert

```
We reverted the following paths: <list>.
Read docs/port/PROGRESS.md for what was established before the revert.
Re-run the Acceptance section of docs/port/WO-<N>.md and tell me what is still true and what is not.
Do not redo work that the evidence shows is done — list it and move on.
```

Half of a review round is wasted re-establishing facts that are already recorded. Say so explicitly.

---

## The three failure modes to watch for

**Volume over evidence.** A long report with no pasted output. Ask for the command and its result; the report is not the artefact, the output is.

**Scope creep.** It writes the Dockerfile and then notices the CI workflow needs updating, and does both. The work order boundary is the only thing preventing this; reinforce it in Prompt 2 rather than trusting the document alone.

**Invented verification.** "The suite passes" when it was never run, or run in the wrong environment. This is the one that costs you a week, because it looks exactly like success. Every acceptance section in the work orders is written to be pasted, for this reason.

---

## Optional: the factory roles are not these prompts

`.github/agents/*.agent.md` (WO-3) defines the builder, reviewer and lead that the *factory* uses once the port is live. They are not for executing the port. Do not use the Reviewer agent to review your own port work — it is pinned to a different model family for the factory's purposes, and using it as a generic reviewer invites the same confusion the split exists to prevent.
