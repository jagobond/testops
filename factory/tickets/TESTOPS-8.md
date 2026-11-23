---
id: TESTOPS-8
title: Packaging proof - install into a fresh venv and import through the distribution
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-2
---

# TESTOPS-8 — The packaging test tests the source tree, not the package

## Finding (reviewer concern 3 on TESTOPS-2)

`tests/test_packaging.py` imports the app through `sys.path`, so it exercises the checkout rather than an installed
distribution. If `package-data` omitted the templates, static files or `schema.sql`, the test would stay green while an
installed copy served 500s on every page. Harry plans to clone this repo at work and run it somewhere other than this
laptop, so this is the difference between "works here" and "works when someone installs it".

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A test builds a wheel (`python -m build --wheel` or `pip wheel`), installs it into a freshly created venv, and imports/runs **only** through that venv's site-packages - no repo on `sys.path`, no editable install. |
| AC2 | The installed copy serves `/`, `/runs`, `/config` and one case page with HTTP 200 from a store created by the installed package, proving template and schema files shipped. |
| AC3 | Prove the test can fail: remove one file from the wheel's `package-data` (or build with a deliberately narrowed `include`), watch the test go red, then restore. Report the red output. |
| AC4 | The check is in the ordinary suite and does not need network access; it must finish in under two minutes, or be marked so it can be skipped in the fast lane and still run in CI. |
| AC5 | `pyproject.toml` lists every non-Python file the app needs at runtime, and a test asserts the list matches what the app actually resolves at startup (templates dir, static dir, `schema.sql`), so a new template directory cannot be forgotten. |

## Notes

- Do not restructure the project. This is proof, not refactoring.
- If building a wheel in-test proves too slow or brittle on Windows, install from a copied source tree with
  `pip install .` into the temp venv - that is still the distribution path, not `sys.path`.
