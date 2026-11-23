---
id: TESTOPS-54
title: Every page leads somewhere - a case links to its run, and /config is reachable
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-53
---

# TESTOPS-54 - Every page leads somewhere

## Why this exists

The blind author could not walk from a case back to the run that produced it (the case page links only `/`, `/runs` and
GitHub), and could not reach `/config` from any page at all - it exists only if you know the URL. The brief's P5 forbids
exactly that: no dead ends, and no page that only exists if you already know its address.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A case page links to **its run**, and the link says what it is (not "back" with no context). A test asserts the case page's hrefs include the run page for the run that contains it, on at least three cases from different analysers. |
| AC2 | `/config` is reachable from **every** page by a link a reader can see and understand, with the same affordance everywhere. |
| AC3 | Round trip: run → case → back to the same run, and the run page lists the case. A test walks it with `html.parser` and no URL construction beyond what is linked. |
| AC4 | No new dead ends: every href on every page resolves to a 200 (excluding external links), asserted across front, runs, run, case and config. |
| AC5 | Contract suite **P05** (both tests) passes and nothing else regresses; goldens regenerated only for the added links, with visible-text diffs shown to be the new link labels only. |
