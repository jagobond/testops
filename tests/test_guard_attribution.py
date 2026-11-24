"""TESTOPS-64/66 AC5: the write guard tells a commit during the run from a write by the suite.

The guard failed on ``main`` because a ticket file was committed from another shell mid-run: a true
observation (the working tree changed) with a false attribution ("the suite wrote outside tmp_path").
TESTOPS-66 sharpened the rule: a commit excuses a path only when the working tree's digest equals the
blob the commit holds for it. A content mismatch, a staged-but-uncommitted change and git
unavailability are each their own failure. TESTOPS-67 adds the three boundaries: policy-ignored paths
are counted and named but never attributed, an unreadable tree (corrupt object store) is unreadable
rather than staged, and blob and sha256 digests are never compared. These tests pin the verdicts by
driving ``attribute_differences`` with synthetic snapshots and synthetic commits - no test here
commits, writes outside ``tmp_path``, or touches the real checkout, so the guard cannot fire on its
own author again. The corruption test uses a disposable git repository in ``tmp_path``.
"""
from __future__ import annotations

import os
import subprocess
import stat
from pathlib import Path

from support import (AttributionReport, GitRepository, RepoState, Snapshot, attribute_differences,
                     repository_ignored_snapshot, repository_snapshot)

BEFORE_HEAD = "1111111111111111111111111111111111111111"
AFTER_HEAD = "2222222222222222222222222222222222222222"


def _diff(before, after, *, before_state, after_state, trees, before_ignored=None,
          after_ignored=None):
    """Drive the comparison with synthetic trees: ``trees`` maps a commit sha to path -> blob sha."""
    return attribute_differences(before, after, before_state=before_state, after_state=after_state,
                                 commit_blobs=trees.get,
                                 before_ignored=before_ignored, after_ignored=after_ignored)


def _classes(report):
    """Every path in the report, grouped by the class that claimed it."""
    return {
        "changed_by_commit": report.changed_by_commit,
        "added_by_commit": report.added_by_commit,
        "deleted_by_commit": report.deleted_by_commit,
        "staged": report.staged,
        "unexplained": report.unexplained,
        "untracked": report.untracked,
        "unreadable": report.unreadable,
        "ignored_changed": report.ignored_changed,
    }


def _flatten(report):
    return [path for paths in _classes(report).values() for path in paths]


def test_a_commit_during_the_run_explains_a_tracked_change(repo_guard):
    """AC1: HEAD moved and the working tree equals the new commit's blob - report, do not fail."""
    before = {"factory/tickets/TESTOPS-64.md": (10, "blob-1")}
    after = {"factory/tickets/TESTOPS-64.md": (11, "blob-2")}
    report = _diff(before, after,
                   before_state=RepoState(BEFORE_HEAD, {"factory/tickets/TESTOPS-64.md": "blob-1"}),
                   after_state=RepoState(AFTER_HEAD, {"factory/tickets/TESTOPS-64.md": "blob-2"}),
                   trees={BEFORE_HEAD: {"factory/tickets/TESTOPS-64.md": "blob-1"},
                          AFTER_HEAD: {"factory/tickets/TESTOPS-64.md": "blob-2"}})

    assert report.failures == ()
    assert report.changed_by_commit == ("factory/tickets/TESTOPS-64.md",)
    assert "1 file changed by a commit during the run" in report.summary()[0]
    assert "0 files unexplained" in report.summary()[0]


