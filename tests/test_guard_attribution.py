"""TESTOPS-64 AC5: the write guard tells a commit during the run from a write by the suite.

The guard failed on ``main`` because a ticket file was committed from another shell mid-run: a true
observation (the working tree changed) with a false attribution ("the suite wrote outside tmp_path").
These tests pin the three verdicts by driving ``attribute_differences`` with synthetic snapshots and
synthetic commits - no test here commits, writes outside ``tmp_path``, or touches the real checkout,
so the guard cannot fire on its own author again.
"""
from __future__ import annotations

from support import AttributionReport, RepoState, attribute_differences

BEFORE_HEAD = "1111111111111111111111111111111111111111"
AFTER_HEAD = "2222222222222222222222222222222222222222"


def _diff(before, after, *, before_state, after_state, trees):
    """Drive the comparison with synthetic trees: ``trees`` maps a commit sha to path -> blob sha."""
    return attribute_differences(before, after, before_state=before_state, after_state=after_state,
                                 commit_blobs=trees.get)


def test_a_commit_during_the_run_explains_a_tracked_change(repo_guard):
    """AC1: HEAD moved and the path's blob differs between the two commits - report, do not fail."""
    before = {"factory/tickets/TESTOPS-64.md": (10, "digest-before")}
    after = {"factory/tickets/TESTOPS-64.md": (11, "digest-after")}
    report = _diff(before, after,
                   before_state=RepoState(BEFORE_HEAD, {}),
                   after_state=RepoState(AFTER_HEAD, {"factory/tickets/TESTOPS-64.md": "blob-2"}),
                   trees={BEFORE_HEAD: {"factory/tickets/TESTOPS-64.md": "blob-1"},
                          AFTER_HEAD: {"factory/tickets/TESTOPS-64.md": "blob-2"}})

    assert report.failures == ()
    assert report.changed_by_commit == ("factory/tickets/TESTOPS-64.md",)
    assert report.summary()[0] == (
        "write guard: 1 file changed by a commit during the run, 0 files unexplained")


def test_a_write_to_data_with_no_commit_still_fails(repo_guard):
    """AC2: the loud case stays loud, names the path, and says no commit accounts for it."""
    before = {"data/testops.db": (100, "digest-before")}
    after = {"data/testops.db": (200, "digest-after")}
    report = _diff(before, after,
                   before_state=RepoState(BEFORE_HEAD, {"data/testops.db": "blob-1"}),
                   after_state=RepoState(AFTER_HEAD, {"data/testops.db": "blob-9"}),
                   # The commit that landed during the run does not touch data/ at all.
                   trees={BEFORE_HEAD: {"data/testops.db": "blob-1", "readme.md": "blob-r"},
                          AFTER_HEAD: {"data/testops.db": "blob-1", "readme.md": "blob-r2"}})

    assert report.failures == ("data/testops.db",)
    message = report.failure_message()
    assert "data/testops.db" in message
    assert "no commit" in message
    assert "the suite wrote outside tmp_path" in message
    assert report.summary()[0] == (
        "write guard: 0 files changed by a commit during the run, 1 file unexplained")


def test_an_untracked_file_is_never_excused_by_a_commit(repo_guard):
    """AC3: HEAD moved, but the new file is in no commit's tree - it still fails."""
    before = {}
    after = {"data/leaked.db": (64, "digest-new")}
    report = _diff(before, after,
                   before_state=RepoState(BEFORE_HEAD, {}),
                   after_state=RepoState(AFTER_HEAD, {}),
                   trees={BEFORE_HEAD: {"readme.md": "blob-r"},
                          AFTER_HEAD: {"readme.md": "blob-r2"}})

    assert report.failures == ("data/leaked.db",)
    assert report.untracked == ("data/leaked.db",)
    assert "data/leaked.db" in report.failure_message()
    assert "write guard: 1 untracked addition no commit accounts for" in report.summary()


def test_a_committed_deletion_is_reported_not_failed(repo_guard):
    """AC3: a file deleted by the run's commit is explained, not blamed on the suite."""
    before = {"factory/tickets/TESTOPS-63.md": (20, "digest-old")}
    after = {}
    report = _diff(before, after,
                   before_state=RepoState(BEFORE_HEAD, {"factory/tickets/TESTOPS-63.md": "blob-1"}),
                   after_state=RepoState(AFTER_HEAD, {}),
                   trees={BEFORE_HEAD: {"factory/tickets/TESTOPS-63.md": "blob-1"},
                          AFTER_HEAD: {}})

    assert report.failures == ()
    assert report.deleted_by_commit == ("factory/tickets/TESTOPS-63.md",)
    assert any("deleted by a commit" in line for line in report.summary())


def test_the_report_counts_each_class_separately(repo_guard):
    """AC4: "2 files changed by a commit, 0 unexplained" is printed, not inferred from a pass."""
    before = {"a.py": (1, "a-old"), "b.py": (1, "b-old"), "data/db": (5, "db-old")}
    after = {"a.py": (1, "a-new"), "b.py": (1, "b-new"), "data/db": (9, "db-new"),
             "new.txt": (1, "new")}
    report = _diff(before, after,
                   before_state=RepoState(BEFORE_HEAD, {}),
                   after_state=RepoState(AFTER_HEAD, {}),
                   trees={BEFORE_HEAD: {"a.py": "a1", "b.py": "b1", "data/db": "d1"},
                          AFTER_HEAD: {"a.py": "a2", "b.py": "b2", "data/db": "d1"}})

    assert report.changed_by_commit == ("a.py", "b.py")
    assert report.failures == ("data/db", "new.txt")
    assert report.summary()[0] == (
        "write guard: 2 files changed by a commit during the run, 1 file unexplained")
    assert any("untracked addition" in line for line in report.summary())


def test_without_a_commit_nothing_is_excused(repo_guard):
    """A checkout with no commit, or no git, attributes nothing: every change stays a failure."""
    report = _diff({"x": (1, "old")}, {"x": (2, "new")},
                   before_state=RepoState(None, {}),
                   after_state=RepoState(None, {}),
                   trees={})
    assert report.failures == ("x",)


def test_head_that_did_not_move_excuses_nothing(repo_guard):
    """A dirty baseline commit does not launder a later write: the guard compares the same commit."""
    report = _diff({"x": (1, "old")}, {"x": (2, "new")},
                   before_state=RepoState(BEFORE_HEAD, {"x": "blob-1"}),
                   after_state=RepoState(BEFORE_HEAD, {"x": "blob-9"}),
                   trees={BEFORE_HEAD: {"x": "blob-1"}})
    assert report.failures == ("x",)


def test_baseline_records_head_and_the_index(repo_guard):
    """AC1: the baseline is HEAD plus the index, not the digest alone."""
    assert repo_guard.state.head, "the guard must record HEAD at baseline"
    assert "tests/support.py" in repo_guard.state.index, (
        "the guard must record the index at baseline, path -> blob sha")
    assert repo_guard.snapshot["tests/support.py"], "the digest of the tree is still the comparison"


def test_an_empty_report_has_nothing_to_say():
    """The summary line is printed even when nothing changed, so a pass is legible as a pass."""
    report = AttributionReport()
    assert report.failures == ()
    assert report.summary() == ["write guard: 0 files changed by a commit during the run, "
                                "0 files unexplained"]
