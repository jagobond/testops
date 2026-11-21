# PRODUCT — TestOps

TestOps reads a repository pair — a product repo and its behavioural test repo — and reports what
the tests actually establish, at what level, and what they claim but never check. Its output is a
*case*: one claim, the evidence behind it, what it could not check, and a proposed action a
development team can accept or reject.

It exists because "the suite is green" is a statement about coverage the suite does not support.
A test can cross four layers to assert one field, or assert an accessibility guarantee while never
starting a browser, and nothing in a passing run says so.

## Outcomes

Observable results, not features. A ticket that does not move one of these is not worth building.

| # | Outcome | Why it matters | Status |
|---|---------|----------------|--------|
| 1 | **A developer can decide what to do with a claim without being told what a claim is.** | The tool's only product is a decision. A finding a reader cannot understand is a finding nobody acts on, and the team stops opening the UI. | in progress |
| 2 | **Every claim names the exact assertion it came from, the file and line, and the sources it could not consult.** | A finding is an accusation. It has to be checkable against the code, and it has to admit its blind spots — otherwise "no problems found" and "we could not look" are indistinguishable. | in progress |
| 3 | **A team can see where a test buys a level it does not need, and where it claims a guarantee it never establishes.** | Level fitness is the waste nobody measures: slow suites for claims a response body settles, and gaps where a claim needs a browser that was never started. | in progress |
| 4 | **The tool runs on the sources a team actually has — two repositories, no issue tracker.** | At Quilter there is no route to Jira or ADO from Foundry and no Jira PAT can be issued because of breach risk; only GitHub, through an internal MCP server. A tool that requires a tracker is unusable there, and a tool that treats a missing source as an empty one lies. | in progress |
| 5 | **No finding can be silenced without a recorded, reversible decision.** | Suppression is the failure mode of every analysis tool: the first noisy finding trains the team to switch it off. A decision must name its actor and be undoable. | shipped (pre-factory) |

## What this is not

Not a test runner, not a coverage percentage, and not a code-quality linter. It does not judge
whether a test is *correct* — it judges what level of interaction a claim needs, and whether the
test reaches that level.
