# TESTOPS-49 build — an enumeration that refuses to pass on nothing

Builder run, 2026-11-23. Worktree `C:/Users/<name>/Projects/testops-t49`, branch
`factory/testops-49-not-vacuous`. Interpreter
`env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1 C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe`.
Test files changed only; no file under `testops/` was touched (`git status` names only `tests/`).

## Baseline and final

    before:  557 passed, 11 skipped in 108.87s
    after:   557 passed, 11 skipped in 103.70s

Same counts. The four edited files are `tests/test_packaging.py`, `tests/conftest.py`,
`tests/test_partial_reads_visible.py`, `tests/test_verdict_vocabulary.py`.

## AC1 — the walk is asserted before any verdict

`tests/test_packaging.py` now enumerates once into `files`, then calls
`_assert_enumeration_is_real(files)` **before** the wheel is opened and before any `missing` list is
built. The guard gives the directory it walked (`PACKAGE`) in every message, and the empty case says
the probe is broken — not that packaging is fine:

    assert files, (
        f"the package-data walk of {PACKAGE} found no non-Python files at all. That is a broken "
        "probe - a missing or wrong package directory - not a statement that packaging is "
        "complete, so no wheel-coverage verdict is drawn from it.")

`_data_files_on_disk` and the wheel-namelist verdict itself are unchanged; only what happens
before the verdict was added, and the loop now iterates the already-checked `files`.

## AC2 — proved red, then green

Three red runs, each with a pytest plugin that interferes before collection:

(a) `_data_files_on_disk` monkeypatched to `[]` — the reviewer's exact simulation:

    E  AssertionError: the package-data walk of C:\Users\<name>\Projects\testops-t49\testops found no non-Python files at all. That is a broken probe - a missing or wrong package directory - not a statement that packaging is complete, so no wheel-coverage verdict is drawn from it.
    E  assert []
    1 failed, 3 deselected in 5.69s

(b) `PACKAGE` pointed at `testops_does_not_exist`:

    E  AssertionError: the package-data walk of C:\Users\<name>\Projects\testops-t49\testops_does_not_exist found no non-Python files at all. ...
    1 failed, 3 deselected in 7.67s

(c) one of today's two files gone (`['store/schema.sql']` only):

    E  AssertionError: the walk of ...\testops found only 1 non-Python file(s) (['store/schema.sql']); the package ships at least 2, so files have gone missing from the tree, not from the wheel.
    E  assert 1 >= 2
    1 failed, 3 deselected in 8.20s

With the plugins removed, the same test is green inside the full run above.

## AC3 — a minimum count and the known names are pinned

    MIN_DATA_FILES = 2
    KNOWN_DATA_FILES = ("judgement/prompts/level_fitness.md", "store/schema.sql")

Both are floors, not equalities: a third non-Python file needs no edit, but losing or renaming one
fails. All three failure modes were exercised:

- third file added (guard fed the two real files plus `web/templates/probe.html`): the guard passed
  and the **wheel-namelist verdict** failed on the missing member — the authority is untouched:

        1 failed, 3 deselected in 5.84s
        Left contains one more item: ('web/templates/probe.html', 'testops/web/templates/probe.html', [])

- rename only (`LEVEL_FITNESS.md`, count still 2): fails on the name, not the count —

        FAILS AS INTENDED: the walk of ...\testops no longer finds ['judgement/prompts/level_fitness.md'], which the package ships today. It found ['judgement/prompts/LEVEL_FITNESS.md', 'store/schema.sql'].

## AC4 — every other tree walk in the suite

Searched `tests/` for `rglob`, `.glob(`, `iterdir`, `listdir`, `scandir`, `os.walk` and
`namelist`. Ten sites; four needed work.

Guarded in this ticket:

1. `tests/test_packaging.py::_data_files_on_disk` — the ticket itself.
2. `tests/test_partial_reads_visible.py::test_no_page_module_builds_the_assessment_sentence`
   walked `testops/web/*.py` and asserted two strings absent from each. An empty or moved `web/`
   meant zero modules checked and a pass. Now `assert modules` naming `web`, before the loop.
3. `tests/conftest.py::repo_guard` (via `support.repository_snapshot`, `os.walk`) — an empty
   snapshot compares nothing with nothing and the write guard passes. Now `assert before`,
   naming `ROOT`, before yielding.
4. `tests/test_verdict_vocabulary.py::test_the_analysers_emit_a_vocabulary_at_all` — already
   refused an empty scan (that test exists precisely for this), but its message did not say what
   was walked. Message now names `ANALYSERS` and says the comparisons would be vacuous.

Examined and already sound, no change:

5. `tests/test_python_floor.py::_modules` — already `assert files, f"no modules found under
   {PACKAGE}; the guard would pass vacuously"`.
6. `tests/test_retention.py::_blob_stats` — enumerates a blob directory the test populated
   itself and asserts `after_first["count"] > 0` before comparing snapshots.
7. `tests/wheel_build.py::build_wheel` — `assert len(built) == 1`, not a bare loop.
8. `tests/test_distribution.py` namelist use — a named-member membership check
   (`"testops/store/schema.sql" in names`), not a walk whose emptiness could hide a verdict.
9. `tests/test_third_party_attribution.py` — `rglob("*.csproj") == []` is a claim *about*
   emptiness (no build targets in the fixture), and the same test pins `len(texts) == 108`, so a
   vanished fixture cannot pass.
10. `tests/reqoverflow_fixtures.py::texts` — a corpus builder, not a verdict; its count is pinned
    at 108 by its consumers.

## AC5

Suite green, 557 passed / 11 skipped both sides of the change, repository clean apart from the
four test files, no product code, no ticket or existing report edited, no wheel or `data/`
directory left behind.
