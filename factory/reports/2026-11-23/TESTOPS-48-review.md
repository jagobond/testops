# TESTOPS-48 review — coverage decided by the built wheel

Reviewer run, 2026-11-23. All commands from worktree C:/Users/Chester/Projects/testops-t48, branch
factory/testops-48-wheel-coverage, interpreter
`env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 C:/Users/Chester/Projects/testops/.venv/Scripts/python.exe`.
No product code or ticket edited; tree clean at the end (`git status` empty, no `.whl` anywhere in
the checkout, no `data/` directory exists).

## Verdict

**Pass.** The hole is closed in both directions, not narrowed: an undeclared probe fails, and the
wrongly-declared probe — the exact case the old `PurePosixPath.match` rule let through — also
fails, naming the declaration that fooled the old matcher. The verdict is now the wheel's
namelist; the matcher survives only inside the error message. Two non-blocking weaknesses below
(vacuous-empty enumeration, suite timing variance on a cold disk).

## The hole, closed both ways

Baseline: full suite green before interference — 557 passed, 11 skipped in 145.91s.

Case (a) — `testops/web/templates/probe.html` created, no declaration:

    web/templates/probe.html: expected in wheel as testops/web/templates/probe.html; declared patterns matching this file: none
    1 failed, 3 passed in 8.43s

Case (b) — probe recreated and declared wrongly as `"templates/probe.html"` under `"testops"`
(no `web/` prefix — precisely the declaration the old matcher accepted while shipping nothing):

    web/templates/probe.html: expected in wheel as testops/web/templates/probe.html; declared patterns matching this file: ['templates/probe.html']
    all declared patterns: ['store/schema.sql', 'judgement/prompts/*.md', 'templates/probe.html']
    1 failed, 3 passed in 8.49s

The old rule would have passed this: `PurePosixPath('web/templates/probe.html').match('templates/probe.html')`
is True, and the build ships nothing. The wheel check fails on it. Probe deleted and pyproject
restored; `git diff pyproject.toml` empty afterwards.

## Not vacuous

The enumeration is real but thin: today it lists exactly two files —
`['judgement/prompts/level_fitness.md', 'store/schema.sql']`. Each is independently pinned by a
second test (schema.sql by name in the wheel-content test; the prompts glob by TESTOPS-8's own
checks), so the general rule is not the only line of defence — but the general rule itself
currently guards one file no other test names.

The empty case is a genuine (low-probability) hole. I simulated it by monkeypatching
`_data_files_on_disk` to return `[]` and calling the test with a real empty wheel: **the test
passes vacuously — zero files checked, zero assertions made.** Same if `PACKAGE` points at a
nonexistent directory: enumeration returns `[]`, verdict is a pass. A one-line guard
(`assert files != []`) would close it; not blocking today because the package directory is
created by every other test in the file passing first.

## Cost

`built_wheel` is `scope="session"` (tests/conftest.py:39). Running test_packaging.py and
test_distribution.py together under a controlled `--basetemp` produced exactly one build
directory (`testops-wheel0`) and one wheel, 7 tests in 18.75s — the packaging test added ~2s on
top of the distribution cost TESTOPS-8 already paid. No doubled build. Full suite 145.91s; the
AC4 budget from TESTOPS-8 ("under two minutes") binds the check, not the suite, and the check
is ~17s. Note the build report's 104.93s full-suite figure did not reproduce on my run (145.91s,
cold disk) — same counts, comfortably different wall clock; worth knowing before quoting the
report's number.

## No writes

The build copies the source to pytest's tmp and builds there; install goes to a fresh venv in the
same tmp tree. Verified: `git status --porcelain` empty after the full run and after every red
run and restore; no `data/` directory at the root and none created; no `.whl` in the checkout.
The session-scoped `repo_guard` in conftest would fail the run regardless of order if any test
wrote into the repo, and the store guard blocks writes to the live store.

## The message

    the built wheel is missing non-Python files that are in the package tree; package-data patterns are relative to the package root, and the wheel is the authority:
        web/templates/probe.html: expected in wheel as testops/web/templates/probe.html; declared patterns matching this file: ['templates/probe.html']
        all declared patterns: ['store/schema.sql', 'judgement/prompts/*.md', 'templates/probe.html']

As a reader who just broke the build: the first line tells me the class of mistake and where the
authority lives; the second line is the fix — it names the exact wheel path expected and shows
that my pattern `templates/probe.html` matched but shipped nothing, which points straight at
"add the `web/` prefix". The `all declared patterns` line is mild noise (readable in pyproject)
but cheap and useful when several patterns are declared. One small redundancy: the trailing
pytest diff (`Left contains one more item: ...`) repeats what the message already said better —
that is pytest's `-q` diff on the missing list, not the test's doing, and not worth fighting.

## Three sharpest concerns

1. **Vacuous on empty enumeration.** `_data_files_on_disk()` returning `[]` (missing package dir,
   wrong constant) makes the verdict a silent pass — verified by simulation. An `assert files`
   guard would make the test refuse to assert about nothing. Low likelihood, near-zero cost to
   fix.
2. **The general rule currently guards one file.** Of the two non-Python files enumerated, both
   already have a second line of defence (schema.sql by name; prompts via TESTOPS-8). The new
   test earns its keep the day a third file appears — until then it is mostly insurance, which
   is fine, but do not mistake it for active coverage today.
3. **Timing variance vs the build report.** 145.91s on my run vs the report's 104.93s for the
   identical suite and counts. The AC4 budget (two minutes) applies to the check, which is
   ~17s, so nothing is violated — but any future ticket that quotes full-suite wall clock from
   one run should say so, or budget against the slower figure.
