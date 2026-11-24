---
id: TESTOPS-64
title: The isolation tripwire cannot tell a commit from a write
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-60
---

# TESTOPS-64 - A tripwire that fires on its own author

## Why this exists

`tests/test_isolation.py` digests the whole working tree before the first test and compares it after the last. It exists
to prove the suite writes nothing to `data/` or the repository. It works.

It also failed on `main` today with 876 passed and one error, and the cause was **me**: a ticket file was committed to
`main` from another shell while the suite was running. The guard saw a changed working tree and reported the suite
writing outside `tmp_path` - a true observation with a false attribution. Its error message would have sent someone
hunting a leak that did not exist.

A tripwire that fires when its own repository is used is a tripwire people learn to ignore, and this one guards the
invariant that stopped our test runs from writing into the live store. It must stay loud for a real write, so it has to
get better at attributing.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The guard records `HEAD` and the index state at baseline. On comparison, a path that changed **and** whose change is explained by a commit made during the run (HEAD moved and the path's blob differs between the two commits) is reported separately as *changed by a commit during the run*, and does not fail the suite. |
| AC2 | A path that changed with **no** commit explaining it still fails, with the message naming the path and saying no commit accounts for it - the real-write case must remain as loud as it is now. |
| AC3 | Untracked additions are never excused by a commit: a new file that is not in the new commit's tree fails the guard. A file deleted and then committed is reported, not failed. |
| AC4 | The guard's report distinguishes the two classes in its output (a line per class with counts), so a reader can see "2 files changed by a commit, 0 unexplained" rather than inferring it from a pass. |
| AC5 | Pinned by tests: a simulated mid-run commit to a tracked file passes with the explanation recorded; a simulated mid-run write to `data/` with no commit still fails; a simulated mid-run untracked file still fails. The three cases must be in `tests/`, not demonstrated by hand. |
| AC6 | Full suite green; contract suite green; no case-page golden changes; the module docstring states what the guard can and cannot attribute. |
