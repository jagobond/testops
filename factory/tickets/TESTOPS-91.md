---
id: TESTOPS-91
title: The reply that is 90 percent of an answer is thrown away instead of repaired
feature: F2
status: done
autonomy: build
depends_on: TESTOPS-90
---

# TESTOPS-91 - Repair the reply that forgot its citations

## Why this exists

TESTOPS-90 was accepted and its review named one defect it should have fixed rather than reported: **three of ten real
calls returned an explanation with no `citations` array at all**, `parse_reply` classified the whole reply `malformed`, and
the repair round - built in that same ticket, whose entire purpose is "the reply was almost usable, ask once with the faults
quoted" - never saw it. The reviewer's live rerun then flipped one failure to accepted and, separately, flipped the flagship
case to rejected: the 70% is a per-case coin with known bias, not a property of the feature.

A reply with prose but no citations is not malformed in the sense that matters. It is one field short.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A reply with a JSON object, an `explanation`, and no/damaged `citations` is classified **repairable**, not `malformed`, and triggers the repair round with the exact fault quoted ("you wrote the explanation but omitted the citations array - add one entry per sentence"). Pinned: explanation-only reply, citations as a string, citations as an empty list, citations referencing sentence numbers that do not exist. |
| AC2 | A reply that is not JSON at all, or has no explanation, stays `malformed` and is not repaired (a second call would just be a guess). Pinned. |
| AC3 | The repair round is measured honestly: re-run the ten real cases against `deepseek-flash`, and report accept rate **before and after** the repair, how many needed a repair, how many repairs succeeded, and the token cost of repairs (a repaired explanation costs two calls). State the accept rate as a range if the sample is too small to be a rate. |
| AC4 | The ledger distinguishes `fresh_repaired` from `fresh` so the A/B can price repairs separately. The report page shows it. |
| AC5 | No weakening: the four TESTOPS-88 lies still reject, uncited sentences still reject, agent=off pages byte-identical, suites and contracts green. |
