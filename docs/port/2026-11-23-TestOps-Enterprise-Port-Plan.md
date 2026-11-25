---
title: TestOps — port to the enterprise environment (GitHub + Actions + VS Code)
date: 2026-11-23
revision: 4 (after three QA rounds — see §15)
status: approved for execution
owner: Harry
target: enterprise workstation, GitHub-hosted repo, GitHub Actions, VS Code + devcontainer, Azure AI Foundry
---

# TestOps enterprise port plan

Moving the TestOps product and its factory workflow from the home Hermes system to a GitHub-hosted environment driven from VS Code. No Hermes on the work machine, no CLI agent, models reachable only through Azure AI Foundry deployments restricted to the OpenAI, Anthropic and Microsoft families.

---

## 1. What this plan is and is not

**Is:** an ordered set of steps ending in the same working practice you have now — you write tickets, a builder implements, a reviewer falsifies, you merge on a demo — running on infrastructure that exists at work.

**Is not:** a rewrite. The product does not change. The ticket format does not change. The board does not change. What changes is *who executes the Python* and *which surface you look at*.

**The single idea the plan rests on:** one command — `python factory/coordinator.py --once` — that can run in your VS Code terminal, in a WSL cron entry, or in a GitHub Actions job, with identical code in all three. Everything below exists to give that command the right environment, then choose where to run it.

That command does not exist yet. Writing it is Phase 4, and it is the largest single piece of work in this plan. Nothing before Phase 4 depends on it; nothing after Phase 4 can be tested without it.

---

## 2. Verified starting facts

Measured against the repository on 2026-11-23/24. Every line below was checked against a file or a command, not recalled.

| Fact | Value | Consequence for the port |
|---|---|---|
| Package root | `testops/` — there is no `src/` | `AGENTS.md` already names `testops/`; every path in a prompt or agent file must match |
| Python floor | `requires-python = ">=3.11"` | Container and CI both pin 3.11 |
| Runtime dependencies | **none** (`dependencies = []`) | Nothing to resolve from PyPI at run time |
| Dev extras | `pytest>=8`, `setuptools>=68`, `wheel` | `pip install -e ".[dev]"` is the whole install |
| Lockfile | **no `uv.lock`, no requirements.txt** | Any instruction to `uv sync --frozen` fails. Use pip, as `ci.yml` already does |
| Tests | **1,188** by `pytest --collect-only -q` on 2026-11-24 | A point-in-time figure. Never hard-code it in a gate; §11 pins the count to the migration commit |
| Test files | 84 (`tests/*.py`) | Same rule |
| Existing CI | `.github/workflows/ci.yml` — matrix 3.11 + 3.12, contract gate, render check | **Keep it and add to it.** See §5.6 |
| Config env vars | `TESTOPS_DATA` (default `data`), `TESTOPS_ENV` (default `.env`) | Both usable. `TESTOPS_HOME` is read at import into `config.HOME` and never used again — do not rely on it |
| Secrets | `GITHUB_PAT`, `JIRA_SITE`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, read **only** from the env file | Exporting them into the process environment does nothing |
| Missing credential behaviour | `load_env()` returns `{}` when the file is absent → `env["GITHUB_PAT"]` raises `KeyError`. If the file exists with an empty value, the key exists and the collector is called with an empty token | The second is the dangerous one: silent, not loud |
| CLI surface | `duplicate`, `levels`, `cases`, `runs`, `case-set`, `scrub-fixtures`, `check-store`, `serve`, `retention` | The factory's verification calls `duplicate`/`levels`, so they need `GITHUB_PAT` |
| Console scripts | **none** — no `[project.scripts]`; only `python -m testops.cli` | There is no `testops` command to call |
| Factory tree | `factory/{TICKETS.md, tickets, reports, prompts, briefs, candidates.md}` | Ports unchanged. `factory/config.json` and `factory/coordinator.py` do **not** yet exist — Phase 4 creates them |
| `docs/state/` | **does not exist** | Phase 1 creates it |
| `.devcontainer/` | **does not exist** | Phase 2 creates it |
| `.gitignore` | `.venv/`, `__pycache__/`, `*.egg-info/`, `build/`, `dist/`, `data/`, `*.log`, `.tmp/` — **no `.env`** | Phase 1 adds it. Do not assume it is ignored |
| Remote | `github.com/jagobond/testops` | Already GitHub; the port is a mirror to a work remote |

Two consequences worth stating plainly:

1. **The product has no LLM in it.** The suite asserts determinism and that the analysis and render paths reach no network (`tests/test_claim_determinism.py`, `tests/test_case_summary_and_code.py` AC9, `tests/test_case_page.py`). Keeping that true is why the coordinator lives outside `testops/` — see §4.1.
2. **`ci.yml` already encodes the hard-won rules** — stripped `PYTHONPATH`, `PYTHONNOUSERSITE=1`, the interpreter named in the check, render-not-compile. Do not rewrite it.

---

## 3. Decisions to settle before any code moves

Settle these first. QA's main structural criticism of revision 1 was that two of them were decided after the plan had already come to depend on them.

| # | Decision | Recommendation | If the answer is different |
|---|---|---|---|
| **D1** | Which GitHub org owns the work repo, and can you create workflows in it? | Work org | Nothing runs. Stop here |
| **D2** | Are Actions permitted on private repos, and what is the budget? | Yes; ~$10/month | The local-only fallback in §13 becomes the plan |
| **D3** | **Can the builder reach Jira and ADO?** | Assume **no** for phases 1–7 | If yes, add a self-hosted runner at Phase 5 and drop the "not assessable" compromise |
| **D4** | **Are both an OpenAI and an Anthropic deployment available, with quota?** | builder = Anthropic, reviewer = OpenAI | One family → the review is *advisory*, labelled as such, with a human review gate. It does not become a weaker PASS |
| **D5** | Is a service identity acceptable for commits and PRs? | Workflow token, scoped | If not, the factory cannot push and the plan reduces to read-only assistance |
| **D6** | Does branch protection require a human approval? | Yes — keep it | None. This is the merge gate |

