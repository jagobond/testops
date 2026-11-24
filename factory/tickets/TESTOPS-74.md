---
id: TESTOPS-74
title: The Java reader drops an inherited prefix and invents a route from a constant
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-70
---

# TESTOPS-74 - Two ways the Java reader is silently wrong

## Why this exists

TESTOPS-70's reader is real - it lexes, beats the decoys, and reproduces 142 parsed files and 25 surfaces from a pinned
commit. Its review then found two shapes it gets **silently** wrong, which is the one failure mode a reader of source code
must not have: a wrong answer that looks like a right one.

1. **A parent-class `@RequestMapping` prefix is dropped.** A controller that extends a base class carrying the prefix
   loses its base path, so `GET /booking/{id}` is reported as `GET /{id}` - a route that does not exist, presented as one
   that does.
2. **A mapping whose path is a constant fabricates a bare `GET /`.** `@GetMapping(Paths.BOOKING)` yields a surface at `/`,
   which is not what the code says. A path this reader cannot resolve must be **unread**, with a reason, not invented.

Also from that review: the assessment sentence says "returned N items" where "items" is never defined on the page (it means
files fetched, and a reader can take it for evidence items or surfaces), and the level analyser declares `CODE` in `NEEDS`
while consuming none of it - which TESTOPS-72 fixes by consuming it, so this ticket only has to make the sentence's word
true.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | An inherited class-level prefix is either resolved (read the superclass in the same repository, one level, with the reason recorded) or the mapping is reported **unread** naming the superclass - never silently emitted without its prefix. Pinned by a fixture with a base controller carrying the prefix. |
| AC2 | A mapping path that is not a string literal is **unread**, with a reason naming the expression (`Paths.BOOKING`), and produces no surface. No surface may ever be emitted with a route the reader invented. Pinned. |
| AC3 | The unread cases appear where the run reports what it could not read - a reader of the run page can see "2 mappings unread: path is a constant" rather than a count that silently excludes them. |
| AC4 | The assessment sentence defines its noun: "returned 190 items" becomes something a reader can check - files fetched, named as files - or the sentence is reworded so no reader can mistake it for evidence. Pinned by a page test on the exact wording. |
| AC5 | Corpus re-read: state the surface count again after this ticket and explain any change from 25 - the number must move for a stated reason or not at all. |
| AC6 | Full suite green; contract suite green; no case-page golden changes; run pages change only for the stated reasons. |
