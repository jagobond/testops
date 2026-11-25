# TESTOPS-8 build — packaging proof

Branch `factory/testops-8-packaging`, worktree `C:/Users/<name>/Projects/testops-t8`. Product code
untouched: the change is a test, a marker, one dev dependency and the `package-data` comment.

## What was wrong

`tests/test_packaging.py` imported `testops` through `sys.path`, so it proved the checkout was
complete. A wheel is not a checkout: `package-data` was `["store/schema.sql",
"judgement/prompts/*.md"]` and nothing ever checked that a *built* artefact carried them. Remove
`schema.sql` from the wheel and the old suite stayed green while every page of an installed copy
answered 500 — which is what Harry would have found on his work machine.

## What was built

1. `tests/test_distribution.py` (new, marked `distribution`). A module-scoped fixture copies
   `pyproject.toml` and `testops/` to a tmp dir, builds `testops-0.1.0-py3-none-any.whl` with
   `pip wheel --no-deps --no-build-isolation`, creates a fresh venv (`python -m venv`), and installs
   the wheel with `pip install --no-index` — so no network is touched at any point. Three tests:
   - the wheel's namelist contains `testops/store/schema.sql`;
   - a child interpreter run with `-I` (no repo on `sys.path`, no user site) reports
     `testops.__file__` inside the fresh venv's `site-packages`, and no entry of its `sys.path`
     starts with the checkout;
   - the installed copy, from `-I`, seeds a store through the installed package
     (`db.connect()` with `TESTOPS_DATA` pointed at a temp dir) and serves `/`, `/runs`, `/config`
     and `/case/case-dist` over a real `ThreadingHTTPServer` on port 0: all four answer 200 with a
     non-trivial body, and the store file the installed package created exists.
2. `tests/test_packaging.py` — AC5. `test_package_data_lists_every_file_the_app_resolves_at_startup`
   resolves `testops.store.db.SCHEMA` (the file startup actually opens) and requires the declared
   patterns to cover it, then requires them to cover **every** non-Python file under `testops/`.
   There are no `templates/` or `static/` directories in this app (the HTML is built in
   `testops/web/app.py`), so the general rule is the future-proof form of the ticket's named cases:
   the day someone adds `testops/web/templates/*.html`, a missing declaration fails a test.
3. `pyproject.toml`: dev extras now `["pytest>=8", "setuptools>=68", "wheel"]` (the backend used
   with `--no-build-isolation`), the `markers` entry for `distribution`, and a comment on
   `package-data` saying what each pattern is for. `tests/README.md` documents the fast lane.

## Verification

Full suite, project `.venv`, `PYTHONPATH`/`PYTHONHOME`/`VIRTUAL_ENV`/`CONDA_PREFIX` stripped,
`PYTHONNOUSERSITE=1`:

    557 passed, 11 skipped in 107.66s

Fast lane `-m "not distribution"`: `554 passed, 11 skipped, 3 deselected in 90.28s`. The three
distribution tests alone: `7 passed in 18.74s` (the two packaging tests included), inside AC4's two
minutes.

Environment note: this venv had only `pip`, so `setuptools` 84.2.1 and `wheel` 0.48.0 were installed
into it to match the new dev extras. Without them the fixture fails in one line saying
`pip install -e ".[dev]"`, not with a pip traceback.

## AC3 — the red run

`package-data` narrowed to `"testops" = ["judgement/prompts/*.md"]`, then the same two files run:

    ...FF.F                                                                  [100%]
    __________________________________ FAILURES __________________________________
    _______ test_package_data_lists_every_file_the_app_resolves_at_startup _______
    E       AssertionError: store/schema.sql is read at startup but package-data does not ship it: ['judgement/prompts/*.md']
    E       assert False
    E        +  where False = _covered('store/schema.sql', ['judgement/prompts/*.md'])
    tests\test_packaging.py:107: AssertionError

    __________ test_the_wheel_carries_the_file_the_app_reads_at_startup ___________
    E       AssertionError: schema.sql is read at startup but is not in the wheel:
    ['testops-0.1.0.dist-info/METADATA', ... 'testops/judgement/prompts/level_fitness.md']
    E       assert 'testops/store/schema.sql' in {'testops-0.1.0.dist-info/METADATA', ...}
    tests\test_distribution.py:102: AssertionError

    ________ test_the_installed_copy_serves_every_page_from_its_own_store _________
    E       FileNotFoundError: [Errno 2] No such file or directory:
    'C:\\...\\testops-distribution0\\venv\\Lib\\site-packages\\testops\\store\\schema.sql'
    tests\test_distribution.py:52: AssertionError
    =========================== short test summary info ===========================
    FAILED tests/test_packaging.py::test_package_data_lists_every_file_the_app_resolves_at_startup
    FAILED tests/test_distribution.py::test_the_wheel_carries_the_file_the_app_reads_at_startup
    FAILED tests/test_distribution.py::test_the_installed_copy_serves_every_page_from_its_own_store
    3 failed, 4 passed in 17.42s

Three failures for one omission, and the fourth test — the import-origin check — still passed,
which is the point: the check is specific, not a blanket "distribution is broken". The
`FileNotFoundError` on `site-packages\testops\store\schema.sql` is exactly the crash an installed
copy would have hit, caught here instead of at work. `pyproject.toml` was restored immediately and
re-verified: `grep schema.sql` present, full suite green as reported above.

## What this does not prove

The wheel is built on this machine by this interpreter's backend; a build on a different OS or a
different setuptools could still produce a different artefact. And the check covers the store, the
four pages and the import origin — not that `python -m testops.cli` works from an install (the CLI
reads no package data, so it would fail only on imports, which the import test already covers).