**D3 and D4 are answered before Phase 4, not after.** D3 determines whether the builder can ever run the full suite; D4 determines whether "reviewed" means anything. Both change what the acceptance criteria can honestly assert.

---

## 4. Target architecture

```
   VS Code (devcontainer)                     GitHub Actions (ubuntu-latest)
   ┌──────────────────────────┐               ┌───────────────────────────────┐
   │ Lead agent   → tickets   │               │ schedule / workflow_dispatch  │
   │ Reviewer     → falsify   │               │   ↓ secrets → .factory/       │
   │ terminal     → run once  │               │   ↓ devcontainers/ci          │
   └────────────┬─────────────┘               │   factory/coordinator.py      │
                │  git fetch                 └──────────────┬────────────────┘
                ▼                                            │ push factory/<id>
          ┌──────────────────────────────────────────────────────────┐
          │  GitHub: factory/tickets, factory/reports, draft PRs      │
          └──────────────────────────────────────────────────────────┘
```

### 4.1 The named artefacts

Five files. Each is a deliverable of a named phase; none may be referenced before it exists.

| Artefact | Created in | Purpose |
|---|---|---|
| `.github/workflows/factory.yml` | Phase 5 | Schedule and dispatch |
| `.devcontainer/{Dockerfile,devcontainer.json}` | Phase 2 | The one image, used by editor and runner |
| `.github/agents/{lead,builder,reviewer}.agent.md` | Phase 3 | The three roles |
| `factory/config.json` | Phase 4 | Model deployment per role, budgets, pause flag |
| `factory/coordinator.py` | Phase 4 | The loop |
| `scripts/verify.sh` | Phase 1 | The one canonical test command |
| `docs/state/testops.md` | Phase 1 | Durable project state, read into every builder prompt |

**Why the coordinator lives in `factory/` and not `testops/`:** `AGENTS.md` says product code in `testops/` changes only through tickets, and that the Lead may edit `factory/**` directly. The coordinator is factory infrastructure that the Lead *does* maintain, so putting it inside `testops/` would make it protected product code and force a ticket to change the factory's own plumbing. That circularity is why the home system keeps the coordinator in `scripts/`. Adding a `[project.scripts]` entry point is also rejected for the same reason: an importable `factory` package inside the distribution turns infrastructure into shipped product.

`factory/coordinator.py` is therefore a plain script that puts the repo root on `sys.path` itself:

```python
# factory/coordinator.py — first lines
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
```

Invoked as `python factory/coordinator.py --once` from the repo root, everywhere, always.

---

## 5. Phase 1 — Move the repository and its ground rules (one day)

### 5.1 Mirror, don't re-init

```bash
git clone --mirror https://github.com/jagobond/testops.git testops-mirror.git
cd testops-mirror.git
git remote set-url origin https://github.com/<work-org>/testops.git
git push --mirror origin
```

`--mirror` carries `+refs/*:refs/*`, so every factory branch and tag moves and anything absent at the destination is deleted. Then clone normally from the new remote and confirm **in the new clone** (inside a mirror clone `git branch -r` is empty by design — the refs live in `refs/*`):

```bash
git log --oneline -3                    # same three commits as the source
git branch -r | wc -l                   # same factory/* branch count
ls factory/tickets/*.md | wc -l         # same ticket count
```

Keep the old remote as `upstream` for a fortnight.

### 5.2 Ground rules, committed before anything else

```bash
printf '* text=auto eol=lf\n*.bat text eol=crlf\n' > .gitattributes

cat >> .gitignore <<'EOF'
.env
*.env
.factory/
EOF

git add .gitattributes .gitignore && git commit -m "Port: line endings, ignore secrets and factory state"
git check-ignore -q .env && echo "OK: .env is ignored"
```

`.gitignore` did **not** previously ignore `.env`. This step adds it. `git check-ignore -q` is the test, not a `grep`, because a grep also matches a comment that mentions `.env`.

### 5.3 `scripts/verify.sh` — one canonical test command

There were four slightly different invocations of the same rule in revision 1, one of which dropped `CONDA_PREFIX`. Four copies is four places to drift, and the drift produces "passes here, fails there, blame the code".

```bash
#!/usr/bin/env bash
# scripts/verify.sh — the only way this repo runs its tests.
# The environment is stripped, or an inherited PYTHONPATH makes the result an
# environment error rather than a pass. AGENTS.md is the authority for this rule.
set -euo pipefail
PY="${PY:-python}"
exec env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX \
     PYTHONNOUSERSITE=1 "$PY" -m pytest "$@" -q
```

Used by: Phase 1's baseline, Phase 2's container check, both pytest steps in `ci.yml` (the suite and the contract gate, on both matrix legs), and the coordinator. There is no second copy of the strip list anywhere.

### 5.4 Secrets and data outside the checkout

The code reads credentials only from the file named by `TESTOPS_ENV`. Exporting them does nothing.

- Set `TESTOPS_ENV` to **`<repo>/.factory/secrets.env`**. Inside the checkout so the container can read it after the bind mount (revision 1 wrote it to `$RUNNER_TEMP`, which the container cannot see — the run then died with `KeyError: 'GITHUB_PAT'`). Inside `.factory/`, which is now gitignored and which the coordinator never `git add`s.
- Set `TESTOPS_DATA` to **`<repo>/.factory/data`** — an absolute path in the *parent* checkout, so every worktree shares one store. Worktrees do not share ignored files, and the store is ignored.
- Never put the store on a network share. SQLite in WAL mode over SMB is a documented way to corrupt or hang a store.

Layered guards, because "it's gitignored" is a claim and not a barrier:

1. `.factory/` in `.gitignore` (5.2).
2. The coordinator stages only `factory/reports` and `factory/tickets`, never `git add -A`.
3. The workflow asserts `git check-ignore -q .factory/secrets.env` and fails the job if it is false.
4. The workflow asserts the token is non-empty (an empty `GITHUB_PAT=` produces a silent empty-token run, not a `KeyError`).

### 5.5 `docs/state/testops.md`

Does not exist. Create it in this phase, from what you already know, because the builder prompt reads it and an agent handed a missing path either stops or invents it.

