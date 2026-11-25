---
id: TESTOPS-102
title: The repository carries no personal identifiers
feature: F2
status: building
autonomy: build
depends_on: TESTOPS-93
---

# TESTOPS-102 - Portable to a colleague's GitHub org

## Why

Harry wants to push this repository to a Quilter organisation so colleagues can run it. Today the tree carries his
subscription id, resource group and account names, a tailnet address, absolute `C:/Users/<name>/...` paths and baked
deployment defaults. A scan of the tracked files found 471 matches: 55 Azure identifiers in 20 files, 324 absolute
paths in 154 files, 6 GUIDs, 17 tailnet addresses.

## The rule this ticket establishes

**Deployment identifiers are configuration, never source.** Anything that names who Harry is, what he pays for or where
his machine keeps its files must come from the environment, with an honest "unconfigured" state when it is absent -
never an invented default that silently points at his tenant.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | `testops/judgement/client.py` holds no account, project or host name. `DEFAULT_PROJECT` and every literal `*.services.ai.azure.com` host are gone; the account and project arrive from `TESTOPS_FOUNDRY_ACCOUNT` / `TESTOPS_AGENT_PROJECT`, and with either unset the route reports **unconfigured** naming the variable instead of building a URL. |
| AC2 | `agents/narrator/deploy.py` takes the project endpoint and agent name from the environment and exits with a named error when unset; no default account, project or agent name. |
| AC3 | `cost_probe.py` and `scripts/draw_azure_diagram.py` take the subscription id from `AZURE_SUBSCRIPTION_ID`; no GUID literal remains. |
| AC4 | The scratch deployment scripts that only ever worked on Harry's machine (`deploy_hello.py`, `invoke_hello.py`, `poll_agent.py`, `hello.zip`) are deleted from the repository, not merely ignored. |
| AC5 | `scripts/check_no_secrets.py` scans the tracked tree and fails on: a GUID-shaped identifier outside `tests/`, an absolute home directory (`C:\Users\<name>`, `/home/<name>`), an Azure host name matching `*.services.ai.azure.com` or `*.azurecontainerapps.io` outside a docstring example, a tailnet address (`100.64.0.0/10`), and the credential shapes the store boundary already knows. It prints file:line for each and exits non-zero; `python scripts/check_no_secrets.py` on a clean tree exits 0 and says how many files it read. |
| AC6 | CI runs AC5 in its own job, so a future commit cannot quietly reintroduce an identifier. |
| AC7 | `.gitignore` covers `*.zip`, `*.log`, `.tmp/`, `*.bak`, and the export directory; `git check-ignore -v` proves each line. |
| AC8 | `SECURITY.md` states the policy in one page: no credentials in the tree, configuration through the environment, what to do if a secret is committed, and the fact that this repository's history is squashed on export so an old commit cannot leak. |
| AC9 | `docs/DEPLOYING.md` lists every variable the app reads with a placeholder value and what it is for. No real identifiers appear in it. |
| AC10 | The suite is green, including the two tests that pin the derived agent URL - they set the variables rather than relying on a baked account name. |
