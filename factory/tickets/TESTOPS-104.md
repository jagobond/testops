---
id: TESTOPS-104
title: A fresh install starts with no projects
feature: F2
status: building
autonomy: build
depends_on: TESTOPS-38
---

# TESTOPS-104 - The shipped tree names no project at all

## Why

`testops/config.py` still holds `LEGACY_PROJECTS`: four `Project` records (`demo-product`, `testops`, `demo-service`,
`demo-booking`) with owner/name coordinates, an ADO org and pipeline ids. Its docstring is right that a running build
never resolves it - only `store/migrate.py` reads it, to carry a pre-TESTOPS-38 database forward. But the repository is
being handed to an organisation that has no such database, so the seed's only remaining effect is to name the projects
this tool was demonstrated on in a file every reader opens. On a fresh store it must create nothing.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | `LEGACY_PROJECTS` is an empty dict (or removed entirely, with `store/migrate.py` not importing it). Whichever shape you choose, the migration must still run on a **pre-TESTOPS-38** store without error - it carries whatever the seed contained, and the seed now contains nothing. Say in the report which shape you chose and why. |
| AC2 | A fresh store has no projects: prove it by creating one in a temp directory, running the migration path, and asserting `project` and `service` are empty. Paste the command and the count. |
| AC3 | Nothing in `tests/` depended on the four projects existing implicitly. If something did, it now creates the project it needs through the store (the `/config` path) rather than inheriting a seed row - and the test still asserts what it asserted before. Name every test you changed and the reason. |
| AC4 | The comment left in place says what happened to the seed and why, in a sentence a reader in another organisation can act on: this build ships with no projects, and a project is added through `/config` as rows. Do not leave a comment that explains a seed which no longer exists. |
| AC5 | Full suite green; quote the count. `scripts/check_no_secrets.py` still clean. |
| AC6 | If any documentation, ticket or report claims a fresh install comes with the demo projects, correct it - `docs/REDACTION.md` in particular, since it currently implies the tree is clean while this seed remained. |

## Notes

- `demo-booking`'s test repo names a third-party GitHub account (`m-pujic-levi9-com`) and `demo-service` names
  `reqnroll`. Both are public upstream projects and both disappear with the seed, which is the point: after this ticket
  the only third-party names left in the tree are the licence attribution files named in TESTOPS-103's report.
- Do not touch the migration's *structure*, only its data. An empty seed must be a legitimate no-op, not a branch that
  is skipped by accident.