Content: one page of facts a new session cannot rediscover — the store schema version, the `not_assessable`-not-zero rule, which ecosystems extract and which only detect, the current baseline numbers, and the constraints that look like bugs but are deliberate.

### 5.6 Extend `ci.yml` — add, don't replace
`ci.yml` keeps its matrix, its contract gate and its render job. Three specific changes, and nothing else:

1. **Both existing pytest steps route through `scripts/verify.sh`**, keeping their `tee` and their path argument. Otherwise the strip list still lives in three places and §5.3 was cosmetic.
2. **A new `image` job** builds the devcontainer and runs the suite inside it, so the port's own container is tested on every push.
3. **That job needs its own `permissions:`.** `ci.yml` declares workflow-level `contents: read`, which every job inherits; publishing to GHCR needs `packages: write`, and a job-level block is the only way to grant it without widening the rest.

```yaml
  image:
    name: devcontainer image builds and the suite passes in it
    runs-on: ubuntu-latest
    timeout-minutes: 20
    permissions:
      contents: read
      packages: write          # job-level: the workflow default is contents: read only
    steps:
      - uses: actions/checkout@v5
      - uses: docker/login-action@v4
        with:
          registry: ghcr.io
          username: ${{ github.repository_owner }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: devcontainers/ci@v0.3
        with:
          imageName: ghcr.io/${{ github.repository_owner }}/testops-devcontainer
          cacheFrom: ghcr.io/${{ github.repository_owner }}/testops-devcontainer
          push: filter                 # publish on main, build-only on PRs
          refFilterForPush: refs/heads/main
          runCmd: bash -lc "pip install -e '.[dev]' && ./scripts/verify.sh"
```

The `docker/login-action` step is not optional: `devcontainers/ci` exposes no registry credential input, so it relies on an existing Docker login.

Without this job the port's own container is never tested by CI, and the factory can break for days before anyone notices.
### 5.7 Phase 1 acceptance

| id | criterion |
|---|---|
| P1-AC1 | In the **new normal clone**: `git log --oneline -3` matches the source, `git branch -r \| wc -l` matches, and `ls factory/tickets/*.md \| wc -l` matches. |
| P1-AC2 | `git check-ignore -q .env` and `git check-ignore -q .factory/secrets.env` both exit 0. |
| P1-AC3 | `pip install -e ".[dev]"` then `./scripts/verify.sh` reports the pass count **recorded in the migration ticket**, on Python 3.11. The ticket records the `--collect-only` number from the source checkout and the commit it was taken at; the plan does not carry a literal. |
| P1-AC4 | `git status --porcelain` is empty after a full suite run. |
| P1-AC5 | `docs/state/testops.md` exists, is non-empty, and the builder prompt's first three read paths all resolve. |

---

## 6. Phase 2 — The container (one day)

### 6.1 Dockerfile

```dockerfile
# .devcontainer/Dockerfile
FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm

# Corporate TLS inspection: uncomment and add the root CA if image builds or outbound
# HTTPS fail with SSLCertVerificationError. Keep certs/ out of git.
# COPY certs/corp-root.crt /usr/local/share/ca-certificates/corp-root.crt
# RUN update-ca-certificates
# ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
#     SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
#     GIT_SSL_CAINFO=/etc/ssl/certs/ca-certificates.crt

RUN apt-get update && apt-get install -y --no-install-recommends \
      git sqlite3 jq curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Dev extras only: the package declares no runtime dependencies, and the editable
# install happens against the mounted workspace, not in the image.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir "pytest>=8" "setuptools>=68" wheel

ENV PYTHONNOUSERSITE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /workspaces/testops
```

No Azure CLI in the image. Phase 4 gets its token over HTTPS with stdlib `urllib`, which removes a 500 MB dependency and a whole class of authentication problems (§8.4).

### 6.2 devcontainer.json

```json
{
  "name": "testops",
  "build": { "dockerfile": "Dockerfile" },
  "remoteUser": "vscode",
  "postCreateCommand": "pip install -e '.[dev]'",
  "customizations": {
    "vscode": {
      "extensions": [
        "GitHub.copilot",
        "GitHub.copilot-chat",
        "GitHub.vscode-pull-request-github",
        "GitHub.vscode-github-actions"
      ]
    }
  }
}
```

### 6.3 Verify the image as the user the editor uses

```bash
# run from a WSL/Linux shell, or from MSYS bash with $(cygpath -w "$PWD")
docker build -t testops-dev .devcontainer/

MSYS_NO_PATHCONV=1 docker run --rm --user vscode \
  --mount type=bind,source="$(cygpath -w "$PWD" 2>/dev/null || echo "$PWD")",target=/workspaces/testops \
  -w /workspaces/testops testops-dev \
  bash -lc "pip install -e '.[dev]' && ./scripts/verify.sh"
```

`--user vscode` matters: the Dockerfile sets no `USER`, so a bare `docker run` is root. Root may succeed on permissions where `vscode` fails, and Phase 3 depends on the `vscode` path working.

Then prove the package is actually importable, not merely installed:

```bash
MSYS_NO_PATHCONV=1 docker run --rm --user vscode \
  --mount type=bind,source="$(cygpath -w "$PWD" 2>/dev/null || echo "$PWD")",target=/workspaces/testops \
  -w /workspaces/testops testops-dev \
  python -c "import testops, sys; print(testops.__file__, sys.version)"
```

A container that builds and a suite that passes do not prove the coordinator can `import testops` — the image installs no package; only the post-create step does.

### 6.4 Phase 2 acceptance

| id | criterion |
|---|---|
| P2-AC1 | `./scripts/verify.sh` inside the container **as `vscode`** reports the same pass count as P1-AC3. |
| P2-AC2 | `python .github/ci/render_case_page.py` succeeds inside the container. |
| P2-AC3 | `docker run --rm --user vscode ... python -c "import testops"` succeeds. (Revision 1 used `docker history \| grep secret`, which inspects layer *commands*, not contents, and matches legitimate words like `ca-certificates`.) |
| P2-AC4 | Nothing is copied into the image: `grep -i -E "^(COPY\|ADD)" .devcontainer/Dockerfile` returns only the commented CA line. |