def test_a_write_to_data_with_no_commit_still_fails(repo_guard):
    """AC2: the loud case stays loud, names the path, and says no commit accounts for it."""
    before = {"data/testops.db": (100, "blob-1")}
    after = {"data/testops.db": (200, "blob-9")}
    report = _diff(before, after,
                   before_state=RepoState(BEFORE_HEAD, {"data/testops.db": "blob-1"}),
                   # The index did not move: this is a plain write, not a staged one.
                   after_state=RepoState(AFTER_HEAD, {"data/testops.db": "blob-1"}),
                   # The commit that landed during the run does not touch data/ at all.
                   trees={BEFORE_HEAD: {"data/testops.db": "blob-1", "readme.md": "blob-r"},
                          AFTER_HEAD: {"data/testops.db": "blob-1", "readme.md": "blob-r2"}})

    assert report.failures == ("data/testops.db",)
    assert report.staged == ()
    message = report.failure_message()
    assert "data/testops.db" in message
    assert "no commit" in message
    assert "the suite wrote outside tmp_path" in message
    assert "0 files changed by a commit during the run" in report.summary()[0]
    assert "1 file unexplained" in report.summary()[0]


def test_an_untracked_file_is_never_excused_by_a_commit(repo_guard):
    """AC3: HEAD moved, but the new file is in no commit's tree - it still fails."""
    before = {}
    after = {"data/leaked.db": (64, "blob-new")}
    report = _diff(before, after,
                   before_state=RepoState(BEFORE_HEAD, {}),
                   after_state=RepoState(AFTER_HEAD, {}),
                   trees={BEFORE_HEAD: {"readme.md": "blob-r"},
                          AFTER_HEAD: {"readme.md": "blob-r2"}})

    assert report.failures == ("data/leaked.db",)
    assert report.untracked == ("data/leaked.db",)
    assert "data/leaked.db" in report.failure_message()
    assert "1 untracked addition" in report.summary()[0]


def test_a_content_mismatch_fails_naming_the_working_tree_and_commit(repo_guard):
    """AC1: the commit touched the path, but the working tree's bytes are not the commit's."""
    before = {"factory/tickets/TESTOPS-64.md": (10, "blob-1")}
    after = {"factory/tickets/TESTOPS-64.md": (11, "blob-3")}
    report = _diff(before, after,
                   before_state=RepoState(BEFORE_HEAD, {"factory/tickets/TESTOPS-64.md": "blob-1"}),
                   after_state=RepoState(AFTER_HEAD, {"factory/tickets/TESTOPS-64.md": "blob-2"}),
                   trees={BEFORE_HEAD: {"factory/tickets/TESTOPS-64.md": "blob-1"},
                          AFTER_HEAD: {"factory/tickets/TESTOPS-64.md": "blob-2"}})

    assert report.failures == ("factory/tickets/TESTOPS-64.md",)
    assert report.unexplained == ("factory/tickets/TESTOPS-64.md",)
    assert report.content_mismatches == (("factory/tickets/TESTOPS-64.md", "blob-2", "blob-3"),)
    message = report.failure_message()
    assert "factory/tickets/TESTOPS-64.md" in message
    assert "expected blob blob-2" in message
    assert "observed digest blob-3" in message
    assert "the working tree and the commit disagree" in message


def test_a_staged_but_uncommitted_change_fails(repo_guard):
    """AC2: HEAD did not move; the index did and the working tree matches the index, not HEAD."""
    before = {"data/staged.db": (10, "blob-1")}
    after = {"data/staged.db": (11, "blob-2")}
    report = _diff(before, after,
                   before_state=RepoState(BEFORE_HEAD, {"data/staged.db": "blob-1"}),
                   after_state=RepoState(BEFORE_HEAD, {"data/staged.db": "blob-2"}),
                   trees={BEFORE_HEAD: {"data/staged.db": "blob-1"}})

    assert report.failures == ("data/staged.db",)
    assert report.staged == ("data/staged.db",)
    assert report.unexplained == ()
    message = report.failure_message()
    assert "data/staged.db" in message
    assert "staged but uncommitted" in message
    assert "1 staged but uncommitted change" in report.summary()[0]


