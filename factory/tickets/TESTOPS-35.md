---
id: TESTOPS-35
title: A reviewer's fixture case is sitting in Harry's live store
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-34
---

# TESTOPS-35 — Test data must not reach the live store

## Finding

`/case/rev-duplicate` renders on the live server. Its case row is `{id: rev-duplicate, run_id:
reqoverflow-dup-20261122T090439, analyser: "x"}` — a case written by a review session, with an analyser name that
does not exist, reachable from the Product Owner's dashboard. The Product Owner opened it and asked whether it was
one of his own claims.

Whatever else is true, a review harness wrote into `data/testops.db` and the result became a page a reader could
act on.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The `rev-duplicate` case and any other case whose `analyser` is not a registered analyser are removed from the live store by a documented, re-runnable command (`testops scrub-fixtures --dry-run` then `--yes`), not by hand-editing SQLite. Report exactly what was removed, with row counts and ids. |
| AC2 | A case whose analyser is not registered cannot render: the page answers 404 with the TESTOPS-30 "no longer in the store" page, rather than a page built from a fixture. |
| AC3 | The test suite cannot write to `data/`: a guard fails any test that opens the real store outside a declared read-only path, and the suite runs green against a temporary store. |
| AC4 | Review prompts in `factory/prompts/` say plainly that fixtures belong in a copy of the store, and the reviewer workflow used today (worktree + copy) is written down where a reviewer will read it. |
| AC5 | Verdicts unchanged; no surviving case page changes bytes. |

## Notes

- This is the second time today that test apparatus reached something the Product Owner could see. The first was
  the fixture corpus described as "synthetic" when it was copied. Both are the same fault: the boundary between
  what we know and what we assume was not enforced by anything but care.