---

## 7. Phase 3 — The roles as VS Code custom agents (half a day)

Custom agents are the closest analogue to a Hermes profile: a file in `.github/agents/` carrying a persona, a tool allowlist and a pinned model, versioned with the tickets it serves.

### 7.1 Model allocation

Two families is enough, but the split is **not** the intuitive one:

| Role | Family | Why |
|---|---|---|
| **builder** | Anthropic, cheapest capable tier | Mechanical, well-specified edits guarded by the suite. Runs 3–4× more often than the reviewer, so the cheap model belongs here |
| **reviewer** | OpenAI, strongest available | The job is falsification. It gets the strongest model, which is also the family that did not write the code |
| **lead** | Either | Runs rarely; writes tickets and reports, never code |

If Anthropic proves stronger in practice, invert it. The rule that must hold: **reviewer ≠ builder family, and reviewer is at least as capable.**

### 7.2 `.github/agents/reviewer.agent.md`

```markdown
---
name: Reviewer
description: Falsify a TestOps build against its ticket. Reads, searches and runs tests. Never edits.
tools: ['read', 'search', 'execute']
model: ['<strongest OpenAI deployment name>']
model-policy: required
---
You are reviewing a build against its ticket. You have not seen the builder's reasoning and must not
ask for it. Re-derive what "correct" means from the ticket, the diff and the source.

DEMAND FAILURE, NOT AGREEMENT. For every guard, constraint or baseline the ticket adds, make it go
red first, and paste the red output into the report. A test nobody has watched fail proves only that
it ran.

Recompute any headline number with your own code — your own walk, your own matcher. A right count of
wrongly-classified items is worse than a low count.

A missing source is never a zero (AGENTS.md). If Jira or ADO is unreachable, the verdict is "cannot
assess", never "nothing found".

Write factory/reports/<YYYY-MM-DD>/<ID>-review.md containing:
- verdict (PASS / FAIL / INCOMPLETE) and the evidence for it
- what you did not verify, stated plainly
- a Demo section with exactly these labels: The problem / What changed / How we know it works /
  What it does not solve / Where to look

An INCOMPLETE verdict with the evidence you have is worth more than silence. Write the file even if a
probe fails or times out. Do not edit code. Do not edit acceptance criteria. If a change is needed,
write it as a finding.
```

### 7.3 `.github/agents/builder.agent.md`

```markdown
---
name: Builder
description: Implement one factory ticket. Edits code and runs tests within the ticket's scope.
tools: ['read', 'search', 'edit', 'execute']
model: ['<cheapest capable Anthropic deployment name>']
model-policy: required
---
Implement exactly one ticket, named in the request, on branch factory/<ID>.

Read, in this order: AGENTS.md, docs/state/testops.md, factory/tickets/<ID>.md, then the code.
You are an elephant: you get the full context and are expected to use it.

Not negotiable:
- Do not edit acceptance criteria. If two criteria contradict each other, stop and report it.
- Do not edit anything outside the ticket's scope. If a change is needed elsewhere, write it in the
  report; do not make it.
- Every number you report must come from a run you performed, with the command in the report.
- If a target cannot be met, say so with the funnel and the evidence. A recorded miss is more useful
  than a tuned pass. Do not tune until the number looks acceptable.

Verify with ./scripts/verify.sh — never a bare pytest call, because the stripped environment is the
difference between a pass and an environment error.

Write factory/reports/<YYYY-MM-DD>/<ID>-build.md: what changed, the commands you ran with their
output, what you measured against each criterion, and what you did not verify.
```

### 7.4 `.github/agents/lead.agent.md`

```markdown
---
name: Lead
description: Write and maintain factory tickets. Never edits product code.
tools: ['read', 'search', 'edit']
---
You write tickets; you do not write product code. Writable: factory/**, PRODUCT.md, ROLES.md, docs/**.
Everything under testops/ is out of bounds — if a fix is needed there, it is a ticket.

Before writing a ticket, search factory/tickets/ for one that already covers the capability. A blocked
ticket is a planned requirement, not a gap.

Every ticket carries testable acceptance criteria as a table with stable AC ids, written before any
code. Where a criterion's purpose is provenance, restraint, or non-vacuity, write the test of that
purpose into the criterion, not just the artefact it produces.

State the boundary explicitly when a ticket resembles an existing one, and say in the new ticket why
it is not the same thing.
```

`AGENTS.md` needs no change: VS Code reads it as project instructions, and it already protects `testops/`.

### 7.5 Phase 3 acceptance

| id | criterion |
|---|---|
| P3-AC1 | All three files load without frontmatter errors and appear in the agent picker. |
| P3-AC2 | The Reviewer agent cannot edit a file when asked to — prove it by asking, and by checking the tool activity, not the reply. |
| P3-AC3 | A review of a real build produces a report with all five Demo labels. |

---

## 8. Phase 4 — Write the coordinator (two to three days)

This is the only genuinely new code. Revision 1 implied it already existed; it does not.

### 8.1 What carries over unchanged

Worktree per ticket, cap, `PAUSED` flag, report shapes, the tri-state test result, the Demo section, the reviewer's different-family requirement, the Lead's merge gate. All of it is behaviour, not plumbing, and all of it survives the move.

### 8.2 `factory/config.json` (created here, validated before use)
```json
{
  "models": {
    "builder":  { "deployment": "<anthropic-deployment>", "family": "anthropic" },
    "reviewer": { "deployment": "<openai-deployment>",    "family": "openai" }
  },
  "endpoint": "https://<account>.services.ai.azure.com/openai/v1/chat/completions",
  "budgets_minutes": { "builder": 45, "reviewer": 20 },
  "max_tickets_per_run": 1,
  "paused": false
}
```

The file is validated on load; this is the contract, not an example:

| Path | Type | Required | Rule |
|---|---|---|---|
| `models.builder.deployment` | string | yes | non-empty |
| `models.builder.family` | string | yes | `anthropic` \| `openai` \| `microsoft` |
| `models.reviewer.deployment` | string | yes | non-empty |
| `models.reviewer.family` | string | yes | must **differ** from `models.builder.family` |
| `endpoint` | string | yes | `https://` and ends `/chat/completions` |
| `budgets_minutes.*` | int | yes | 1–120 |
| `max_tickets_per_run` | int | yes | ≥ 1 |
| `paused` | bool | yes | — |