def test_a_committed_deletion_is_reported_not_failed(repo_guard):
    """AC3: a file deleted by the run's commit is explained, not blamed on the suite."""
    before = {"factory/tickets/TESTOPS-63.md": (20, "blob-1")}
    after = {}
    report = _diff(before, after,
                   before_state=RepoState(BEFORE_HEAD, {"factory/tickets/TESTOPS-63.md": "blob-1"}),
                   after_state=RepoState(AFTER_HEAD, {}),
                   trees={BEFORE_HEAD: {"factory/tickets/TESTOPS-63.md": "blob-1"},
                          AFTER_HEAD: {}})

    assert report.failures == ()
    assert report.deleted_by_commit == ("factory/tickets/TESTOPS-63.md",)
    assert "1 file deleted by a commit during the run" in report.summary()[0]


def test_without_a_commit_nothing_is_excused(repo_guard):
    """A checkout with no commit attributes nothing: every change stays a failure."""
    report = _diff({"x": (1, "old")}, {"x": (2, "new")},
                   before_state=RepoState(None, {}),
                   after_state=RepoState(None, {}),
                   trees={})
    assert report.failures == ("x",)


def test_head_that_did_not_move_excuses_nothing(repo_guard):
    """A dirty baseline commit does not launder a later write: the guard compares the same commit."""
    report = _diff({"x": (1, "old")}, {"x": (2, "new")},
                   before_state=RepoState(BEFORE_HEAD, {"x": "blob-1"}),
                   after_state=RepoState(BEFORE_HEAD, {"x": "blob-1"}),
                   trees={BEFORE_HEAD: {"x": "blob-1"}})
    assert report.failures == ("x",)
    assert report.staged == ()


def test_baseline_records_head_and_the_index(repo_guard):
    """AC1: the baseline is HEAD plus the index, not the digest alone."""
    assert repo_guard.state.head, "the guard must record HEAD at baseline"
    assert repo_guard.state.readable, "the guard must record whether git was readable"
    assert "tests/support.py" in repo_guard.state.index, (
        "the guard must record the index at baseline, path -> blob sha")
    assert repo_guard.snapshot["tests/support.py"], "the digest of the tree is still the comparison"


def test_an_empty_report_has_nothing_to_say():
    """The summary line is printed even when nothing changed, so a pass is legible as a pass."""
    report = AttributionReport()
    assert report.failures == ()
    # TESTOPS-69 AC3: "git readable: yes/no" is in every summary, a pass included.
    assert report.summary() == [
        "write guard: git readable: yes; 0 files changed by a commit during the run, 0 files "
        "deleted by a commit during the run, 0 staged but uncommitted changes, 0 files unexplained, "
        "0 untracked additions no commit accounts for, 0 unreadable files, 0 paths under "
        "policy-ignored directories changed (report-only: not attributed)"
    ]


