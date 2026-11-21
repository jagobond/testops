# TESTOPS-15 review — 2026-11-21

## Verdict — PASS

The workflow is real, green on the ticket branch at run 44961907849, and — proven by a deliberate
break — it goes red on the 3.11 leg and stays green on 3.12, which is the property the ticket
actually asked for.

## Criteria

- **AC1 — HOLDS.** `.github/workflows/ci.yml` triggers on push and pull_request for `main` and
  `feature/*`, with `matrix: python: ["3.11", "3.12"]` and `fail-fast: false`. Confirmed live: runs
  44961811226/44961907849 fired on the branch's pull_request event.
- **AC2 — HOLDS.** Both legs install `-e ".[dev]"` (pytest is the only dev extra, matching
  pyproject.toml) and run `env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX
  PYTHONNOUSERSITE=1 python -m pytest -q` — the exact command in tests/README.md, no `-k`, no
  deselect, no `continue-on-error` anywhere in the file.
- **AC3 — HOLDS.** The `render` job (needs the suite) imports `testops.web.app` on 3.11, seeds the
  store from `tests/test_case_page.py`'s own fixture, renders `app.case_page` from the store, then
  starts the real `app.ThreadingHTTPServer` with `app.Handler`, GETs the case URL, and fails unless
  the response is 200, an `<!doctype html>` document containing all six section headings and the
  assertion coordinates. This serves an actual page over HTTP; it is not a file-existence assert.
- **AC4 — HOLDS.** The failing leg is named in the check title itself (`suite (Python 3.11)`), in
  the step summary, and in `::error` annotations titled with the interpreter. Verified live on the
  probe run: annotations "suite (Python 3.11): ERROR tests/test_case_page.py" surfaced on the PR.
- **AC5 — HOLDS.** `concurrency` group keyed on the ref with `cancel-in-progress: true` cancels
  superseded runs; one run per push/PR. Cost honesty: the comment claims ~3 billed minutes; the
  real green run 44961907849 took 13s/14s/13s of job time, each rounding up to 1 billed minute
  per job, so 3 billed minutes is exactly right — the number is honest, if slightly conservative
  (caching will not drop it below the per-job rounding floor).
- **AC6 — HOLDS.** Diff vs feature/f1 touches only `.github/workflows/ci.yml`,
  `.github/ci/render_case_page.py` and the review prompt. No product code, no weakened tests.
  (The workflow comment says the same, and nothing was weakened to fit.)
- **AC7 — WEAK.** There is no builder report in `factory/reports/` for this ticket — the criterion
  says "the report includes the real run URL and the actual output of the first green run", and the
  ticket builder produced none. The evidence exists (runs above), but the deliverable as written
  is not on the board. Flagged, not blocking: the reviewer verification below supplies both URL and
  real output.

## Can it fail?

Yes. Branch `review/testops-15-fail-proof` (commit cb45655) added
`from itertools import batched` at import time in `testops/web/app.py` — the ticket's own example of
a 3.11-only runtime break that slips past the compile guard — and pushed as PR #11 against
`feature/f1`.

Run: https://github.com/jagobond/testops/actions/runs/44962212770

- **suite (Python 3.11): FAILURE** — pytest collection error: `ImportError: cannot import name
  'batched' from 'itertools'` while importing `tests/test_case_page.py`. Annotations named the
  interpreter and the failing files.
- **suite (Python 3.12): SUCCESS** — the same commit is green on the other leg.
- **render case page (Python 3.11): SKIPPED** — `needs: suite` short-circuits it. Correct, but note
  the render job can never be the leg that catches a break the suite already catches.

Probe branch and PR were deleted after the run; working tree verified clean at ed4f79a.

## Three sharpest concerns

1. **No builder report (AC7).** The board has no TESTOPS-15 report; the ticket's own deliverable is
   missing even though the build is good. The Lead should ask the builder to write it, or the
   factory rule should say which of builder/reviewer owns the report.
2. **`pull_request` runs on the PR merge ref, not the branch head.** Fine today, but the fail-proof
   proved the trigger list is branch-narrow: a push to a throwaway branch runs nothing until a PR
   exists. Reviewers probing CI must open a PR; the workflow comment does not mention this.
3. **Render job placement.** It is gated behind the suite and duplicates coverage that pytest
   already provides for import failures. Its unique value is exercising the HTTP handler path —
   worth keeping, but a future refactor (needs chaining, or running it in parallel) should not let
   the suite's green mask a handler-only break; consider making it independent.

## Demo

- **The problem.** The suite only ran on 3.11 when a person remembered to point pytest at a scratch
  venv — a property of the Lead's memory, not the repository. TESTOPS-13's guard covers one
  construct, not the interpreter floor.
- **What changed.** A CI workflow (`ci.yml`) running the full local suite command on 3.11 and 3.12
  in a fail-fast:false matrix, plus a 3.11 render job that imports the app, renders a real case
  page from the test suite's store fixture, and serves it over HTTP through `app.Handler`,
  failing on any non-200 or missing section. Concurrency cancels superseded runs.
- **How we know it works.** Green run on the ticket branch:
  https://github.com/jagobond/testops/actions/runs/44961907849 — jobs `suite (Python 3.11)` 13s,
  `suite (Python 3.12)` 14s, `render case page (Python 3.11)` 13s, all success. Red run on the
  probe branch: https://github.com/jagobond/testops/actions/runs/44962212770 — 3.11 failed on
  import-time `batched`, 3.12 green. Billed cost: 3 minutes per run (three jobs, each rounding up
  to one minute) — matches the stated claim.
- **What it does not solve.** No scheduled run on `main` history before merge beyond normal PR
  checks; the render job is skipped when the suite fails; and nothing yet runs the floor check
  against the exact interpreter version that will serve in production beyond a 3.11/3.12 pin
  (a `3.11.x` drift is still possible inside the major).
- **Where to look.** `.github/workflows/ci.yml` (trigger, matrix, concurrency, summary/annotation
  steps); `.github/ci/render_case_page.py` (import → render → serve-over-HTTP check);
  tests/README.md (the command CI reproduces).
