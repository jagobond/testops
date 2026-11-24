---
id: TESTOPS-89
title: The managed identity is on the app and the agent still says it has no token
feature: F2
status: ready
autonomy: build
depends_on: TESTOPS-88
---

# TESTOPS-89 - Find out why the identity is not being used, and say so where a human can read it

## What is observed

Deployed on Container Apps (revision `testops--0000003`, image `testops:v2`, system-assigned identity
`3a887e71-88d6-4d22-b378-954d328ea710` with Cognitive Services User on `testops-resource`, `TESTOPS_FOUNDRY_ENDPOINT` and
`TESTOPS_AGENT_MODEL` set), a case page with `?agent=on` renders the honest fallback sentence: *"The model-written
explanation is not available: this deployment has no token from the environment, a managed identity or the az CLI."*

So `managed_identity_token()` returns `""` inside Azure. Locally the same page reaches the model (and the reply fails the
new citation validator, which is a different, known issue with the prompt). The identity exists; the token does not arrive.

Note: `az containerapp exec` cannot be used to look inside (ClusterExecFailure), so the tool has to tell us.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | `managed_identity_token()` records **why** it failed, not just that it did: the exception class, the HTTP status when there was one, the endpoint and api-version used, and the elapsed time. Stored where the ledger stores things, and printed on `/agent-check`. |
| AC2 | It tries the api-versions a Container Apps instance actually answers (`2018-02-01` and `2019-08-01`) and a timeout that a cold container can meet (10s, one retry), rather than one 3s attempt. Which combination answers is recorded. |
| AC3 | `/agent-check` is a plain page that answers, in words, for the current process: is the endpoint configured and what is it; is the model configured and what is it; did the environment supply a token (yes/no, never the value); did IMDS answer, with the status and cause if not; did `az` answer; and a single sentence at the top saying whether an explanation would be served right now. The token value must never appear in the page, a log line or the ledger - a test asserts the page contains no substring of the token it was given. |
| AC4 | The failure cause recorded today is replaced by the real one once AC1 exists: the build report states what the cause was in the deployed container, or states plainly that it could not be determined and what it narrowed it to. |
| AC5 | No weakening: agent=off pages still byte-identical; suites and contracts green; the citation validator from TESTOPS-88 is untouched. |

## Note

The honest fallback is correct behaviour and stays. This ticket is about the cause being invisible, not about the fallback.