def test_the_partition_counts_every_difference_exactly_once(repo_guard):
    """AC4: every difference is in exactly one class, and the total reconciles."""
    before = {
        "changed.txt": (10, "c1"),
        "deleted.txt": (10, "d1"),
        "staged.txt": (10, "s1"),
        "written.txt": (10, "w1"),
        "mismatch.txt": (10, "m1"),
        "gone.txt": (10, "g1"),
        "staged-deleted.txt": (10, "sd1"),
    }
    after = {
        "changed.txt": (11, "c2"),
        "added.txt": (11, "a2"),
        "staged.txt": (11, "s2"),
        "written.txt": (11, "w2"),
        "mismatch.txt": (11, "m3"),
        "leak.txt": (11, "l1"),
    }
    before_index = {
        "changed.txt": "c1",
        "deleted.txt": "d1",
        "staged.txt": "s1",
        "written.txt": "w1",
        "mismatch.txt": "m1",
        "gone.txt": "g1",
        "staged-deleted.txt": "sd1",
    }
    after_index = {
        "changed.txt": "c2",
        "added.txt": "a2",
        "staged.txt": "s2",
        "written.txt": "w1",
        "mismatch.txt": "m2",
        "gone.txt": "g1",
    }
    trees = {
        BEFORE_HEAD: {
            "changed.txt": "c1",
            "deleted.txt": "d1",
            "staged.txt": "s1",
            "written.txt": "w1",
            "mismatch.txt": "m1",
            "gone.txt": "g1",
            "staged-deleted.txt": "sd1",
        },
        AFTER_HEAD: {
            "changed.txt": "c2",
            "added.txt": "a2",
            "staged.txt": "s1",
            "written.txt": "w1",
            "mismatch.txt": "m2",
            "gone.txt": "g1",
            "staged-deleted.txt": "sd1",
        },
    }

    report = _diff(before, after,
                   before_state=RepoState(BEFORE_HEAD, before_index),
                   after_state=RepoState(AFTER_HEAD, after_index),
                   trees=trees,
                   before_ignored={},
                   after_ignored={"build/out.txt": (5, "i1")})

    expected = set(before) ^ set(after)
    expected |= {path for path in set(before) & set(after) if before[path] != after[path]}
    flat = _flatten(report)
    assert len(flat) == len(set(flat)), "a difference was counted in more than one class"
    assert set(flat) == expected | {"build/out.txt"}, "a difference was dropped or invented"

    assert report.changed_by_commit == ("changed.txt",)
    assert report.added_by_commit == ("added.txt",)
    assert report.deleted_by_commit == ("deleted.txt",)
    assert report.staged == ("staged-deleted.txt", "staged.txt")
    assert report.unexplained == ("gone.txt", "mismatch.txt", "written.txt")
    assert report.untracked == ("leak.txt",)
    assert report.unreadable == ()
    assert report.content_mismatches == (("mismatch.txt", "m2", "m3"),)
    assert report.ignored_changed == ("build/out.txt",)
    assert "build/out.txt" not in report.failures, "ignored paths are report-only, not failures"

    line = report.summary()[0]
    assert "2 files changed by a commit during the run" in line
    assert "1 file deleted by a commit during the run" in line
    assert "2 staged but uncommitted changes" in line
    assert "3 files unexplained" in line
    assert "1 untracked addition" in line
    assert "0 unreadable files" in line
    assert "1 path under policy-ignored directories changed (report-only: not attributed)" in line
    assert "build/out.txt" in report.summary()[1]
    assert sum(len(paths) for paths in _classes(report).values()) == len(expected) + 1

    # The same partition when git cannot be read: every difference is unreadable, and the message
    # points at git rather than at the suite. The policy-ignored path is still reported, still not
    # attributed.
    unreadable = _diff(before, after,
                       before_state=RepoState(None, {}, readable=False),
                       after_state=RepoState(None, {}, readable=False),
                       trees={},
                       before_ignored={},
                       after_ignored={"build/out.txt": (5, "i1")})
    assert unreadable.unreadable == tuple(sorted(expected))
    assert unreadable.ignored_changed == ("build/out.txt",)
    assert unreadable.failures == unreadable.unreadable
    assert len(_flatten(unreadable)) == len(set(_flatten(unreadable))) == len(expected) + 1
    message = unreadable.failure_message()
    assert "the repository could not be read" in message
    assert "git is the suspect" in message
    assert "the suite wrote" not in message


