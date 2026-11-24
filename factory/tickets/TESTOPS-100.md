---
id: TESTOPS-100
title: The store must not be SQLite over an SMB share
feature: F2
status: queued
autonomy: build
depends_on: TESTOPS-93
---

# TESTOPS-100 - Persistence that survives a restart

## The evidence

Mounting the Azure Files share at `/app/data` and running a schema migration killed the deployment: two warm revisions
opened the same `testops.db` and `ALTER TABLE agent_call ADD COLUMN route ...` failed with `database is locked`. The
mount was removed for the demo, so votes and cached explanations now die with the revision.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The store is one of: a local disk with an explicit export/import to blob storage, or a server-side database (Postgres/MySQL) reached over the network - decided in the ticket, with the cost and failure modes written down. SQLite on SMB is not an option. |
| AC2 | A migration runs exactly once, serialised: two replicas starting together must not both attempt it, proved by starting two against the same store in a test. |
| AC3 | Votes, explanation cache and the ledger survive a revision restart, proved by casting a vote, restarting, and reading it back. |
| AC4 | The deployment keeps a single-writer path for the ledger, and the app says which store it is using on `/agent-check`. |
