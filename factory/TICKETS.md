# TICKETS — TestOps

The board is the record of what exists. Ticket files live in `factory/tickets/<id>.md`; the queue
is read from `main`, so a ticket that exists only on a branch is invisible and will not run.

Status values: `ready` (buildable now) · `blocked` (waiting on a decision or a predecessor) ·
`in-progress` · `needs-human` (built, awaiting Lead/PO) · `done` · `killed`.

Only `ready` and `blocked` are meaningful to a coordinator; sequencing prose in the status field
makes a ticket invisible. `proposed` is a Lead placeholder: argued for, not yet written as a
ticket, because criteria encode what PRODUCT.md and ROLES.md decide.

| id | title | feature | status | note |
|----|-------|---------|--------|------|
| TESTOPS-1 | Factory scaffolding: git baseline, PRODUCT/ROLES/AGENTS, board | F0 | done | Lead work, no builder |
| TESTOPS-2 | Test harness baseline: pytest, one real test, dev extras | F1 | ready | **First.** Nothing else can be judged until a suite exists; today there are zero tests and pytest is not a declared dependency |
| TESTOPS-3 | Claim schema v2 — per-assertion subject, sources used and missing, `not_assessable` | F1 | blocked | Shape first; T4 depends on it |
| TESTOPS-4 | Level-fitness analyser emits one claim per assertion, with plain-language statement and proposed action | F1 | blocked | After T3 |
| TESTOPS-5 | Source capability registry; Jira collector disconnected and invisible | F1 | blocked | After T4 — absence as a declared state |
| TESTOPS-6 | Case page rebuilt around the six sections; provenance labels; codes to footnote | F1 | blocked | After T5 |
| TESTOPS-7 | Page-contract suite from qa-author, never shown the implementation | F1 | blocked | The suite a real team would keep |

Feature F1 = "a claim a developer can act on". F0 is scaffolding and carries no product outcome.

## Why the harness comes first

The factory's gate is a test run whose failure modes are distinguishable: pass, genuine failure,
and environment error. TestOps currently has **no tests** and `pytest` was installed only as a
side effect of this scaffolding. A reviewer asked to judge T3 against acceptance criteria with no
suite in the repo can only read the diff and take the builder's word for it — which is the
arrangement the factory exists to replace.
