---
id: TESTOPS-13
title: The app cannot be imported by the interpreter that serves it
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-6
---

# TESTOPS-13 — Python floor

## Why

`pyproject.toml` declares `requires-python = ">=3.11"`. `testops/web/app.py` contains an f-string
whose expression includes a backslash escape:

```python
f'{esc(" \u2014 " + d["note"]) if d and d["note"] else ""}.</p>'
```

Backslashes inside f-string expressions are legal from Python 3.12 (PEP 701) and a `SyntaxError`
before it. The suite passes because it runs under the 3.12 venv; the interpreter that actually serves
the UI on this machine is 3.11.15, and it cannot import the module at all:

```
SyntaxError: f-string expression part cannot include a backslash
```

Three separate failures hid this: the tests run on a newer interpreter than the app is served with;
nothing imports the app under the floor version; and the declared floor is only a string in a TOML
file, so nothing checks it.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Every module under `testops/` imports successfully under Python 3.11. |
| AC2 | The full suite passes under **both** 3.11 and 3.12, with the counts recorded in the report. |
| AC3 | A test fails if any module reintroduces a backslash inside an f-string expression — the specific construct that broke the floor — so the regression cannot return silently on a 3.12-only run. |
| AC4 | The server starts under 3.11 and serves a real case page: the report quotes the rendered text of `case-cotw-levels-20261121T215534-01` fetched from a 3.11-hosted process. |
| AC5 | No behaviour changes: pages render identically before and after (same text content), and no test is weakened to accommodate the change. |
| AC6 | `requires-python` and the code agree. If you conclude 3.11 support is not wanted, changing the declared floor is a decision for the Lead, not something to do silently to make a test pass. |

## Verification

```
# both interpreters
env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
  .venv/Scripts/python.exe -m pytest -q
env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
  "C:/Users/Chester/AppData/Roaming/uv/python/cpython-3.11.15-windows-x86_64-none/python.exe" -m pytest -q
```

## Notes

- 3.11 is not academic: it is the interpreter that already has a Windows firewall allow rule on this
  machine, which is why it serves the UI over Tailscale. Dropping to 3.12 means an elevation prompt.
- The fix is likely one line — build the string before the f-string — but the *guard* is the point:
  the next such construct should fail a test, not a deployment.
- Do not add a pytest plugin to make the syntax legal; that is not a thing.