An unknown key is an error, not a warning: a typo that silently leaves a default in place is how a budget stops applying. The coordinator refuses to start if the two families match — that refusal is what makes D4 enforceable, and it is tested by **P4-AC1**.
### 8.3 The `.env` and data discipline in code

Every subprocess gets an absolute `TESTOPS_ENV` and `TESTOPS_DATA`, set **before** `import testops`, because `testops/config.py` computes `DATA` at import time while `settings()` re-reads the environment — a process that sets the variable afterwards gets the old path from one and the new one from the other.

```python
env = {
    **os.environ,
    "TESTOPS_ENV": str(Path(REPO, ".factory", "secrets.env").resolve()),
    "TESTOPS_DATA": str(Path(REPO, ".factory", "data").resolve()),
    "PYTHONNOUSERSITE": "1",
}
for k in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX"):
    env.pop(k, None)
```

### 8.4 Authentication: client credentials over stdlib HTTPS

The container has no Azure CLI and no `~/.azure` cache. Revision 1 ran `azure/login` on the *runner* and then handed off to a container that could not see that login — the classic "authenticates the wrong process" failure.

The coordinator acquires its own token, with no dependency and no cache:

```python
# factory/coordinator.py — token acquisition (stdlib only)
import json, os, time, urllib.parse, urllib.request

_token = {"value": None, "expires": 0.0}

def aad_token() -> str:
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

Then per call:

```
POST https://<account>.services.ai.azure.com/openai/v1/chat/completions
Authorization: Bearer <token>
{"model": "<deployment name>", "messages": [...], "max_completion_tokens": 8192}
```

Three traps, each worth an afternoon:

- `model` is the **deployment name**, not the model name.
- A reasoning model spends the completion budget on reasoning: a tight budget returns **HTTP 200 with empty content** and bills every token as reasoning. Not an auth failure.
- The token is re-fetched when it is within two minutes of expiry (not on every call, and not only once), so a 65-minute run does not die at the 60-minute mark. This is the concrete reason for not passing a bearer token in from the workflow.

The same code path works locally with the same three environment variables, which is why this beats `az login`: one auth mechanism, not two.

### 8.5 Tri-state test results

`run_tests()` returns `True` pass, `False` genuine failure, `None` environment problem. `None` is never collapsed into `False`. This is the rule that stops a broken measurement reading as a code defect, and it survives the port because it is a rule about reporting, not about Hermes.

### 8.6 How a run is configured

There are two front doors onto one function, and the precedence is stated once so no reader has to infer it:

```
flags  >  environment  >  config.json
```

- `--ticket T-042` beats `FACTORY_TICKET`; `--dry-run` beats `FACTORY_DRY_RUN`.
- The workflow sets only environment variables, because a dispatch input is a string, not an argv.
- Your local terminal uses flags, because typing is cheaper than exporting.
- `factory/config.json` supplies the defaults: which deployments, the budgets, `paused`.

Both paths reach the same `run_once(ticket=None, dry_run=False, ...)`. A dispatch with a ticket id therefore builds *that* ticket, which is what P5-AC1 asserts; a bare `--dry-run` on your machine does what P4-AC2 asserts.

### 8.7 Phase 4 acceptance

| id | criterion |
|---|---|
| P4-AC1 | `factory/config.json` exists and validates against §8.2; a same-family pair makes the coordinator exit non-zero with a message naming both deployments. |
| P4-AC2 | `--dry-run` picks the correct next ticket, prints the plan, and changes no file. |
| P4-AC3 | A run on a scratch ticket produces branch `factory/<ID>` and a **draft** PR whose body contains the build report. |
| P4-AC4 | `paused: true` (or a `PAUSED` file) → exit 0, nothing done, reason printed. |
| P4-AC5 | Killing a build mid-run leaves no worktree behind after the next run: `git worktree list` is clean. |
| P4-AC6 | The token refreshes: a run longer than the token lifetime completes without a 401 (prove with a long sleep before the second call, then remove the sleep). |

---

## 9. Phase 5 — The workflow (half a day)

```yaml
# .github/workflows/factory.yml
name: factory

on:
  schedule:
    - cron: "0 2 * * *"          # 02:00 UTC nightly
  workflow_dispatch:
    inputs:
      ticket:
        description: "Ticket id (blank = next ready)"
        required: false
      dry_run:
        description: "Plan only"
        type: boolean
        default: false

concurrency:
  # Keyed on the ticket, not the ref: the same ticket serialises so two people cannot build it
  # twice, while different tickets run in parallel. Keying on github.ref serialises everybody.
  group: factory-${{ inputs.ticket || 'scheduled' }}
  cancel-in-progress: false       # never cancel a build half-way

