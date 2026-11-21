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
| TESTOPS-2 | Test harness baseline: pytest, one real test, dev extras | F1 | done | 17 tests; PR #1 merged into feature/f1 as 5c008b7 after a PASS review |
| TESTOPS-3 | Claim schema v2 — per-assertion subject, sources used and missing, `not_assessable` | F1 | done | 53 tests; PR #2 merged as 616d5d8 after a PASS review |
| TESTOPS-4 | Level-fitness analyser emits one claim per assertion, with plain-language statement and proposed action | F1 | done | 84 tests; PR #3 merged as 595894e after a PASS review |
| TESTOPS-5 | Source capability registry; Jira collector disconnected and invisible | F1 | blocked | After T4 — absence as a declared state |
| TESTOPS-6 | Case page rebuilt around the six sections; provenance labels; codes to footnote | F1 | blocked | After TESTOPS-10: a page is only as useful as the claims it shows, and half of them currently say nothing |
| TESTOPS-7 | Page-contract suite from qa-author, never shown the implementation | F1 | blocked | The suite a real team would keep |
| TESTOPS-8 | Packaging proof: install into a fresh venv and import through the distribution | F1 | blocked | Reviewer concern 3 on TESTOPS-2: `test_packaging` imports via sys.path, so a broken `package-data` stays green |
| TESTOPS-9 | Stale claim vocabulary: `schema.sql`, the `Claim` docstring and `analysers/base.py` describe verdicts (`optimal`/`overbuilt`/`necessary`) the analyser abandoned | F1 | blocked | Found by the TESTOPS-2 builder; schema comments that lie mislead every reader |

Feature F1 = "a claim a developer can act on". F0 is scaffolding and carries no product outcome.

## Why the harness comes first

The factory's gate is a test run whose failure modes are distinguishable: pass, genuine failure,
and environment error. TestOps currently has **no tests** and `pytest` was installed only as a
side effect of this scaffolding. A reviewer asked to judge T3 against acceptance criteria with no
suite in the repo can only read the diff and take the builder's word for it — which is the
arrangement the factory exists to replace.
| TESTOPS-10 | Classification coverage: 51% of the real corpus is `unplaced` | F1 | done | 48 → 0 unplaced, gaps unchanged; PR #4 merged after a PASS review |
| TESTOPS-11 | Restraint: a claim is not `distinct` because one of its words is familiar | F1 | ready | Reviewer found "that count is correct for the store it was run against" promoted to `distinct` on the word "store" — the ticket's own example of genuine ambiguity |
