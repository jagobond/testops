---
id: TESTOPS-14
title: A level run cannot rebuild itself, and its claims carry no observations
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-13
---

# TESTOPS-14 — Evidence depth

## Why

Two related gaps, both found while building and reviewing the case page.

**1. The level snapshot records only the product arm.** The claim is that the store is the product's
memory and everything else is derived. A `levels` run writes artefacts for the product repository
only; the test repository's features and step definitions — the things every claim is *about* — are
never recorded. So the run cannot be rebuilt from its own snapshot, and TESTOPS-10's builder had to
read the test arm from a *different* snapshot and refuse to run if the commits disagreed.

**2. Claims carry no observations.** The case page's evidence section renders, honestly:

> "This run recorded no observations at these coordinates, so the source link above is the only
> evidence there is."

For every real specimen. The page was built to show what a claim rests on; the store holds nothing
to show, because the collector writes artefacts only for feature and step-definition files it parses
and records no observation rows for them.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A `levels` run records artefacts for **both** arms, so `run_id → snapshot → artefacts` is sufficient to rebuild the claim set without any other snapshot and without network access. |
| AC2 | A claim's coordinates resolve to an artefact in its own snapshot: `assertion_path` + `assertion_commit` find the feature file that was analysed. |
| AC3 | Each v2 claim carries the observations that back it — at minimum the matched step binding, so `support` is non-empty for a claim whose steps were bound, and empty (explicitly, not NULL) only when nothing bound. |
| AC4 | The case page's evidence section shows those observations with a one-line statement of what each shows, and no longer falls back to "no observations at these coordinates" for the specimen. |
| AC5 | A run is reproducible: given the snapshot id alone, a rebuild produces claims identical to the originals (AC8 of TESTOPS-4 still holds). |
| AC6 | Corpus numbers are unchanged by this ticket: 94 claims, 90 distinct, 1 unplaced, 1 gap, 2 review. Recording evidence must not change a verdict. |
| AC7 | Suite green; determinism preserved. |

## Notes

- This is the ticket that makes "the store is the product's memory" true rather than aspirational.
  Everything downstream — the coverage report, the Quilter story where Jira is absent — depends on a
  run being explainable from what it stored.
- Observation rows must not become a dumping ground: record what a claim rests on, keyed so the page
  can say what it shows. The existing `observation` table and `_shows` renderer are the seam.
- If recording the test arm explodes the store size, say so with numbers rather than trimming
  silently.
