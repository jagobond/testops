---
id: TESTOPS-101
title: A default that names the account where the project belongs
feature: F2
status: queued
autonomy: build
depends_on: TESTOPS-93
---

# TESTOPS-101 - The derived agent endpoint

## The evidence

`agent_endpoint()` defaults the project to `DEFAULT_PROJECT` and builds
`https://{project}.services.ai.azure.com/api/projects/{project}/...`. On this subscription the account is
`<foundry-account>` and the project is `testops`, so the derived URL was wrong and every `?agent=foundry` call 404'd until
`TESTOPS_AGENT_ROUTE_ENDPOINT` was set by hand. `/agent-check` said "derived from the project and the agent name" while
being wrong, which reads as authoritative.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The project name is configuration with no default that pretends to be derived: an unset `TESTOPS_AGENT_PROJECT` renders the route as **unconfigured**, naming the variable, rather than inventing a URL. |
| AC2 | `agent_endpoint()` never derives the account from the project or the project from the account; both are stated or the route is unconfigured. |
| AC3 | `/agent-check` says which variable supplied each part, and a test pins the sentence for "set", "derived", and "unconfigured". |
