---
id: TESTOPS-24
title: Retention — keep every run explainable without keeping every byte four times
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-22
---

# TESTOPS-24 — Retention

## Decision (Product Owner, 22 Nov 2026)

Deduplicate artefacts by content hash: keep full rebuildability, bound growth. Harry took the Lead's
recommendation explicitly.

## What the store actually does today (measured, not assumed)

| measure | value |
|---|---|
| database | 3.4 MB, 841 pages × 4096 |
| blobs on disk | 2.2 MB, 440 files |
| artefact rows | 1132 |
| **distinct blob shas** | **269** |

Blobs are already content-addressed (`testops/blobs.py` dedupes on sha256), so re-recording an unchanged test
arm does **not** duplicate file content — 1132 rows share 269 blobs. Growth per run is *rows*: artefact rows,
observation rows, claim rows. The "~250 KB per run" figure in the TESTOPS-14 report was an estimate of snapshot
size, not measured store growth; this ticket replaces it with measurements.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A test proves dedupe: two runs over an unchanged commit add zero new blob files, and the blob directory's byte total is identical after the second run. |
| AC2 | The report states measured growth per run in bytes and rows, for a levels run and a duplication run, from before/after measurements of a real store — not an estimate. |
| AC3 | A `retention` command reports, per snapshot: age, rows, bytes, and whether any case referencing it has a decision (`case_state` present) or a suppression. |
| AC4 | `retention --prune --keep N` deletes only snapshots that (a) are older than the N most recent, (b) are referenced by no case with a decision or suppression, and (c) are not the snapshot of the newest run per analyser. It prints what it would delete and refuses without `--yes`. |
| AC5 | Pruning a snapshot leaves every surviving case page rendering exactly as before; a test prunes the oldest levels snapshot and renders three cases from the survivors. |
| AC6 | Pruning never deletes blobs still referenced by a surviving artefact row; a test proves a shared blob survives. |
| AC7 | The default is report-only. No scheduled pruning, no silent deletion. |
| AC8 | Suite green on both interpreters. |

## Notes

- Never delete evidence a decision was taken on: the case says "resolved because <note>", and that claim must
  remain explainable afterwards. That is the line (a) and (b) draw.
- Blob dedupe is older than this ticket; the point is to prove it stays true and to make growth a number rather
  than a worry.
