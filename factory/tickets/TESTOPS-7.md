---
id: TESTOPS-7
title: Page-contract suite written by a qa-author who never sees the implementation
feature: F1
status: blocked
autonomy: build
depends_on: TESTOPS-42
---

# TESTOPS-7 — A contract suite written blind

## Why this exists

Every page test we have was written by the people who built the page. A suite written by an author who has only the
brief - what a page promises a reader - is the only way to find out whether the page keeps those promises to someone who
was not in the room.

## Blocked on

TESTOPS-42 decides whether case pages and their contracts are stable enough to pin, and whether the corpus the suite is
written against (CotW + ReqOverflow, or a second ecosystem) is the one that survives. Writing the suite first means
rewriting it.

## Acceptance criteria (draft - finalise once T42 lands)

| id | criterion |
|----|-----------|
| AC1 | The qa-author profile receives `factory/briefs/page-contracts.md` and **no access** to `testops/web/`, goldens, or existing page tests. Record what was given. |
| AC2 | The brief states each page's promise in a reader's words - not selectors, not template names. |
| AC3 | The suite tests those promises against a running server, and is run by the reviewer, not the author. |
| AC4 | The first run's results are reported even where ugly: every failure is either a page that breaks its promise or a brief that promised too much. |
| AC5 | The suite lives outside the page-author's test files, so regenerating goldens cannot quietly satisfy it. |

## Notes

- Do not write this until T42 is decided; the corpus it targets is the thing T42 chooses.
