# TESTOPS-64 build - the tripwire learns to tell a commit from a write

Ticket: `factory/tickets/TESTOPS-64.md`. Branch: `factory/testops-64-tripwire`. Only `tests/` was
changed: no product code, no golden, no data. The live store and port 8791 were never contacted; the
guard tests drive synthetic snapshots and a real temporary git repository under the scratch directory.

## What the guard records now

`tests/support.py` gains a baseline that is more than a digest:

- `repository_snapshot()` - unchanged, the sha256/size digest of every file that is not an interpreter
  cache.
- `GitRepository.state()` - `HEAD` and the index (`git ls-files -s`), as `RepoState(head, index)`.
- `GitRepository.commit_blobs(commit)` - that commit's path-to-blob-sha tree (`git ls-tree -r
  --full-tree`), read once per commit and cached.
- `guard_baseline()` / `guard_report()` - the fixture's before and after calls; `guard_report`
  recomputes the digest and the state and hands both to one comparison.

`attribute_differences(before, after, before_state, after_state, commit_blobs)` is the comparison and
is pure: it takes the two snapshots and a callback that answers "what blobs does this commit's tree
hold". No test needs to commit, so AC5's three cases are synthetic.

## The rule

A difference is explained only when `HEAD` moved **and** the path's blob differs between the baseline
commit and the commit at comparison. Then:

| difference | explained | not explained |
|---|---|---|
| modified | reported "changed by a commit during the run", no failure | fails, path named, "no commit accounts for" |
| added | reported (new commit's tree holds it) | fails as an untracked addition - AC3 |
| removed | reported "deleted by a commit during the run", no failure | fails, path named |

An addition is never excused merely because `HEAD` moved: the new commit's tree must actually contain
it. Nothing is explained when either side has no commit, when `HEAD` did not move, or when git cannot
be read - every difference then fails, which is the loud direction.

## AC1-AC4

- **AC1** - baseline records `HEAD` and the index; a tracked path whose blob differs between the two
  commits is reported as *changed by a commit during the run* and does not fail.
- **AC2** - an unexplained change still fails, naming the path: "the suite wrote outside tmp_path: no
  commit made during the run accounts for data/store.db" plus `HEAD old -> new`.
- **AC3** - untracked additions fail even when `HEAD` moved; a committed deletion is reported under
  its own class and does not fail.
- **AC4** - `AttributionReport.summary()` prints one line per class with counts, always, on pass as
  well as failure: `write guard: 2 files changed by a commit during the run, 0 files unexplained`,
  then a line for deletions and for untracked additions when either is non-zero. `conftest.repo_guard`
  and `tests/test_isolation.py` print it and fail with `failure_message()`.

## AC5 - the three pinned cases, and the rest

`tests/test_guard_attribution.py` (9 tests, no commits and no writes outside the tree):

1. `test_a_commit_during_the_run_explains_a_tracked_change` - mid-run commit to a tracked file
   (`factory/tickets/TESTOPS-64.md`, the ticket that started this): nothing fails,
   `changed_by_commit` records it, summary line reads "1 file changed by a commit ... 0 files
   unexplained".
2. `test_a_write_to_data_with_no_commit_still_fails` - `data/testops.db` changes, the run's commit
   touches another file: fails, message names the path and says no commit accounts for it.
3. `test_an_untracked_file_is_never_excused_by_a_commit` - `data/leaked.db` new while `HEAD` moved:
   fails as an untracked addition.

Plus a committed deletion (reported, not failed), the AC4 counts line, a no-commit checkout
(nothing excused), an unmoved `HEAD` (nothing excused), and the baseline recording `HEAD` and the
index.

The same code was exercised against a real temporary git repository: commit-explained change passes;
an untracked write to `data/` fails; a committed deletion is reported.

## AC6 - verification

Interpreter:
`env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1
C:/Users/Chester/Projects/testops/.venv/Scripts/python.exe -m pytest -q`

- Full suite: **886 passed, 2 skipped** (154s).
- Contract suite (`tests/contracts`): **37 passed, 2 skipped**.
- Case-page goldens untouched; `git status --short` shows only `tests/conftest.py`,
  `tests/support.py`, `tests/test_isolation.py` and new `tests/test_guard_attribution.py`.
- The module docstring of `tests/support.py` states what the guard can and cannot attribute.

## What it still cannot attribute

- A commit that changes path P *and* a test that writes P in the same run: the write is attributed to
  the commit. The guard proves the tree now matches something a commit did, not that no test wrote.
- A write reverted to its exact baseline bytes by the end of the run - no digest can see it. That is
  why the store guard still refuses the open rather than trusting the digest.
- Which process or person made a commit.
