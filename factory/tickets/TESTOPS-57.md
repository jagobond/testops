---
id: TESTOPS-57
title: The claims the tool could not place have no page of their own
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-52
---

# TESTOPS-57 - The claims the tool could not place have no page of their own

## Why this exists

The T52 review found that the `soft` badge is defined, toned, unit-tested - and rendered nowhere, because only claims
whose verdict is in `RAISES = {review, gap, duplicate}` become cases. `unplaced` never becomes a case, so the one verdict
whose point is "I could not tell" has no page. The store holds 351 such claims.

That is backwards. An unplaced claim is the most actionable thing the tool produces: it says the suite and the code do not
meet, which is what a reader most needs to see and fix. Right now those claims exist only as a count and a paragraph on
the run page.

## The decision this ticket implements

Option (b), not (a):

- **(a) A case page per unplaced claim** - rejected: it would create 351 near-identical pages whose content is "I could
  not place this", inflating case counts and burying real findings.
- **(b) A per-run section listing the unplaced claims, each with its own anchor and its own page-addressable identity** -
  chosen: a reader can see all of them for a run, link to one, and the run page stays honest about what it could not do.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A run page gives the unplaced claims **a section of their own**, not a sentence: each listed with the step's words, the two nearest patterns, and a stable anchor a reader can cite (`/run/<id>#unplaced-<n>` or a per-claim URL). |
| AC2 | Each entry carries the **soft** tone - the dashed, dimmed treatment - so an unplaced claim is visibly less settled than a placed one, satisfying P20 where unplaced claims are actually shown. This is the first place the soft badge is rendered on a served page; a test asserts the class is present and is NOT the alarm class. |
| AC3 | The count on the run page and the number of entries in the section are the same number, derived - a test renders a run with a known unplaced count and asserts they agree. |
| AC4 | Nothing about placed claims, verdicts or case pages changes: case-page goldens byte-identical, CotW 94/90/1/1/2 and ReqOverflow 17/17 unchanged. |
| AC5 | The section is honest about what a reader can do: it says these are not assessed rather than merely absent, and where the nearest patterns are known it says why they did not match. No banned phrases, no "unsupported ecosystem". |
| AC6 | Contract suite: P20 passes where it applies; every other contract test unchanged in outcome (no new failures). Full suite green. |
