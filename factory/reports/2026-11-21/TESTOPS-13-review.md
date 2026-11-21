# TESTOPS-13 review — Python floor (reviewer, 2026-11-21)

## Verdict

**PASS.** The app imports and the suite is green on both interpreters, the guard is real and
defeats on both sides, rendering is byte-identical, and the two gaps I found (a 3.12-only runtime
API slips past the guard; one edited branch is unreachable code) are noted concerns, not
acceptance failures.

## Criteria

- **AC1 HOLDS.** I imported all 33 modules under `testops/` (scripts excluded, `__main__`
  excluded) with cpython-3.11.15 in isolated mode with the environment stripped: all imported
  without error. Before the fix, the same import dies with
  `SyntaxError: f-string expression part cannot include a backslash` (verified against a
  `git archive feature/f1` checkout).
- **AC2 HOLDS.** Both suites run by me, environment stripped as specified:
  3.12 venv (3.12.5): `118 passed in 8.72s`.
  3.11 (builder's scratch venv311, 3.11.15): `114 passed, 4 skipped in 9.34s`.
- **AC3 HOLDS.** The guard (`tests/test_python_floor.py`) compiles every module on 3.11 — where
  the interpreter is the authority — and on 3.12 tokenises f-strings and inspects expression
  tokens only (FSTRING_MIDDLE literals are skipped, so legal escapes in text are not flagged).
  The scan's own self-tests are the four skipped tests on 3.11, all in
  `tests/test_python_floor.py` at lines 171, 184, 192, 201, each skipping with
  "pre-3.12: compiling the source is the equivalent check" — genuine 3.12-only tokenizer tests,
  no product test hides among them. Caveats under "Defeating the guard".
- **AC4 HOLDS.** I started `app.serve(port=8812)` as a background process under the 3.11 venv
  (log: `TestOps UI on http://127.0.0.1:8812`) and fetched
  `/case/case-cotw-levels-20261121T215534-01` (HTTP 200, 5838 bytes). Rendered text (tags
  stripped, verbatim): "Never actually proved · 1. What is asserted ... 'each fact's citation is
  in an element reachable by an accessible name' ... 5. What could not be checked — Jira and
  Azure DevOps were never consulted ... 6. Proposed action and decision ... Decide this case — 1
  finding rides on this decision ... Debugging shorthand, not part of the finding: interaction
  I4; verdict gap." Note the standing rule is honoured on the page itself: Jira/ADO read as
  "cannot assess", never "nothing found".
- **AC5 HOLDS, with one observation.** `git diff feature/f1..HEAD` touches no existing test —
  only new `tests/test_python_floor.py`, `testops/web/app.py`, and my review prompt. I rendered
  case pages under both `git archive feature/f1` and HEAD against the same DB copies and compared
  bytes: 5 real cases (including the full 62,801-byte `case-cotw-levels-20261120T194425`) are
  byte-identical, plus a synthetic case with a suppression note and terminal state, which
  exercises the `decision_form` hunk and renders the note suffix identically (5,538/5,538 bytes).
  I could not exercise the second hunk ("Every finding in this case has been suppressed", in
  `case_page`): see concerns.
- **AC6 HOLDS.** `pyproject.toml` still declares `>=3.11` and the new
  `test_declared_floor_and_the_guard_agree` test asserts the guard and the declaration agree,
  so a silent floor change fails a test instead of passing quietly.

## Defeating the guard

Planted a scratch module whose f-string expression contains a backslash
(`f'{d["note"] + "\u2014" ...}'`). The 3.11 interpreter rejects it at compile with
`SyntaxError: f-string expression part cannot include a backslash`; the 3.12 tokenizer guard
reports `sneaky.py:2: "\u2014"`. Both sides of the guard fail on the construct. Feeding the
guard through the test module itself (`fstring_backslash_violations` imported from
`tests/test_python_floor.py`) gives the same result.

Then I tried what the guard is not built to see: `from itertools import batched` (3.12-only,
added in 3.12). It compiles cleanly on 3.11 — `compile()` passes — and fails only at runtime
with `ImportError: cannot import name 'batched' from 'itertools'`. Neither side of the guard
catches it: on 3.11 compiling is the whole test, and `batched` is a legal name everywhere it
looks. So AC3's promise is exactly as narrow as its wording: it protects *the construct that
broke the floor*, not the floor in general. A 3.12-only API, a 3.12-only stdlib module, or a
3.12-only syntax feature other than backslashes-in-expressions will pass the guard and break
the serving interpreter. AC1 is still met because the interpreter itself is exercised directly,
but the guard is a one-fence guard, and nothing prevents the next PEP 701-shaped breakage from
being a different shaped hole.

## Three sharpest concerns

1. **The guard protects one construct, not the floor.** `itertools.batched` (or `Path.walk`,
   or `tomllib`-neighbouring additions) compiles on 3.11 and dies at import-or-runtime. The
   suite would never notice unless something imports that module under 3.11. The only structural
   answer — running the whole suite under the floor interpreter on every run — is what the
   scratch 3.11 venv now makes possible, and it is not wired into any cron or CI today.
2. **`KNOWN_FLOOR_INTERPRETERS` hardcodes this machine's uv path.** On any other machine (CI, a
   colleague, the next laptop) the list is empty and the 3.11 compile test skips. The guard is
   machine-bound; its portability is an open ticket waiting to happen.
3. **The second edited hunk sits in a branch no store can reach.** "Every finding in this case
   has been suppressed" fires when `findings` is empty *and* the superseded query joins a
   finding of the case — but `queries.finding_rows` emits one entry per finding row, so the two
   conditions are contradictory with today's query. No existing test renders that text, and the
   live store has zero suppressions. The edit is provably inert (the expression is moved out
   unchanged), so AC5 is unaffected, but the branch is dead code carrying a TESTOPS-13-shaped
   comment, and the TESTOPS-6 review once quoted that text — the reachability of it changed
   somewhere along the way and nothing caught that either.

## Demo

- **The problem.** `pyproject.toml` said `>=3.11` while the tests ran on 3.12 and the UI was
  served by 3.11.15 — which could not even parse `testops/web/app.py`, so the UI never started.
  Three quiet failures hid one loud one.
- **What changed.** Two one-line moves in `testops/web/app.py` (the `— note` suffixes are now
  built into `note_suffix` before the f-string, in `decision_form` and `case_page`), plus a new
  `tests/test_python_floor.py` with a two-sided guard: interpreter-compile on 3.11,
  token-stream inspection on 3.12, self-tests so the scan cannot rot silently, and a floor-
  agreement check on `requires-python`.
- **How we know it works.** 33/33 modules import under 3.11.15; suites are 118 passed (3.12) and
  114 passed + 4 skipped (3.11), both run by me with the environment stripped. A 3.11-hosted
  server renders `case-cotw-levels-20261121T215534-01` (text quoted above). Pages are
  byte-identical before and after on five real cases plus a suppression-note case. Both sides of
  the guard fail on a planted backslash module.
- **What it does not solve.** 3.12-only runtime APIs still pass the guard and would break the
  serving interpreter; the guard's floor list is hardcoded to this machine; and nothing has
  wired the 3.11 suite into a cron or CI so the green-light continues by default.
- **Where to look.** `tests/test_python_floor.py` (guard + self-tests),
  `testops/web/app.py:371-376` and `:444-451` (the two hunks),
  `tests/test_python_floor.py:32-35` (hardcoded interpreter paths).
