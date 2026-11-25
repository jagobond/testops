# TESTOPS-49 review — the enumeration refuses to pass on nothing

Reviewer run, 2026-11-23. Worktree `C:/Users/<name>/Projects/testops-t49`, branch
`factory/testops-49-not-vacuous`, interpreter
`env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1 C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe`.
Full suite first: **557 passed, 11 skipped in 104.69s** — same counts as the build's before/after.
No product code, ticket, or pyproject left modified at the end (verified after every attack).

## Verdict

**Pass.** The vacuous pass TESTOPS-48's review found is closed, and closed without weakening
anything: the enumeration is asserted (non-empty, minimum count, known names) before the wheel
verdict is drawn, the wheel-namelist verdict itself is untouched and still fires when the wheel
is broken independently of the walk. AC3 holds in both directions. AC4 was done correctly — the
two extra files are the same rule, applied as additions only.

## The three attacks

All three were re-run by me (not taken from the build report). Each ran
`tests/test_packaging.py -k package_data_ships` with a pytest plugin that interferes before the
test body; each restored the tree afterwards.

1. **Monkeypatch `_data_files_on_disk` to `[]`** (the TESTOPS-48 reviewer's exact attack, which
   previously passed):
       E  AssertionError: the package-data walk of C:\Users\<name>\Projects\testops-t49\testops found no non-Python files at all. That is a broken probe - a missing or wrong package directory - not a statement that packaging is complete, so no wheel-coverage verdict is drawn from it.
       E  assert []
       1 failed, 3 deselected in 8.19s
   **Fails.** Message says the probe is broken, not that packaging is fine.
2. **`PACKAGE` pointed at a directory that does not exist** (`testops_does_not_exist`):
       E  AssertionError: the package-data walk of ...\testops_does_not_exist found no non-Python files at all. ...
       1 failed, 3 deselected in 8.13s
   **Fails.**
3. **`PACKAGE` pointed at a directory that exists but holds only Python files**
   (`testops/surfaces` — `discover.py` only):
       E  AssertionError: the package-data walk of ...\testops\surfaces found no non-Python files at all. ...
       1 failed, 3 deselected in 5.98s
   **Fails.** (A dir with exactly one data file, `testops/store`, fails on the min-count line
   instead: `found only 1 non-Python file(s) (['schema.sql'])`.)

## AC3 both ways

- **Delete** `judgement/prompts/level_fitness.md` (copied aside first): the test fails on the
  minimum count —
      E  AssertionError: the walk of ...\testops found only 1 non-Python file(s) (['store/schema.sql']); the package ships at least 2, ...
  Restored; `git status -- testops/` empty after restore.
- **Add** a third fake non-Python file (`testops/web/templates/probe.html`): the enumeration
  guard passed **without any edit** — `MIN_DATA_FILES = 2` and `KNOWN_DATA_FILES` are floors and
  a name list, not an equality — and the test then failed on the **wheel-namelist verdict**
  (`web/templates/probe.html: expected in wheel as testops/web/templates/probe.html; declared
  patterns matching this file: none`). That is correct, not a violation of AC3: the guard's job
  is to not stand in the way of new files, and the wheel verdict's job is to demand the new file
  be declared. The build report discloses exactly this. File removed; tree clean.
  (AC3 also has a third leg the ticket implies and I verified indirectly: a rename that keeps the
  count at 2 is caught by `KNOWN_DATA_FILES` — the build demonstrated it with `LEVEL_FITNESS.md`,
  and the name check is a straightforward `in` test on the same list I exercised above.)

## Verdict not weakened

I narrowed the package-data declaration in `pyproject.toml`
(`"store/schema.sql"` → `"store/other.sql"`) so the built wheel genuinely loses `schema.sql`.
The wheel-coverage failure still fired, from the wheel, not from the walk:

    E  AssertionError: the built wheel is missing non-Python files that are in the package tree; ...
        store/schema.sql: expected in wheel as testops/store/schema.sql; declared patterns matching this file: none

`1 failed, 3 deselected in 6.03s`. The new guard sat in front and did not short-circuit it — the
walk found both real files, passed the guard, and the wheel verdict caught the missing member.
`pyproject.toml` restored byte-identical afterwards (`git diff --stat` empty).

## The two extra files

