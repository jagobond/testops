---
phase: 4
title: Write the coordinator
prereqs: [WO-1, WO-3 complete; D4 deployment names recorded]
deliverables: [factory/config.json, factory/coordinator.py]
gate: dry-run selects correctly; same-family pair is refused; paused exits 0; token refresh proven
stop-if: you reach anything needing a live Foundry deployment to verify, and no credentials are available
---

# WO-4 — Write the coordinator

## Scope

Two files, and they are the only new code in the whole port. Everything with a behavioural guarantee already exists in the home implementation: worktree per ticket, tri-state test results, the review round, report shapes, the Lead merge gate. You are porting behaviour, not inventing it.

This is also the largest work order. If you cannot finish it in one session, stop after `config.json` and a `coordinator.py` that passes the offline acceptance checks, record exactly where you stopped, and say so.

## Preconditions

```bash
ls factory/config.json 2>/dev/null || echo "absent (expected)"
git worktree list
python -V
```

Read `docs/port/DECISIONS.md` for the deployment names and families, and `AGENTS.md` for the paths you may write.

## 1. `factory/config.json`

```json
{
  "models": {
    "builder":  { "deployment": "<builder>",  "family": "<family>" },
    "reviewer": { "deployment": "<reviewer>", "family": "<family>" }
  },
  "endpoint": "https://<account>.services.ai.azure.com/openai/v1/chat/completions",
  "budgets_minutes": { "builder": 45, "reviewer": 20 },
  "max_tickets_per_run": 1,
  "paused": false
}
```

Validate on load against this contract, and treat an unknown key as an error rather than a warning — a typo that silently leaves a default in place is how a budget stops applying.

| Path | Type | Rule |
|---|---|---|
| `models.builder.deployment` | string | non-empty |
| `models.builder.family` | string | `anthropic` \| `openai` \| `microsoft` |
| `models.reviewer.deployment` | string | non-empty |
| `models.reviewer.family` | string | must **differ** from the builder's |
| `endpoint` | string | `https://` and ends `/chat/completions` |
| `budgets_minutes.*` | int | 1–120 |
| `max_tickets_per_run` | int | ≥ 1 |
| `paused` | bool | — |

Refuse to start when the two families match, naming both deployments in the message.

## 2. `factory/coordinator.py`

A plain script, not a package. It puts the repo root on `sys.path` itself so `import testops` works without a console-script entry point — the coordinator is factory infrastructure that the Lead maintains, and putting it under `testops/` would make it protected product code that only a ticket could change.

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
```

Required behaviours, each with the acceptance test that proves it:

**Ticket selection.** Read `factory/tickets/*.md` frontmatter. Eligible when `status: ready` and every `depends_on` ticket is `done`. Lowest id wins. Skip any ticket that already has a `factory/<ID>` branch or an open PR. This is the same-ticket race guard: two people dispatching the same ticket must not both build it.

**The board is derived, never written.** `factory/TICKETS.md` is generated from ticket frontmatter plus open-PR state, or is Lead-only and human-edited. The coordinator must not `git add` it. Two parallel builds editing the same rows of one file conflict every time.

**Cap, scoped.** Count factory PRs opened in the last 24 hours via the API, and apply the cap **only to the scheduled run**. A human dispatch is exempt: a person pressing a button is the control, and a repo-wide cap would let one person's build silently starve another's.

**Staging is restricted.** Stage `factory/reports` and `factory/tickets` only. Never `git add -A`, and never `factory/TICKETS.md`. A credential file now lives in `.factory/` and one `git add -A` is all that stands between it and the history.

**Single-run lock.** `.factory/run.lock` holding a pid, cleared only when that pid is gone. Two runs in one checkout share the SQLite store and the worktree directory.

**Tri-state tests.** `run_tests()` returns `True` pass, `False` genuine failure, `None` environment problem. Never collapse `None` into `False`: a broken measurement reported as a failure sends a human debugging healthy code.

**Subprocess environment.** Set `TESTOPS_ENV` and `TESTOPS_DATA` to absolute paths under `.factory/`, and strip `PYTHONPATH`, `PYTHONHOME`, `VIRTUAL_ENV`, `CONDA_PREFIX`. Set them **before** importing `testops`: `config.DATA` is computed at import while `settings()` re-reads the environment, so a late assignment gives you one old path and one new one.

**Token.** Standard library only, cached until two minutes before expiry:

```python
_token = {"value": None, "expires": 0.0}

def aad_token() -> str:
    import json, os, time, urllib.parse, urllib.request
    if _token["value"] and time.time() < _token["expires"] - 120:
        return _token["value"]
    tenant = os.environ["AZURE_TENANT_ID"]
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": os.environ["AZURE_CLIENT_ID"],
        "client_secret": os.environ["AZURE_CLIENT_SECRET"],
        "scope": "https://cognitiveservices.azure.com/.default",
    }).encode()
    req = urllib.request.Request(
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token", data=body)
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    _token["value"] = payload["access_token"]
    _token["expires"] = time.time() + int(payload.get("expires_in", 3600))
    return _token["value"]
```

`model` in the chat-completions body is the **deployment name**, never the model name. A reasoning model spends `max_completion_tokens` on reasoning and returns HTTP 200 with empty content: that is a budget that is too small, not an auth failure.

**Precedence.** `flags > environment > config.json`. `--ticket` beats `FACTORY_TICKET`, `--dry-run` beats `FACTORY_DRY_RUN`. The workflow can only pass environment variables; your terminal passes flags. Both reach the same `run_once(ticket=None, dry_run=False)`.

**Pause.** `paused: true` or a `PAUSED` file → exit 0, do nothing, print why.

## 3. Report shapes

Build and review reports go to `factory/reports/<YYYY-MM-DD>/<ID>-build.md` and `-review.md`. The review report carries a Demo section with exactly five labels: The problem / What changed / How we know it works / What it does not solve / Where to look. Approve, redo or kill must be decidable from that section alone.

## Acceptance

**Provable offline — run these, paste the output:**

```bash
python factory/coordinator.py --dry-run          # prints the chosen ticket, changes nothing
git status --porcelain                           # empty
python -c "import json;json.load(open('factory/config.json'))"
# same-family refusal: set both families equal in a COPY of the config and run with it
PAUSED=1 python factory/coordinator.py --once    # exit 0, prints the reason, builds nothing
git worktree list                                # no stale worktrees
```

**Requires a live deployment — if credentials are unavailable, stop here and say so:**

```bash
python factory/coordinator.py --once             # produces factory/<ID> and a draft PR
```

Report the offline results either way. Do not describe the live run as verified if you could not perform it.

## Stop list — do not work around

- Do not commit `.factory/` or any credential.
- Do not print a token, or an `Authorization` header, into a log or a report.
- Do not force-push, and do not push to a protected branch.
- Do not edit acceptance criteria in a ticket, and do not edit anything under `testops/` to make the coordinator pass.
- Do not "temporarily" relax the family check to get a run through.

## When done

Append a row to `docs/port/PROGRESS.md` with which acceptance checks passed, which needed credentials and were not run, and the exact command someone with credentials should execute.
