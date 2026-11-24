---
id: TESTOPS-98
title: The gate - what a candidate must prove before it becomes a finding
feature: F3
status: queued
autonomy: build
depends_on: TESTOPS-97
---

# TESTOPS-98 - Rules dispose

## Shape

Each candidate kind has a deterministic gate. Nothing passes on the agent's word.

| candidate kind | gate |
|---|---|
| wrong level | the claimed product route must exist in the stored surface at that commit, and the assertion's binding must not already reach that layer |
| duplicate of product | the product's own claim for that route must be present, and the test's assertion must match its words |
| duplicate of another test | the other assertion must exist with different wording, and both must be in the same suite scope |
| asserts nothing | the asserting step must have no assertion verb, proved against the step definition body |
| unverifiable | rejected by default, with the reason recorded |

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Every gate is a pure function over stored rows, unit-tested against one accepting and one rejecting fixture, and cannot call the network or a model. |
| AC2 | A passed candidate becomes a case that says, in words: proposed by `<agent> <version>`, verified by `<rule>`, with links to the rows it rests on. |
| AC3 | Every rejection is recorded with the gate's reason, and `/agent-report` shows **acceptance rate per candidate kind** - the number that decides whether proposals are worth running. |
| AC4 | A proven non-regression: with proposals on and every candidate rejected, the case set is byte-identical to a run with proposals off. |