AC4 sent the build looking for every other tree walk in the suite that proves something about
its subject. It found two it judged to need work and touched three files total besides
`test_packaging.py`.

1. **`tests/test_partial_reads_visible.py::test_no_page_module_builds_the_assessment_sentence`**
   walked `testops/web/*.py` with a bare `for` loop; a moved or emptied `web/` would check zero
   modules and pass. Now it materialises `modules = sorted(web.glob("*.py"))` and
   `assert modules` naming `web` before the loop. **Correct application of the rule** — same
   shape as AC1, message names the directory, nothing removed.
2. **`tests/conftest.py::repo_guard`** (via `support.repository_snapshot`, an `os.walk`) took a
   before-snapshot and compared it with an after-snapshot; an empty before-snapshot would compare
   nothing with nothing and pass. Now `assert before, f"the repository walk of {ROOT} found no
   files at all; ..."`. **Correct application.** Note this guard is session-scoped, so every
   full-suite run I did also exercised it — it never fired spuriously on this tree.
3. **`tests/test_verdict_vocabulary.py::test_the_analysers_emit_a_vocabulary_at_all`** already
   asserted `emitted` non-empty (the test exists precisely for this); the build only improved the
   message to name `ANALYSERS` and say the comparisons would be vacuous. **No weakening** — the
   assert is byte-for-byte as strict as before.

**Not scope creep.** Each edit adds an assertion or sharpens a message; none removes or loosens
one. AC4 asked for exactly this sweep ("wherever else the suite enumerates a tree to prove
something about it"), and the build's ten-site audit (four changed, six examined and left alone
with reasons) checks out against the diff: the six untouched sites either already assert
non-emptiness (`test_python_floor.py::_modules`), enumerate a fixture the test itself populated
and re-asserts (`test_retention.py`), or make a claim *about* emptiness that is pinned elsewhere
(`test_third_party_attribution.py`'s `len(texts) == 108`).

## Hygiene

- `git diff --stat origin/main...HEAD -- testops/` — **empty**. No product code touched.
- Suite count unchanged: 557 passed, 11 skipped, identical on my full run to the build's before
  and after figures. Duration 104.69s, consistent with the build's 103.70s (the TESTOPS-48
  review's 145.91s cold-disk outlier did not recur).
- After every attack (file delete, file add, pyproject narrow, PACKAGE monkeypatch) the tree was
  restored and `git status --porcelain` was empty at the end. No wheel or `data/` directory left
  in the checkout.
- The full diff is `tests/test_packaging.py`, `tests/conftest.py`,
  `tests/test_partial_reads_visible.py`, `tests/test_verdict_vocabulary.py` plus factory
  artefacts. Matches the build report exactly.

## Three sharpest concerns

1. **`KNOWN_DATA_FILES` can drift silently in one direction.** Adding a shipped data file needs
   no edit (by design), so the list will lag reality: the day a third data file ships, deleting
   it is not caught by name (only by the count, which won't know it was 3). That is the price of
   "floors, not equalities" and is acceptable — the wheel verdict catches an undeclared file
   going missing only if it was declared; a tree-side deletion of a wheel-shipped file is caught
   by the wheel check comparing against the (still complete) walk — but nobody is under
   obligation to update the list. A note in the file already says renaming/deleting "needs a
   deliberate edit"; consider requiring the walk count be commented at bump time too. Cosmetic.
2. **The `assert before` in `repo_guard` is a global tripwire with an environmental failure mode.**
   If a future change to `support.repository_snapshot`'s ignore rules (or an exotic checkout with
   few tracked files) legitimately empties the snapshot, every test in the suite fails with a
   guard message rather than a clear cause. Low likelihood on this tree (the snapshot is
   non-trivial and includes tests/), but it is the only new assertion that can fail without any
   test having done anything wrong. Worth remembering if a mysterious session-wide failure ever
   points at conftest.
3. **Attack (b) depends on `PACKAGE` being module-level state.** The min-count/known-names guard
   reads the real `testops/` tree through the module constant; my attacks (b)/(b2) patched
   `tp.PACKAGE`, which works because the constant is read inside the function. That is fine
   today, but if `_data_files_on_disk` is ever changed to capture the path at import time, the
   "wrong PACKAGE" failure mode could become unprovable by simulation. Not a defect in this
   change — an observation about which structure made it testable.

Both non-blocking. Recommend merge.
