---
id: TESTOPS-25
title: The fixture is somebody else's MIT code, and we are not carrying its licence
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-21
---

# TESTOPS-25 — Attribution for the sample we measure against

## Finding

The reviewer of TESTOPS-21 established that `tests/fixtures/reqoverflow/` is **not** a synthetic corpus. It is a
verbatim subset of `reqnroll/Sample-ReqOverflow` (namespace `ReqOverflow.Specs.*`, the sample's own fictional
`Trillian` / `139139` credentials), read back from a stored snapshot of that repository at `78153818`.

Verified upstream: the sample is **MIT licensed, © 2013–2024 Reqnroll and Gaspar Nagy** (github.com/reqnroll/
Sample-ReqOverflow — README and `LICENSE`). MIT permits redistribution *provided the copyright notice and
permission notice are included*. The fixture directory carries neither, and the repository root has no licence
file at all.

## Why this is a ticket, not a note

This project's whole argument is that a claim must be traceable to the thing that settles it. Shipping copied
code with no attribution is the same defect in the repository that we cite test suites for: the evidence exists,
the provenance is missing, and a reader cannot tell what is ours.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | `tests/fixtures/reqoverflow/LICENSE` contains the upstream MIT notice verbatim, with the copyright line intact. |
| AC2 | `tests/fixtures/reqoverflow/PROVENANCE.md` names the upstream repository, the exact commit `78153818`, which projects were copied and which were left out, the date, and the fact that the files are unmodified except for whatever we did modify (list any modification honestly; if none, say none). |
| AC3 | The repository root gains a `THIRD-PARTY-NOTICES.md` listing the fixture, its licence and its copyright holder, so the obligation is visible without reading a test directory. |
| AC4 | `tests/reqoverflow_fixtures.py`'s docstring keeps its candid provenance sentence and points at `PROVENANCE.md`. |
| AC5 | The build does not add the upstream's own `.csproj` build targets in a way that changes our CI; the fixture remains data for the duplication analyser, and CI stays green. |
| AC6 | A test asserts both files exist and that `PROVENANCE.md` contains a commit hash of the expected form, so a future tidy-up cannot quietly delete the attribution. |

## Notes

- Do not relicense anything or touch upstream's copyright line.
- If any file was modified to make it parse, say what and why rather than tidying it into silence.
