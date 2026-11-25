---
id: TESTOPS-94
title: The platform already offers a token, and the app never asked for it
feature: F2
status: queued
autonomy: build
depends_on: TESTOPS-93
---

# TESTOPS-94 - Ask for the token the platform already provides

## Evidence

The hosted Foundry agent's runtime shows `IDENTITY_ENDPOINT=http://<tailnet-address>/msi/token` and `IDENTITY_HEADER`
(44 chars), and `DefaultAzureCredential` obtained a working token from it. The TestOps container app tried only
`169.254.169.254`, which answers `Connection refused`, and then fell back to a stored key.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | `managed_identity_token()` tries, in order: `IDENTITY_ENDPOINT` with `IDENTITY_HEADER` and the resource in the query string, then IMDS on both api-versions, then the environment token. Each attempt records its source, status, elapsed ms and cause on `/agent-check`. |
| AC2 | If the platform endpoint answers, `/agent-check` says so, and the deployment runs with `TESTOPS_AGENT_TOKEN` unset - proven by a deployment with the secret removed. |
| AC3 | The stored key is deleted only after a page renders an explanation with no key present, and the deployment report says which source served it. |
| AC4 | If the platform endpoint does not answer in this environment, the finding is recorded honestly and the key stays, with the reason stated. |
