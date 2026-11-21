# TICKETS — TestOps

The board is the record of what exists. Ticket files live in `factory/tickets/<id>.md`; the queue
is read from `main`, so a ticket that exists only on a branch is invisible and will not run.

Status values: `ready` (buildable now) · `blocked` (waiting on a decision or a predecessor) ·
`in-progress` · `needs-human` (built, awaiting Lead/PO) · `done` · `killed`.

Only `ready` and `blocked` are meaningful to a coordinator; sequencing prose in the status field
makes a ticket invisible.

| id | title | feature | status | note |
|----|-------|---------|--------|------|
| TESTOPS-1 | Factory scaffolding: git baseline, PRODUCT/ROLES/AGENTS, board | F0 | done | Lead work, no builder; pre-queue |
| TESTOPS-2 | Claim schema v2 — per-assertion subject, sources used and missing, `not_assessable` | F1 | proposed | Shape first; T3 depends on it |
| TESTOPS-3 | Level-fitness analyser emits one claim per assertion, with plain-language statement and proposed action | F1 | proposed | Needs T2; must not run in parallel |
| TESTOPS-4 | Source capability registry; Jira collector disconnected and invisible | F1 | proposed | Absence as a declared state |
| TESTOPS-5 | Case page rebuilt around the six sections; provenance labels; codes to footnote | F1 | proposed | Follows the approved UI review |
| TESTOPS-6 | Page-contract suite from qa-author, never shown the implementation | F1 | proposed | The suite a real team would keep |

`proposed` is a Lead placeholder meaning "argued for, not yet written as a ticket". Tickets are
written after the Product Owner has seen `PRODUCT.md` and `ROLES.md`, because criteria encode what
those documents decide.
