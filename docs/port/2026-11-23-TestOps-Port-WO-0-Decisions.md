---
phase: 0
title: Decisions and preconditions
prereqs: none — this is the first work order
deliverables: [docs/port/DECISIONS.md]
gate: DECISIONS.md exists, all seven rows answered, and no answer reads "unknown" or "TBD"
stop-if: any decision needs a person who is not in this conversation
---

# WO-0 — Decisions and preconditions

## Scope

Interview the operator and record seven decisions. **Do not create, edit or delete any other file. Do not begin Phase 1.** This work order produces a document, nothing else.

## Why this exists

Every later work order branches on these answers. An agent that assumes them produces work that has to be thrown away, and — worse — work that looks finished. The most expensive failure in this plan is a builder/reviewer pair from the same model family, because the review then reads as evidence when it is only an echo.

## Do this

Ask the seven questions **one at a time**, conversationally, and wait for each answer. Do not batch them and do not offer a default that the operator might accept without thinking.

Then write `docs/port/DECISIONS.md` with a table of all seven, the answer, the date, and one line of consequence for each.

## The seven questions

**D1 — Repo.** Which GitHub org and repository will host this? Does the operator have write access to it, and permission to add workflows? If the repo does not exist yet, say so plainly: creating it is a human step and WO-1 cannot start.

**D2 — Actions.** Are GitHub Actions permitted on private repositories in this organisation, and is there a spend limit the operator knows about? The factory costs roughly $10/month of compute at one build a night.

**D3 — Network reach.** Can a GitHub-hosted runner reach the internal Jira and ADO instances? Ask directly; do not infer from anything else. Record the answer as yes or no. If no, record the consequence: the builder can produce changes but cannot prove anything end-to-end, and every verdict that depends on those sources is `not_assessable`.

**D4 — Models.** Which Azure AI Foundry deployments are available, and which family is each? Record the **deployment name** (not the model name) for the builder slot and the reviewer slot, and the family (`anthropic`, `openai`, `microsoft`). The families must differ. If the operator does not know, help them check:

```bash
az cognitiveservices account deployment list -n <account> -g <rg> -o table
az cognitiveservices account list-models -n <account> -g <rg> -o json
```

A model in the catalogue with no quota cannot be deployed; `InsufficientQuota` naming capacity 1 means the allocation is genuinely zero. If only one family is available, record that, and record the consequence: review becomes **advisory**, is labelled as such in every review report, and a human holds the merge gate. Do not describe an advisory review as a review.

**D5 — Identity.** Is a service identity acceptable for commits and pull requests, and who signs that off? If the answer is no, stop the whole plan here and say so.

**D6 — Branch protection.** Does the protected branch require a human approval before merge? If yes, keep it. This is the merge gate and removing it is not an option the factory needs.

**D7 — History.** Does the work repository need the private repository's ~460-commit history, or does it start at a single import commit? Record the answer and its consequence either way, and record **why**, because this is the one decision that cannot be revisited quietly:

- **Single import (recommended, and the default).** `scripts/export_clean.sh` builds a one-commit repository. It costs `git log` archaeology and the `factory/*` branches, and it guarantees nothing that was in the private history can be recovered from the work remote.
- **Full history.** Only if the organisation requires it for audit, and only with a written statement that the early commits contain a subscription id, absolute local paths and the names of the projects the tool was demonstrated on. Say who accepted that, and do not describe the result as scrubbed.

A mirror (`git push --mirror`) is not a third option: it republishes every ref and deletes nothing, so it is the full-history answer taken silently.

## Files you may create or edit

- `docs/port/DECISIONS.md` (new)

Nothing else. Not `.gitignore`, not `pyproject.toml`, not a ticket.

## Acceptance

Run this and paste the raw output:

```bash
cat docs/port/DECISIONS.md
```

Pass requires: seven rows, each with a concrete answer, none reading "unknown", "TBD" or "ask someone". For D4, two deployment names and two different families.

## Stop list — do not work around

- Do not create the repository, a GitHub organisation, secrets, or runner groups.
- Do not install anything.
- Do not write code, tests, or factory tickets.
- Do not "proceed on a reasonable assumption" for any of the six. An unanswered decision is a stop, not a default.

## When done

Append one row to `docs/port/PROGRESS.md` recording that WO-0 is complete, the date, and the D4 families. Then tell the operator which work order is next and what it needs from them.
