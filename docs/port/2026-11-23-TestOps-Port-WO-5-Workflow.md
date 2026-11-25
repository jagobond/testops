---
phase: 5
title: The factory workflow
prereqs: [WO-4 complete, D2 and D5 answered]
deliverables: [.github/workflows/factory.yml]
gate: a dispatch with a ticket id builds exactly that ticket; an unset secret fails loudly by name
stop-if: you need to create a secret, enable Actions, or change a repo setting — those are human steps
---

# WO-5 — The factory workflow

## Scope

One file. Every credential it needs must already exist as a repository secret or variable; creating them is a human step and is on your stop list.

## Preconditions

```bash
gh secret list 2>/dev/null || echo "check the repository settings page"
gh variable list 2>/dev/null
```

Required, and the workflow fails loudly if any is absent:

| Name | Kind | Used for |
|---|---|---|
| `FACTORY_READ_PAT` | secret | the product's collectors, which need a read token to clone the repos under analysis |
| `JIRA_SITE` | variable | Jira base URL |
| `JIRA_EMAIL`, `JIRA_API_TOKEN` | secret | Jira credentials |
| `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` | variable | token endpoint |
| `AZURE_CLIENT_SECRET` | secret | token endpoint |

`GITHUB_TOKEN` is provided by Actions and is **not** in a step's environment by default — `checkout` receives it as its own input. The coordinator needs it for the PR count and the draft PR, so map it explicitly.

## Do this

Create `.github/workflows/factory.yml`:

```yaml
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
  # Keyed on the ticket, not the ref. Keying on github.ref serialises every user onto one group;
  # this way the same ticket serialises and different tickets run in parallel.
  group: factory-${{ inputs.ticket || 'scheduled' }}
  cancel-in-progress: false

permissions:
  contents: write
  pull-requests: write

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 90
    env:
      AZURE_TENANT_ID: ${{ vars.AZURE_TENANT_ID }}
      AZURE_CLIENT_ID: ${{ vars.AZURE_CLIENT_ID }}
      AZURE_CLIENT_SECRET: ${{ secrets.AZURE_CLIENT_SECRET }}
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

Four things that will otherwise cost a day:

- **The secrets file goes inside the mounted workspace**, under a gitignored directory. A path under `$RUNNER_TEMP` is a host path the container cannot see; the run then dies on `KeyError: 'GITHUB_PAT'`.
- **A bare `KEY` in the action's `env:` input is omitted entirely when the variable is unset**, rather than passed as empty. That is why the guard checks each name.
- **`push: never` here.** `ci.yml` builds and publishes the image; this job should not make image freshness depend on whether a ticket got built.
- **Do not add `id-token: write`.** There is no OIDC exchange in this design; the token call is a client-credentials request made by the container.

## Acceptance

Paste the raw output of each:

```bash
# 1. YAML is valid
python -c "import yaml,sys;yaml.safe_load(open('.github/workflows/factory.yml'))" && echo VALID

# 2. dispatch with a ticket id builds that ticket  (needs a human to press Run workflow)
#    record the run URL

# 3. guard fails by name with a credential unset
#    temporarily unset one secret, dispatch, confirm the message names it, restore the secret
#    DO NOT leave the repository in the unset state
```

Pass requires: valid YAML, one run that built the named ticket, and one run that failed at the guard naming the missing variable rather than raising a traceback.

## Stop list — do not work around

- Do not create, rotate or delete a secret or variable. Ask.
- Do not enable or disable Actions, change branch protection, or change repository visibility.
- Do not add `permissions` beyond `contents: write` and `pull-requests: write`.
- Do not disable the guard to get a green run.
- Do not commit `.factory/secrets.env`.

## When done

Append a row to `docs/port/PROGRESS.md` with the run URL of the successful dispatch and the guard-failure run, and name any secret the operator still has to create.
