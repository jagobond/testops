# TESTOPS-66 build - the guard attributes only what it can prove

Branch `factory/testops-66-guard-content`, worktree `C:/Users/<name>/Projects/testops-t66`.
The live store and port 8791 were never touched. Every probe ran in a disposable scratch repository.

## What changed

`tests/support.py`

- **Content agreement (AC1).** `repository_snapshot()` now records git's blob digest for each file
  (`git hash-object --stdin-paths`), which applies the repository's clean filters, including
  `core.autocrlf=true` on this checkout. A raw sha256 fallback is used only when git is unavailable.
  A commit excuses a path only when the working-tree digest equals the blob the new commit's tree
  holds for that path. A mismatch fails and names the path, the expected blob and the observed
  digest, saying "the working tree and the commit disagree".
- **The index is load-bearing (AC2).** A staged-but-uncommitted change is detected by comparing the
  baseline and comparison indexes: the index changed, the working tree matches the new index blob,
  and that blob differs from `HEAD`'s tree. It fails as its own class. The false docstring sentence
  claiming the index distinguishes trackedness is gone.
- **Git unavailability is its own class (AC3).** `RepoState` carries `readable`; `GitRepository.state()`
  sets it from `git rev-parse --is-inside-work-tree`. An unreadable repository reports "the
  repository could not be read, so nothing could be attributed", names git as the suspect, and still
  fails. It never claims the suite wrote.
- **Partition and counts (AC4).** `AttributionReport.summary()` prints every class with its count in
  one line; the classes are disjoint and the counts sum to the total difference.
- **Removals and additions.** A commit only explains a deletion when the path is absent from the new
  tree, and only explains an addition when the path is present and its bytes agree. A commit that
  merely modifies a path no longer launders a deletion; a commit that deletes a path no longer
  launders an addition.

`tests/conftest.py`, `tests/test_isolation.py` - docstrings now state the content-agreement rule, the
staged class and the unreadable class.

`tests/test_guard_attribution.py` - five pinned tests plus the partition test, all synthetic against
`attribute_differences`:

1. mid-run commit to a tracked file passes;
2. plain write fails;
3. untracked addition fails;
4. content mismatch fails for its own reason;
5. staged-uncommitted change fails for its own reason;
6. the partition test proves every difference is in exactly one class, for both the normal and
   git-unreadable states.

## Verification

Interpreter: `env -u PYTHONPATH -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1
C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe -m pytest -q`.

- Targeted guard tests: **12 passed**.
- Full suite: **938 passed, 2 skipped** (158s).
- Contract suite (`tests/contracts`): **37 passed, 2 skipped**.
- Real-git probes in disposable scratch repositories: matching mid-run commit passes; content
  mismatch fails with the expected/observed blobs; staged change fails as staged; git unavailable
  fails as unreadable without accusing the suite.
- `git status --short` shows only the four test files; no case-page golden changed.

## What the guard still cannot attribute

A test write whose bytes exactly equal the commit's blob is indistinguishable from the commit. A
write reverted to its exact baseline bytes is invisible to a digest. With no commit at all, every
difference remains unexplained. The module docstring states these limits.
