# TESTOPS-48 build — the built wheel decides coverage

## What changed

- `tests/wheel_build.py` (new): shared plumbing and a session-scoped wheel builder. The source is
  copied to a temp directory; the wheel is built with `--no-build-isolation`; the install uses
  `--no-index`. No network.
- `tests/conftest.py`: `built_wheel` session fixture, so packaging and distribution checks share one
  build.
- `tests/test_distribution.py`: uses the shared wheel and only creates the venv/install. Plumbing
  moved to `wheel_build.py`.
- `tests/test_packaging.py`: the AC5 test now checks the wheel's `namelist` at
  `testops/<package-relative-path>`. `PurePosixPath.match` is retained only to suggest which glob
  to fix in the failure message, never for the verdict.
- `tests/README.md`: documents the shared wheel and the wheel-authority check.
- No product code touched. `pyproject.toml` is unchanged.

## AC1 — wheel is the authority

For every non-Python file under `testops/`, the test asserts that
`testops/<relative-path>` appears in the built wheel's `namelist`. A missing entry fails the test.
The matcher is no longer the authority.

## AC2 — proof it bites twice

Case (a): create `testops/web/templates/probe.html` with no declared pattern. Run the test:

```
E       AssertionError: the built wheel is missing non-Python files that are in the package tree; package-data patterns are relative to the package root, and the wheel is the authority:
E           web/templates/probe.html: expected in wheel as testops/web/templates/probe.html; declared patterns matching this file: none
E           all declared patterns: ['store/schema.sql', 'judgement/prompts/*.md']
E       assert [('web/templa...be.html', [])] == []
E         Left contains one more item: ('web/templates/probe.html', 'testops/web/templates/probe.html', [])
FAILED tests/test_packaging.py::test_package_data_ships_every_non_python_file_in_the_package
```

Probe deleted.

Case (b): recreate the probe and declare the pattern wrongly under `"testops"` — omit the
package-relative `web/` prefix, so the declaration is `"templates/probe.html"`:

```
E       AssertionError: the built wheel is missing non-Python files that are in the package tree; package-data patterns are relative to the package root, and the wheel is the authority:
E           web/templates/probe.html: expected in wheel as testops/web/templates/probe.html; declared patterns matching this file: ['templates/probe.html']
E           all declared patterns: ['store/schema.sql', 'judgement/prompts/*.md', 'templates/probe.html']
E       assert [('web/templa...probe.html'])] == []
E         Left contains one more item: ('web/templates/probe.html', 'testops/web/templates/probe.html', ['templates/probe.html'])
FAILED tests/test_packaging.py::test_package_data_ships_every_non_python_file_in_the_package
```

This is the case the old matcher let through. `PurePosixPath('web/templates/probe.html').match(
'templates/probe.html')` is `True`, so the old check would have passed while the wheel shipped
nothing. The wheel check fails. `pyproject.toml` restored and the probe deleted.

## AC3 — missing file reporting

The failure names the expected wheel path (`testops/web/templates/probe.html`) and the declared
patterns that match the file (`['templates/probe.html']`), plus the full declared list. The reader
is not left guessing which glob to fix.

## AC4 — one wheel per session, no network

`built_wheel` is session-scoped. `test_packaging.py` and `test_distribution.py` share one build. The
build runs `pip wheel --no-deps --no-build-isolation`; the install runs `pip install --no-index`.
Full suite: **104.93s**, inside the two-minute budget.

## AC5 — suite green, counts unchanged

```
557 passed, 11 skipped in 104.93s (0:01:44)
```

No product code touched. `git status` shows only `tests/` and `tests/README.md` changes.

## Verification command

```
env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
  C:/Users/Chester/Projects/testops/.venv/Scripts/python.exe -m pytest -q
```
