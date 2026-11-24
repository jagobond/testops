---
id: TESTOPS-90
title: The validator refuses the good explanation for naming its own citation
feature: F2
status: done
autonomy: build
depends_on: TESTOPS-88
---

# TESTOPS-90 - A citation id is not a fact, and a rejection deserves one repair

## The evidence

`deepseek-flash` was called with the real prompt for case `case-restfulbooker-levels-20261124T123451-05`. It returned valid
JSON with correct citations and four sentences of genuinely good prose. `parse_reply` accepted it. `violations` then
rejected it for **one** reason:

```
the number 2405, which no cited fact holds
```

2405 is the claim id. The model wrote `claim:2405` *in the prose* ("...claim:2405 is the claim whose record that gap
concerns"). The number scan reads every numeral in the sentence and demands it appear in a cited row, so a citation id
written in words is treated as a fabricated statistic. The guard is punishing the model for citing.

With this in place the feature serves **no explanations at all** against the real model, which is why the local page says
"the model's reply was not readable prose".

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A number that is part of a citation identifier written in prose (`claim:<id>`, `reason:<id>`) is not a fact and is not scanned. Pinned with the exact sentence above, asserting it is now accepted. A plain number that is not an id (`the number 7`) is still refused. |
| AC2 | The prompt says: cite identifiers in the `citations` array only; do not write them in the prose. Belt and braces, so the model is not relying on AC1. Pinned by asserting the instruction is in the system prompt and that the prompt version changes. |
| AC3 | One repair round: on rejection the model is asked once, with the exact violations quoted, to fix only those sentences. A second rejection falls back to the honest sentence and records the state as `rejected`. Pinned with a fake model that fails twice and a fake that fails once then succeeds. |
| AC4 | Measure the real thing: run the agent over **ten real cases** from the stored run against `deepseek-flash` (network is allowed here, this is the one ticket where it is the point), and report accept rate, mean tokens in/out per explanation, wall time, and the cost model used with any price marked as an assumption. If fewer than 7 of 10 are accepted, say so plainly and show the rejection reasons. |
| AC5 | No weakening: the four TESTOPS-88 lies still reject, the uncited sentence still rejects, agent=off pages still byte-identical, suites and contracts green. |