permissions:
  contents: write                 # push the factory branch
  pull-requests: write            # open the draft PR

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 90
    env:
      # The token call in the coordinator reads these three from the process environment.
      # They must be mapped here: a bare `KEY` in the action's `env:` input inherits from
      # the job environment and is silently DROPPED when unset.
      AZURE_TENANT_ID: ${{ vars.AZURE_TENANT_ID }}
      AZURE_CLIENT_ID: ${{ vars.AZURE_CLIENT_ID }}
      AZURE_CLIENT_SECRET: ${{ secrets.AZURE_CLIENT_SECRET }}
      # Not injected into step environments by default: checkout receives it as an input of its
      # own. The coordinator needs it for the PR count and the draft PR, so it must be mapped.
      GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    steps:
      - uses: actions/checkout@v5
        with:
          fetch-depth: 0

      - name: Write secrets where the container can read them
        shell: bash
        run: |
          umask 077
          mkdir -p .factory/data
          {
            echo "GITHUB_PAT=${{ secrets.FACTORY_READ_PAT }}"
            echo "JIRA_SITE=${{ vars.JIRA_SITE }}"
            echo "JIRA_EMAIL=${{ secrets.JIRA_EMAIL }}"
            echo "JIRA_API_TOKEN=${{ secrets.JIRA_API_TOKEN }}"
          } > .factory/secrets.env

      - name: Refuse to continue on a missing or empty credential
        shell: bash
        run: |
          git check-ignore -q .factory/secrets.env || { echo "::error::.factory/ is not gitignored"; exit 1; }
          for v in AZURE_TENANT_ID AZURE_CLIENT_ID AZURE_CLIENT_SECRET GITHUB_TOKEN; do
            if [ -z "${!v}" ]; then echo "::error::$v is not set on this repository"; exit 1; fi
          done
          if grep -qE '^GITHUB_PAT=$' .factory/secrets.env; then
            echo "::error::GITHUB_PAT is empty — the secret is not set on this repository"
            exit 1
          fi

      - uses: devcontainers/ci@v0.3
        with:
          imageName: ghcr.io/${{ github.repository_owner }}/testops-devcontainer
          cacheFrom: ghcr.io/${{ github.repository_owner }}/testops-devcontainer
          push: never
          env: |
            TESTOPS_ENV=/workspaces/testops/.factory/secrets.env
            TESTOPS_DATA=/workspaces/testops/.factory/data
            AZURE_TENANT_ID
            AZURE_CLIENT_ID
            AZURE_CLIENT_SECRET
            GITHUB_TOKEN
            FACTORY_TICKET=${{ inputs.ticket }}
            FACTORY_DRY_RUN=${{ inputs.dry_run }}
          runCmd: bash -lc "pip install -e '.[dev]' && python factory/coordinator.py --once"