def test_a_write_under_a_policy_ignored_directory_is_visible_not_attributed(tmp_path):
    """AC1: a write to build/ is counted and named in the summary, and is not a failure."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.txt").write_bytes(b"kept\n")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "x.txt").write_bytes(b"build output\n")
    (tmp_path / "pkg" / "__pycache__").mkdir(parents=True)
    (tmp_path / "pkg" / "__pycache__" / "z.pyc").write_bytes(b"cache\n")

    normal = repository_snapshot(tmp_path)
    ignored = repository_ignored_snapshot(tmp_path)
    assert set(normal) == {"src/a.txt"}
    assert set(ignored) == {"build/x.txt", "pkg/__pycache__/z.pyc"}

    report = attribute_differences(normal, normal,
                                   before_state=RepoState(None, {}),
                                   after_state=RepoState(None, {}),
                                   commit_blobs=lambda _: {},
                                   before_ignored={}, after_ignored=ignored)

    assert report.failures == ()
    assert report.ignored_changed == ("build/x.txt", "pkg/__pycache__/z.pyc")
    line = report.summary()[0]
    assert "0 files unexplained" in line
    assert "2 paths under policy-ignored directories changed (report-only: not attributed)" in line
    assert "build/x.txt" in report.summary()[1]
    assert "pkg/__pycache__/z.pyc" in report.summary()[1]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def test_a_corrupt_repository_is_unreadable_not_staged(tmp_path):
    """AC2: a corrupt object store makes the tree unreadable, names git, and attributes nothing."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")

    (repo / "f.txt").write_bytes(b"one\n")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-q", "-m", "one")
    before = repository_snapshot(repo)
    before_state = GitRepository(repo).state()

    (repo / "f.txt").write_bytes(b"two\n")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-q", "-m", "two")
    after = repository_snapshot(repo)
    after_state = GitRepository(repo).state()
    assert before_state.head != after_state.head
    # The working tree agrees with the new index: before the fix this is exactly the shape the
    # staged rule claimed, while the commit's tree was silently unavailable.
    assert after["f.txt"][1] == after_state.index["f.txt"]

    assert after_state.head is not None
    obj = repo / ".git" / "objects" / after_state.head[:2] / after_state.head[2:]
    assert obj.is_file()
    os.chmod(obj, stat.S_IWRITE)  # git stores loose objects read-only
    obj.write_bytes(b"corrupt")

    repository = GitRepository(repo)
    assert repository.commit_blobs(after_state.head) is None
    report = attribute_differences(before, after,
                                   before_state=before_state, after_state=after_state,
                                   commit_blobs=repository.commit_blobs,
                                   before_alphabet=before.alphabet,
                                   after_alphabet=after.alphabet)

    assert report.unreadable == ("f.txt",)
    assert report.staged == ()
    assert report.changed_by_commit == report.added_by_commit == ()
    assert report.failures == ("f.txt",)
    message = report.failure_message()
    assert "could not read the tree" in message
    assert "git" in message
    assert "a staged but uncommitted change appeared" not in message
    assert "the suite wrote" not in message


def test_blob_and_sha256_digests_are_never_compared(repo_guard):
    """AC3: a baseline in blob shas and a comparison in sha256 fail as unreadable, not as a mass write."""
    before = Snapshot({"f.txt": (10, "blob-1")}, alphabet="git-blob")
    after = Snapshot({"f.txt": (10, "0" * 64)}, alphabet="sha256")

    report = attribute_differences(before, after,
                                   before_state=RepoState(BEFORE_HEAD, {"f.txt": "blob-1"}),
                                   after_state=RepoState(BEFORE_HEAD, {"f.txt": "blob-1"}),
                                   commit_blobs=lambda _: {},
                                   before_alphabet=before.alphabet,
                                   after_alphabet=after.alphabet)

    assert report.not_comparable is True
    assert report.unreadable == ("f.txt",)
    assert report.failures == ("f.txt",)
    assert report.changed_by_commit == ()
    assert report.staged == ()
    assert report.unexplained == ()
    message = report.failure_message()
    assert "not comparable" in message
    assert "git-blob" in message and "sha256" in message
    assert "the suite wrote" not in message

    # The ignored half is subject to the same rule: an alphabet mismatch there is not compared
    # either, even when the ordinary half is unchanged.
    mixed_ignored = attribute_differences(before, before,
                                          before_state=RepoState(BEFORE_HEAD, {}),
                                          after_state=RepoState(BEFORE_HEAD, {}),
                                          commit_blobs=lambda _: {},
                                          before_ignored_alphabet="git-blob",
                                          after_ignored_alphabet="sha256")
    assert mixed_ignored.not_comparable is True
    assert mixed_ignored.failures, "an incomparable ignored snapshot must still fail the guard"
    assert "not comparable" in mixed_ignored.failure_message()
