# TESTOPS-8 review — packaging proof

Reviewer run, 2026-11-23. All commands from worktree C:/Users/<name>/Projects/testops-t8,
branch factory/testops-8-packaging, interpreter
`env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe`.
No product code or ticket edited; working tree confirmed clean afterwards (`git status` empty).

## Verdict

**Pass.** The replacement is not the old false confidence in new clothes: the red runs are real,
the installed copy is genuinely the installed copy, AC5's general rule bites on a probe file, and
CI runs the marked tests. Full suite green before interference: 557 passed, 11 skipped in 151.53s.
One real (non-blocking) weakness in AC5's matcher is listed under concerns.

## Red runs (both)

**Red 1 — package-data narrowed to `["judgement/prompts/*.md"]`**, then
`pytest tests/test_packaging.py tests/test_distribution.py`:

    3 failed, 4 passed in 17.42s
    FAILED tests/test_packaging.py::test_package_data_lists_every_file_the_app_resolves_at_startup
    FAILED tests/test_distribution.py::test_the_wheel_carries_the_file_the_app_reads_at_startup
    FAILED tests/test_distribution.py::test_the_installed_copy_serves_every_page_from_its_own_store

The serve test failed with the honest crash, not an assertion:
`FileNotFoundError: ...venv\Lib\site-packages\testops\store\schema.sql` raised inside the installed
package's `db.connect()`. Matches the build report exactly. Restored, re-ran green.

**Red 2 — the break the build did not try: `testops/store/schema.sql` deleted from the source
tree** (copied aside first). `pytest tests/test_distribution.py`:

    2 failed, 1 passed in 18.23s
    FAILED test_the_wheel_carries_the_file_the_app_reads_at_startup
    FAILED test_the_installed_copy_serves_every_page_from_its_own_store

Same `FileNotFoundError` from the installed copy's `db.connect()` — the app does not silently start
without a schema; it dies at startup, and the test dies with it. Restored from the copy; `git status`
clean; full-suite green state previously confirmed.

## Installed means installed

I ran the build/install/child-interpreter sequence myself, outside the test fixture, from a copied
tree in the scratch dir. Wheel built with `pip wheel --no-deps --no-build-isolation`, installed with
`pip install --no-index` into a fresh `python -m venv`, then:

    venv/Scripts/python.exe -I -c "import sys, testops; ..."

    FILE: ...\rev-probe\venv\Lib\site-packages\testops\__init__.py
    PATH: C:\Python312\python312.zip
    PATH: C:\Python312\DLLs
    PATH: C:\Python312\Lib
    PATH: C:\Python312
    PATH: ...\rev-probe\venv
    PATH: ...\rev-probe\venv\Lib\site-packages

`testops.__file__` is inside the fresh venv's site-packages and no `sys.path` entry starts with the
checkout (or with anything repo-shaped). The test could not pass while importing the repo: even
without `-I`, the child's cwd is the tmp work dir and `_env()` strips PYTHONPATH/PYTHONHOME/
VIRTUAL_ENV/CONDA_PREFIX, so there is no route back to the checkout. The serve test additionally
asserts `site-packages` in the reported `testops.__file__` from inside the serving process.

## Network

No PyPI contact is possible, and I proved it rather than trusting the flags:

- the fixture's build command carries `--no-deps --no-build-isolation` (tests/test_distribution.py:69) and its install carries `--no-index --disable-pip-version-check` (tests/test_distribution.py:81);
- I re-ran the three distribution tests with `PIP_INDEX_URL=http://127.0.0.1:9/ PIP_RETRIES=0 PIP_TIMEOUT=1` — a poisoned index that would fail instantly on any network attempt: **3 passed in 18.27s**. Nothing reached an index.

## AC5 bites

Created `testops/web/templates/probe.html`, ran the AC5 test:

    Left contains one more item: 'web/templates/probe.html'
    1 failed in 0.59s

A new template directory is a failing test, not a forgotten 500. Probe deleted; `templates/`
directory removed; tree clean.

## CI

`.github/workflows/ci.yml` runs `python -m pytest -q` (line 59) with **no** `-m` filter on both
matrix legs (3.11, 3.12), after `pip install -e ".[dev]"` — so the marked distribution tests DO run
in CI, on two interpreters, and the dev extras put the build backend in place. The fast-lane
deselection (`-m "not distribution"`, documented in tests/README.md) is local convention only.
One wrinkle: CI installs *editable*, so CI proves the suite passes against the checkout plus a
fixture-built wheel, not a deployed wheel — acceptable, since the wheel path is exercised inside
the tests themselves.

## Hygiene

- `git status` clean at start and after every red run, probe and restore; nothing written into the
  repo. No `data/` directory exists at the root and none was created; the distribution test points
  `TESTOPS_DATA` at tmp, and `test_isolation.py` (pre-existing, AC10) guards repo/data writes.
- No `.whl` anywhere in the worktree (builds go to pytest's tmp_path; my manual probe also built
  outside the tree and was deleted).
- The 11 skips are pre-existing: they come from `test_python_floor.py` (no 3.11 interpreter,
  pre-3.12 equivalents) and the `skipif(not STORED.exists())` corpus tests, none of which this
  ticket touched. The two files it changed contain no skip logic. Fast lane: 557 - 3 = 554 + 11
  skipped matches the build report's arithmetic.

## Three sharpest concerns

1. **AC5's matcher is looser than the build.** `_covered` uses `PurePosixPath.match`, which
   right-anchors: `web/templates/probe.html` is "covered" by the pattern `templates/probe.html`,
   but a pattern declared as `templates/probe.html` under `"testops"` would NOT ship the file
   (package-data patterns are relative to the package root). A future file could satisfy the
   coverage test with a pattern that never reaches the wheel. Only `store/schema.sql` has the
   second line of defence (the wheel-content test). Suggested tightening: require the pattern to
   match from the left (prefix semantics), or assert every non-Python file is in a fixture-built
   wheel's namelist.
2. **Single-interpreter wheel.** The wheel is built with `--no-build-isolation` by whatever
   setuptools/wheel the host venv holds; a different backend version could produce a different
   artefact than the one tested. The build report says as much. Low risk for a pure-Python wheel,
   but CI's matrix runs the check on 3.11/3.12, which blunts it.
3. **`-I` does part of the work.** The provenance assertions are as strong as the `-I` flag the
   test itself chose — they prove `-I` behaves, plus that `_env()` strips the inherited paths. If
   a later refactor dropped `-I` while keeping the assertions, the tests would still likely pass
   (cwd is tmp, PYTHONPATH stripped), but the checkout-on-sys.path guard would no longer be
   independently exercised. Cheap hardening: run one child without `-I` and assert the same origin.
