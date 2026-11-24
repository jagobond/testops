---
id: TESTOPS-73
title: The case page names what it examined - sources as linked tags, up front
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-70
---

# TESTOPS-73 - How interconnected is this case?

## Why this exists

A finding is only as trustworthy as what it examined, and a reader should be able to see that without hunting. Today the
case page states neither the repositories behind the assertion nor the tracker items or pipeline runs that bear on it, so
a reader cannot tell an interconnected case (test code, product code, a ticket and a run) from a bare one.

Harry's framing: put the examined sources **up front as hyperlinked tags**, so the interconnection is visible at a glance -
and make it explicit when a case rests on the test repository alone, because that is a legitimate finding too, not a
lesser one.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The top of the case page carries a **source band**: one tag per examined source, before the statement. Each tag names the source *and* its kind, and links where a link exists. |
| AC2 | Kinds and their links: **test repository** (link to the file at the commit the assertion was read from, not to the repository root), **product repository** (link to the repository at that commit), **Jira issue** / **Azure DevOps work item** (link to the item) when one is linked, **pipeline run** (link to the run) when one is linked, and **requirements document** when one is attached. A kind that is not linked is not shown as a tag - an absent tag means "not part of this case", and the page says so in one line rather than leaving it ambiguous. |
| AC3 | The band distinguishes **examined** from **wanted but unavailable**: a source that was needed and could not be consulted appears as a dimmed tag reading "not consulted" with the reason, so a reader sees the blind spot at the same glance as the evidence. |
| AC4 | When a case rests on the test repository alone, the band says so in words a reader can act on - e.g. "assessed against test code only: the product's routes could not be consulted" - not as an empty space and not as a warning. |
| AC5 | Tags are keyboard-reachable, have accessible names that include the source kind, and do not rely on colour alone to distinguish "consulted" from "not consulted". |
| AC6 | The case page's existing promises hold: the page-promise contract suite passes, including any promise about the page's opening content, and the goldens are regenerated deliberately with the new band in the record. |
| AC7 | Full suite green; contract suite green. |
