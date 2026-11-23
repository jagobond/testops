---
id: TESTOPS-7
title: Page-contract suite written by a qa-author who never sees the implementation
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-42
---

# TESTOPS-7 — A contract suite written blind

## Why this exists

Every page test we have was written by the people who built the page, and the goldens were generated from the pages
themselves - so they can say "the page changed" but never "the page is wrong". A misleading sentence, a silent skip, a
count with no unit would be pinned happily forever. A suite written by an author who has only the promise, and never the
implementation, is the only way to find out whether the pages keep their promises to someone who was not in the room.

## The brief

`factory/briefs/page-contracts.md` is the complete brief: 24 promises across the front page, runs index, run page, case
page and config page, plus what is out of scope. It states promises in a reader's words - no selectors, no template
names, no class names.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The qa-author receives `factory/briefs/page-contracts.md` **and nothing else**: no access to `testops/web/`, `testops/queries.py`, `tests/`, the goldens, or any build report. What was given is recorded verbatim in the build report, and the author states what it deliberately did not open. |
| AC2 | The suite drives a **running server** over HTTP as a reader would - following links from the front page rather than constructing URLs it should not know, except where the brief promises a URL is citable. No importing the app's modules, no reading its templates, no database queries to assert on presentation. |
| AC3 | **Every promise in the brief that can be tested over HTTP is tested**, and the mapping from promise number to test is listed. A promise that cannot be tested this way is named as such rather than dropped silently. |
| AC4 | The suite is **run by the reviewer, not the author**, against the live store. The first full run is reported as it came out, including every failure, with the page and the sentence that broke the promise. No test may be relaxed to make the run green without the reviewer agreeing which of the two causes applies. |
| AC5 | Each failure is triaged into exactly one of: **page breaks the promise**, or **brief promised too much** (with the corrected wording proposed). A suite adjusted to pass has told us nothing. |
| AC6 | The suite lives at `tests/test_page_contracts.py` (or a `tests/contracts/` file set) with its own marker, so it can be run against a server without touching the store and cannot be satisfied by regenerating goldens. |
| AC7 | No product code is changed by this ticket. Findings become their own tickets. |

## Notes

- The blindness is the product. If the author reads the source to make a test pass, the evidence is void.
- Record what the server was serving: project, run ids and a case id, so the result is reproducible.
- Expect failures. Report them; do not soften them.
