---
phase: 1
title: Move the repository and set its ground rules
prereqs: [D1, D2]
deliverables:
  - .gitattributes
  - .gitignore (three additions)
  - scripts/verify.sh
  - docs/state/testops.md
  - .github/workflows/ci.yml (three changes)
  - factory/tickets/ (migration ticket)
gate: ./scripts/verify.sh reports the recorded baseline count, and git check-ignore passes for both secrets paths
stop-if: no write access to the target repo; Actions disabled; the suite is not green before any change
---

# WO-1 — Move the repository and set its ground rules

## Scope

Phase 1 of the plan, and only phase 1. The product code under `testops/` is **not** in scope: this work order changes configuration, adds one script, adds one document, and adds one CI job.

## Preconditions — confirm by running, not by assuming

```bash
git remote -v                       # expect the source remote, or the target if already mirrored
git status --porcelain              # expect empty; a dirty tree makes the baseline meaningless
python -V                           # expect 3.11 or 3.12
ls .gitignore .github/workflows/ci.yml
```

Stop if the tree is dirty. A baseline taken on a dirty tree is not a baseline.

## Do this

**1. Mirror the repository.** If `DECISIONS.md` says the target repo exists and is empty:

```bash
git clone --mirror <source-url> /tmp/testops-mirror.git
cd /tmp/testops-mirror.git
git remote set-url origin <target-url>
git push --mirror origin
```

`--mirror` carries every ref and deletes anything absent at the destination. Then clone the target normally and check **in the new clone** — inside a mirror clone `git branch -r` is empty by design, because the refs live in `refs/*`:

```bash
git log --oneline -3
git branch -r | wc -l
ls factory/tickets/*.md | wc -l
```

All three must match the source. If the target already contains the history, skip this step and say so.

**2. Line endings and ignores**, committed before anything else:

```bash
printf '* text=auto eol=lf\n*.bat text eol=crlf\n' > .gitattributes
cat >> .gitignore <<'EOF'
.env
*.env
.factory/
EOF
git add .gitattributes .gitignore
git commit -m "Port: line endings, ignore secrets and factory state"
```

`.gitignore` does **not** currently contain `.env`. This step adds it. Do not assume it is already there.

**3. `scripts/verify.sh`** — the single canonical test command:

```bash
#!/usr/bin/env bash
set -euo pipefail
PY="${PY:-python}"
exec env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX \
     PYTHONNOUSERSITE=1 "$PY" -m pytest "$@" -q
```

`chmod +x scripts/verify.sh`. Then record the **baseline**:

```bash
pip install -e ".[dev]"
./scripts/verify.sh --collect-only | tail -1
./scripts/verify.sh
```

Write both numbers — collected and passed — into a new migration ticket `factory/tickets/T-<yyyymmdd>-port-baseline.md`, with the commit id. **Do not put the number in any plan or README**; it changes whenever the suite grows.

**4. `docs/state/testops.md`** — one page, from what the existing tickets and `AGENTS.md` already say: the store schema version, the `not_assessable`-not-zero rule, which ecosystems extract and which only detect, the current baseline verdict numbers, and the constraints that look like bugs but are deliberate. Do not invent facts; if you cannot establish one, write "not established" and list it for the operator.

**5. `.github/workflows/ci.yml`** — three changes, and no others. Keep the matrix, the contract gate and the render job exactly as they are.

- Route the **two** existing pytest steps through `./scripts/verify.sh`, keeping their `tee` and their path argument. There are two, in the `suite` job; the render job runs a script, not pytest.
- Add a job `image` that builds the devcontainer, with `permissions: {contents: read, packages: write}` at job level, a `docker/login-action@v4` step for `ghcr.io`, and `devcontainers/ci@v0.3` with `push: filter` / `refFilterForPush: refs/heads/main`.
- Do not touch `.devcontainer/` itself; that is WO-2 and the job will fail until it exists. If that is unacceptable, comment the job out with a `TODO WO-2` and say so in the report.

## Ticket IDs

If `DECISIONS.md` recorded a change of ID scheme, apply it to any ticket you create here (`T-<yyyymmdd>-<slug>`), not the old counter.

## Files you may create or edit

`.gitattributes`, `.gitignore`, `scripts/verify.sh`, `docs/state/testops.md`, `.github/workflows/ci.yml`, `factory/tickets/T-<date>-port-baseline.md`. Nothing under `testops/`.

## Acceptance — run it, paste the raw output

```bash
git check-ignore -q .env && echo "OK env"
git check-ignore -q .factory/secrets.env && echo "OK factory"
./scripts/verify.sh | tail -3
git status --porcelain
```

Pass requires: both `OK` lines, a pass count matching the migration ticket, and an empty `git status`.

## Stop list — do not work around

- Do not create the repo, secrets, or branch protection rules.
- Do not edit anything under `testops/`. If a test fails, stop and report it: a red suite at this gate means the port is not ready, and fixing product code here would be a factory violation.
- Do not disable, skip or `xfail` a test to reach a green run.
- Do not push to a protected branch.

## When done

Append a row to `docs/port/PROGRESS.md` with the baseline numbers, the commit id, and anything you could not establish. Then stop.
