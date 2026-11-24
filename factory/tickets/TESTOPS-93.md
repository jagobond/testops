---
id: TESTOPS-93
title: The narrator runs as a Foundry agent, and the page can say which route served it
feature: F2
status: done
autonomy: build
depends_on: TESTOPS-92
---

# TESTOPS-93 - A third variant that is an actual Foundry agent

## What exists, verified today

A **hosted agent** is deployed in the Foundry project and answers:

```
POST https://testops-resource.services.ai.azure.com/api/projects/testops/agents/testops-narrator/endpoint/protocols/openai/responses?api-version=v1
header: api-key: <the same Cognitive Services key the app already holds as the secret testops-agent-token>
body:   {"input": "{\"system\": \"...\", \"user\": \"...\"}"}
```

Its reply is OpenAI-shaped (`output[].content[].text`, type `output_text`). Its text is the model's message content
followed by a final line `USAGE {"prompt_tokens": n, "completion_tokens": n, "model": "deepseek-flash",
"served_by": "foundry-hosted-agent"}`. A live invocation returned `ready` plus that line. The agent runs with its own
managed identity, which now holds `Cognitive Services User`, `Cognitive Services OpenAI User` and `Azure AI Developer`
on the account/project - role propagation took ~2 minutes, so a first 401 is not a defect.

**A managed (prompt) agent cannot be used on this subscription** - `POST /openai/agents/{name}/responses` answers
`403 Managed agents require an enabled subscription`. Hosted agents do work. Do not spend time on prompt agents.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | `?agent=foundry` renders an explanation produced **by the agent route**. Same page, same block, same label, and the block names the route it came from (`served by: foundry-hosted-agent`) rather than pretending the two are the same. |
| AC2 | The citation guard is unchanged and applies identically: the agent's prose passes through the same parser and the same `violations` check as the model route, and a reply that fails falls back to the same honest sentence with the same state names. A test feeds a fabricated verb through the agent route and asserts it is refused. |
| AC3 | The ledger records the route per explanation (`model` / `foundry`), the agent's own token counts from its `USAGE` line (not an estimate), its wall time, and failures by kind (unreachable, timeout, non-200, missing text, rejected). `/agent-report` shows the routes side by side with votes, so cost per route is answerable. |
| AC4 | Failure is honest and cheap: if the agent endpoint is unreachable or slow (>20s), the page falls back to the model route only when explicitly asked to (`TESTOPS_AGENT_FALLBACK=model`), otherwise it renders the honest failure sentence. Never silently substitute one route for the other - that would make the A/B a lie. |
| AC5 | `agent=off` and no-parameter remain byte-identical over all 275 real pages; `agent=on` behaviour is unchanged; suites and contracts green. |
| AC6 | The credential is read from `TESTOPS_AGENT_TOKEN` only. No key in code, tests, fixtures, logs or a page - a test asserts no substring of a supplied token is rendered on `/agent-check`, `/agent-report` or a case page after an agent call. |

## Notes for the builder

- The endpoint and model belong in settings (`TESTOPS_AGENT_ENDPOINT`, `TESTOPS_AGENT_NAME`), defaulting to the values
  above, so the route is configuration rather than a constant.
- Tests must not call the live agent. Use a local stub HTTP server, and pin the reply-shape parsing with the real
  response body quoted above. One optional live smoke check is allowed but must skip when no token is present.
- Keep `client.py`'s existing model route untouched; add the agent route beside it.