```

Why each part is the way it is:

- **The secrets file lives inside the mounted workspace**, under a gitignored directory. The container sees `/workspaces/testops/.factory/secrets.env`; the runner sees `.factory/secrets.env`. One file, two paths, no copying across a boundary that does not exist.
- **The Azure trio is mapped at job level and passed into the container.** The action's `env:` input accepts a bare `KEY` meaning "inherit", but it resolves that name from the workflow step's environment and **omits the entry entirely when unset** — which is why the guard tests them explicitly rather than trusting the passthrough.
- **`push: never` here**, because this job needs no image; `ci.yml` builds and publishes it.
- **The workflow token does three jobs**: it authenticates the push, it answers the cap query, and it opens the draft PR. It is passed explicitly into the container, because `checkout` keeps its auth header inside the mounted workspace's `.git/config` — which is enough for `git push` but gives the API calls no credential at all. `FACTORY_READ_PAT` is a different credential for a different job: the *product's* collectors need a read token to clone the repos under analysis.
- **The cap is derived, not stored.** A fresh runner has no memory and a committed counter would need a push to `main` that branch protection forbids. So the cap is a question asked of the API: *how many factory PRs were opened in the last 24 hours?* One, and the next dispatch does nothing. Self-healing, no state file, and the audit trail is the PR list itself.
- **Branch protection stays on.** The factory opens a draft PR; the merge is yours.
- **This job assumes one committer.** §17 covers what changes when several people use it.

### 9.1 Triggering without a CLI

- **Nightly** — nothing to do.
- **"Build this one now"** — Actions tab → *factory* → *Run workflow* → ticket id. Or the same from the GitHub Actions panel inside VS Code. Ten seconds.
- **A VS Code task** — `tasks.json` with a command that runs `python factory/coordinator.py --once` in the devcontainer terminal, for when you want the loop on your own machine.

### 9.2 Phase 5 acceptance

| id | criterion |
|---|---|
| P5-AC1 | `workflow_dispatch` with a ticket id builds that ticket and nothing else. |
| P5-AC2 | `workflow_dispatch` with no id builds at most one ticket, and a second dispatch in the same day builds none — prove it by dispatching twice and showing the second run reports the PR count that stopped it, with no new branch created. |
| P5-AC3 | One run produces exactly one branch and one PR; re-dispatching the same ticket opens no duplicate. |
| P5-AC4 | A runaway build is stopped by the per-role budget in the coordinator *and* by `timeout-minutes`. Prove with a deliberately slow ticket. |
| P5-AC5 | A job with `GITHUB_PAT` unset fails at the guard step with the naming message, not with `KeyError`. |
| P5-AC6 | No credential in the log: `grep -E "ghp_\|api_token"` over the run log returns nothing. |

---

## 10. Phase 6 — The daily loop

This replaces the TUI. Six steps, no terminal outside VS Code.

1. **Write a ticket.** Repo open in the devcontainer, pick the **Lead** agent, describe the outcome. It writes `factory/tickets/T-0NN.md` and the `TICKETS.md` row. You read, adjust, commit, push.
2. **Dispatch.** Nothing (nightly), or *Run workflow* with the id.
3. **Wait.** Builder, reviewer, draft PR with the demo in the body.
4. **Read, in VS Code.** `git fetch`, check out `factory/T-0NN` from the Source Control branch list, read `factory/reports/<date>/T-0NN-build.md` and `-review.md`. You never need github.com.
5. **Judge.** Approve → merge from the Source Control pane. Redo → you are already on the branch: fix it, or switch to the **Reviewer** agent for a second opinion, then amend and push. Kill → close the PR, set the ticket back to `ready` with a note.
6. **Weekly**, run the drift check: commits on `main` that did not arrive via a factory PR. Non-zero means the rule slipped or the factory is behind. Both are worth knowing.

---

## 11. Baseline and gates

The pass count is **not** in this plan. It is recorded in the migration ticket, taken from `--collect-only` on the source checkout, with the commit it was taken at. Revision 1 carried "1,151" while a later measurement on a dirty tree returned 1,188; a hard-coded number makes every gate wrong the moment the suite grows, and makes a reader believe the port changed something.

| Gate | Proves |
|---|---|
| P1-AC3 | The repo works in the new environment |
| P2-AC1 | The **container** works, as the editor's user |
| P2-AC3 | The **package** is importable, not merely installed |
| P4-AC3 | The loop produces a reviewable artefact |
| P5-AC2 | The cap actually binds on a memoryless runner |
| §10 step 6 | The factory is still in use |

---

## 12. Costs

| Item | Estimate | Note |
|---|---|---|
| Actions compute | ~1,500 min/month ≈ **$10** | 45-min build + setup, nightly. Private repos bill in dollars since Oct 2026; Enterprise Cloud includes $300/month, so this is noise — but it is billed to the org, so say so |
| Model tokens | per run, deployment-dependent | Bounded by the per-run cap and `max_tickets_per_run` |
| Storage | negligible | Reports are text; the store lives in `.factory/` |

Self-hosted runners are no longer free by default — GitHub has introduced a per-minute fee. Check current pricing before treating one as the cheap option.

---

## 13. Risks and the fallback

| Risk | Likelihood | Mitigation |
|---|---|---|
| Suite not green in a Linux container | Medium | Phase 2 is a gate; do not pass a red suite |
| Only one model family deployable | Medium | Review becomes *advisory*, labelled, with a human review gate. Never a weaker PASS |
| TLS inspection breaks builds and API calls | Medium | The commented CA block in the Dockerfile |
| Actions blocked or budget-capped | Low | **The whole loop also runs from the VS Code terminal** — that is the fallback, and it needs no pipeline |
| Agent commits to `main` | Low | Branch protection, scoped `permissions`, the AGENTS.md rule, the weekly drift count |
| Secrets committed | Medium | `.factory/` ignored, staged paths restricted, `git check-ignore` gate, P5-AC5 |
| Builder cannot reach Jira/ADO | **High** | Expected. `not_assessable` is the honest verdict and `AGENTS.md` requires it. A self-hosted runner is the only real fix (D3) |
| Factory decays into "nobody uses it" | Medium | The weekly drift count |

---

## 14. Sequence and effort

| Phase | Work | Days | Gate |
|---|---|---|---|
| 0 | Settle D1–D6, especially D3 and D4 | 1 | Two families confirmed |
| 1 | Mirror, ground rules, `verify.sh`, `docs/state/`, extend `ci.yml` | 1 | Count matches; `.env` ignored; container job green |
| 2 | Container + verify as `vscode` | 1 | Suite green inside the container |
| 3 | Three agent files | 0.5 | Reviewer cannot edit; Demo section appears |
| 4 | **Write** `config.json` + `coordinator.py` | 2–3 | Dry-run correct; one real draft PR |
| 5 | Workflow | 0.5 | Cap binds; empty secret fails loudly |
| 6 | Daily loop, drift check | 1 | One ticket from ticket to merge without a terminal |

**Total 6–7 working days**, with Phases 2 and 4 as the two that can double.

Recommended cut: **stop after Phase 3 and drive the loop by hand for a week.** That is already the same working practice, and it tells you whether the prompts are right before you spend three days on the coordinator. If you would not have merged the hand-driven PRs, the prompts are wrong and scheduling will not fix it.

---

## 15. What the QA review changed

Revision 1 was returned **NOT EXECUTABLE**: three blockers, seven majors, six minors. All were accepted. The substantive changes:

| QA finding | Change in revision 2 |
|---|---|
| BLOCKER: the coordinator had three names and no file; no phase budgeted writing it | §4.1 names it once (`factory/coordinator.py`), Phase 4 is "write the coordinator", effort raised by a day |
| BLOCKER: secrets written to `$RUNNER_TEMP`, invisible inside the container | §5.4 and §9 put the file at `.factory/secrets.env` inside the mount; `env:` carries the paths |
| BLOCKER: `azure/login` on the runner does not authenticate the container | §8.4 replaces it with a stdlib client-credentials call that refreshes per request; the Azure CLI is removed from the image |
| MAJOR: 1,151/77 vs 1,188/84 | §11 removes the literal; the count lives in the migration ticket |
| MAJOR: `.env` not in `.gitignore`, yet P1-AC4 asserted it was | §5.2 adds it as a step; the test is `git check-ignore -q` |
| MAJOR: container check ran as root | §6.3 uses `--user vscode` |
| MAJOR: `-v "$PWD"` is not a valid bind from MSYS bash | §6.3 shows `cygpath`, and notes the WSL/Linux shell the plan assumes |
| MAJOR: `docs/state/testops.md`, `factory/config.json` referenced but absent | Phase 1 and Phase 4 now create them, with schemas |
| MAJOR: four env-stripping copies, one dropping `CONDA_PREFIX` | §5.3 makes `scripts/verify.sh` the only invocation |
| MINOR: `TESTOPS_HOME` is dead | §2 corrected to say it is read at import and never used again |
| MINOR: "fails with 'not assessable'" was wrong — it is `KeyError`, or a silent empty token | §2 states both behaviours; §9 adds the empty-secret guard |
| MINOR: `docker history \| grep` proves nothing | replaced with an import check (P2-AC3, P2-AC4) |
| MINOR: "untouched" vs "extend" `ci.yml`; PAT vs workflow token; cap on a memoryless runner | §5.6, §9 notes, and a cap derived from the PR list rather than a stored counter |

### 15.1 Round 2 — the first rewrite introduced its own blocker

The second QA pass returned **FIXES DO NOT HOLD**: eleven of thirteen fixes held, but replacing `azure/login` with a stdlib token call moved authentication into the container without ever binding the three `AZURE_*` variables into the job environment. The new code would have raised `KeyError: 'AZURE_TENANT_ID'` on the first call — the same class of failure the rewrite existed to remove.

| Round-2 finding | Change in revision 3 |
|---|---|
| BLOCKER: `AZURE_TENANT_ID/CLIENT_ID/CLIENT_SECRET` have no source; bare `KEY` entries are dropped when unset | §9 adds a job-level `env:` mapping them from `vars`/`secrets`, and the guard step now fails by name for all three |
| MAJOR: the new `image` job cannot push to GHCR — `ci.yml`'s workflow-level `contents: read` is inherited | §5.6 gives the job `permissions: {contents: read, packages: write}` and a preceding `docker/login-action` |
| MAJOR: the committed cap file had no route to `main` and contradicted §5.4's staging rule | §9 derives the cap from the PRs opened in the last 24 hours; no state file, no push to `main` |
| MINOR: `ci.yml`'s two hand-rolled pytest calls survive, so the strip list still lives in three places | §5.6 routes them through `scripts/verify.sh` |
| MINOR: §8.2 cited P4-AC3 for the same-family refusal, which is P4-AC1 | corrected, and §8.2 now carries a field contract rather than an example instance |
| MINOR: the `-v` bind is still exposed to MSYS path mangling | §6.3 uses `--mount type=bind` plus `MSYS_NO_PATHCONV=1` |
| MINOR: "refreshed per call" described caching-until-skew | corrected in §8.4 |
| MINOR: dispatch inputs are environment variables but the acceptance criteria test flags, with no stated precedence | §8.6 states `flags > environment > config.json` once and points both criteria at it |
| MINOR: `TESTOPS_HOME` still in §2 while §15 claimed it was removed | §2 now says what is true: it is read at import into `config.HOME` and never used again |

### 15.2 Round 3 — six of eight held, and the loop closed by measurement

The third pass verified only the eight round-2 fixes. Six held outright; two did not, and one new major surfaced while checking the third:

| Round-3 finding | Fix in revision 4 |
|---|---|
| MAJOR: `GITHUB_TOKEN` never reaches the container, so the cap query and draft PR have no credential (`checkout`'s persisted header covers `git push` only) | mapped at job level, forwarded as a bare `KEY` in the action's `env:`, added to the guard loop, and explained in §9 |
| MAJOR: §5.3 said "all three pytest steps"; `ci.yml` has two | corrected to "both pytest steps (the suite and the contract gate, on both matrix legs)" |
| MINOR: frontmatter said revision 2 while §15.1 described revision 3 | frontmatter now reads revision 4 |
| Observation: `docker/login-action@v3` is a major behind | bumped to `@v4` |

Applied and self-verified rather than re-reviewed — the checks are greps, and running a fourth review round to confirm a grep would cost more than it buys. The verification that matters, given round 2's failure mode, is that each claim here is matched by the document:

```
grep -c 'GITHUB_TOKEN' factory.yml section   -> 2 (job env) + 1 (bare passthrough) + 1 (guard) each
grep -c 'python -m pytest' ci.yml            -> 2
grep -n 'revision:' frontmatter              -> revision: 4
```

One recommendation was **rejected**: QA proposed moving the coordinator to `testops/factory/` with a `[project.scripts]` entry point. That would make the coordinator protected product code that only a ticket can change — circular, and contrary to `AGENTS.md`, which lets the Lead edit `factory/**` directly. The reasoning is recorded in §4.1 so the next reader does not re-open it.

Left open by design: QA could not build the image, run the suite, or reach GHCR. Those are the gates in §11, and they are gates precisely because they are unverified.

---

## 16. Before you believe any of this

1. **Which model families are deployable, with quota?** One family turns §7.1 from a mechanism into a labelled caveat.
2. **Are Actions permitted on private repos, and is there a budget?**
3. **Can the builder reach Jira and ADO?** If not, accept the `not_assessable` compromise, or budget for a self-hosted runner.
4. **Is a service identity acceptable for commits, and who signs off?**
5. **Is the suite green in a Linux container with no network?** The single measurement that decides whether the rest of this is real.

---

## 17. Multiple committers

The plan above assumes one person driving. Most of it already survives several — branches, worktrees, reports and PRs are per-ticket and cannot collide — but four shared resources break, and two of them break silently.

### 17.1 The four that break

**The board is a single mutable file.** Every ticket touches a row in `factory/TICKETS.md`, so two parallel builds produce two diffs against the same lines and the second PR conflicts every time. Fix: the coordinator never writes the board. Status is derived at read time from each ticket's `status:` frontmatter plus the open-PR state from the API. `TICKETS.md` becomes generated, or Lead-only and human-edited. The ticket *file* stays the per-ticket artefact, so builds conflict nowhere.

**Ticket IDs race.** Two people, or two Lead sessions, both take max+1 and both write `T-043`; both then build `factory/T-043` and the second push is rejected or clobbers the first. Fix: stop using a counter. Name tickets `T-<yyyymmdd>-<slug>`, unique by construction, or take the ID from a GitHub issue number, which the server allocates. Deciding this after a few hundred tickets is a renumbering exercise nobody wants.

**The cap starves people.** "PRs opened in the last 24 hours" is a repo-wide question, so one person's build consumes the cap and the next person's dispatch silently does nothing. Fix: the cap applies to the **scheduled** run only. A human pressing dispatch is itself the control, and the cost is bounded by `max_tickets_per_run` and the per-role budget.

**The concurrency group serialises everyone.** Keyed on `github.ref`, every dispatch on the default branch shares one group, so people queue behind each other — which accidentally prevents the same-ticket race but destroys parallelism. Fix, now in §9: `group: factory-${{ inputs.ticket || 'scheduled' }}`. Same ticket serialises; different tickets run together.

### 17.2 What no design removes

Two tickets built from the same base that touch the same file will conflict. That is ordinary team life, not a factory defect. Three practices keep it rare rather than routine:

- **Small tickets.** The factory is strongest on single-file or single-call-site changes, which is also what makes conflicts improbable and reviews possible.
- **Rebase on pickup, never during review.** The coordinator rebases onto current `main` when it starts a ticket. It must never rebase a PR a human is reading: that changes the diff under the reviewer and silently invalidates the approval.
- **Keep state files out of the builder's write scope.** `docs/state/testops.md` is a conflict magnet if every builder appends to it. `AGENTS.md` already gives `docs/**` to the Lead; the builder prompt must say so explicitly rather than relying on the convention.

### 17.3 Two runs on one machine

Separate machines cannot interfere. Two runs in one checkout share the SQLite store and the worktree directory, so the coordinator keeps the single-run lock the home version already has (`.factory/run.lock`, cleared only when the recorded pid is gone). Do not remove that check while porting.

### 17.4 What to change in the work orders

WO-1 carries the ticket-ID scheme and the board-derivation change; WO-4 implements both; WO-5 carries the rekeyed concurrency group and the scoped cap. The acceptance gates that already cover this are P5-AC2 (cap binds) and P5-AC3 (no duplicate PR per ticket) — both need re-reading as per-ticket rather than per-repo.
