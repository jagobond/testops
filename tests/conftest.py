"""Shared fixtures.

Two global obligations here:

  * AC10 of an earlier ticket, sharpened by TESTOPS-64 and TESTOPS-66: a session-scoped guard digests
    the repository before the first test and compares it after the last one, so a write by *any* test
    fails the run regardless of file or collection order. A difference is only a write if no commit
    made during the run accounts for it: the baseline records ``HEAD`` and the index as well as the
    digest, and a path whose blob differs between the two commits is reported as *changed by a
    commit* only when the working-tree digest equals the blob the new commit holds. A staged but
    uncommitted change is its own failure, and git unavailability is reported as unreadable rather
    than blamed on the suite. A repository whose tree cannot be read (corrupt object store) is
    unreadable too, never staged, and git is named. A comparison whose two snapshots used different
    digest alphabets (git blob vs sha256) is unreadable as "not comparable" and compares nothing.
    Policy-ignored paths - ``build/``, ``dist/``, ``__pycache__/``, ``.pytest_cache/`` and ``*.pyc`` -
    are walked and counted, and the summary always states how many changed and that they are
    not attributed; the policy is **report-only**, so a legitimate build or cache write does not fail
    the run but can never be mistaken for "0 files" outside the guard's view (TESTOPS-67 AC1). The
    policy covers *untracked* churn only: a path the index or a commit tracks is never pruned or
    ignored by name, so a committed artefact is attributed like any other file (TESTOPS-69 AC4), and
    the summary states ``git readable: yes/no`` in every run, because the unreadable count is
    difference-driven and a zero cannot say whether git was read at all (TESTOPS-69 AC3). An unknown
    tracked set is not an empty one: when the tracked-path lookup fails, every walked path is content
    and nothing is pruned or ignored by name (TESTOPS-71 AC1), and ``git readable`` is ``no`` because
    that lookup is one of the reads it answers for (TESTOPS-71 AC2).
    Everything a commit cannot explain - including every untracked addition and every content
    mismatch - still fails and still names the path. What it cannot attribute is stated in
    ``support``'s docstring: a test write whose bytes equal the commit's blob is indistinguishable
    from the commit.
  * TESTOPS-35 AC3: the suite cannot open a product store for writing. The guard refuses the
    connection itself, so a fixture script that reaches for ``data/testops.db`` fails at the line
    that reached for it rather than being noticed, if at all, by a digest an hour later. The only
    permitted access to a real store is a declared read-only open (``file:...?mode=ro``).
"""
from __future__ import annotations

import pytest

from support import ROOT, guard_baseline, guard_report, install_store_guard
from wheel_build import build_wheel_for_session


@pytest.fixture(scope="session", autouse=True)
def store_guard():
    """TESTOPS-35 AC3: no test may open the live store for writing."""
    monkeypatch = install_store_guard()
    yield
    monkeypatch.undo()


@pytest.fixture(scope="session", autouse=True)
def repo_guard():
    """Session-wide guard against writes to the repository or to ``data/``.

    Yields the baseline (digest, ``HEAD``, index, and whether git was readable);
    ``support.guard_report`` turns it into a report that separates changes a commit accounts for
    from staged, unexplained and unreadable ones.
    """
    baseline = guard_baseline()
    # TESTOPS-49: a walk that found no files would make the comparison below vacuously empty, so
    # the snapshot is refused when it is empty and the directory it walked is named.
    assert baseline.snapshot, (
        f"the repository walk of {ROOT} found no files at all; the write guard would compare "
        "nothing with nothing and pass vacuously"
    )
    yield baseline
    report = guard_report(baseline)
    # TESTOPS-64 AC4: the report says which class each change fell into, with counts, whether or not
    # it fails - a reader never has to infer the outcome from a pass. pytest shows this on failure
    # and under -s.
    for line in report.summary():
        print(line)
    assert not report.failures, report.failure_message()


@pytest.fixture(scope="session")
def built_wheel(tmp_path_factory):
    """TESTOPS-48 AC4: one wheel per session, shared by packaging and distribution checks."""
    return build_wheel_for_session(tmp_path_factory)
