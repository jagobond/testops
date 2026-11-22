"""AC10: the suite writes nothing to the repository, to ``data/``, or outside pytest's tmp_path.

The session-scoped ``repo_guard`` fixture (conftest.py) digests the working tree before the first
test and re-checks after the last, so this holds for every test in the run. This test names the
comparison explicitly.
"""
from __future__ import annotations

from support import repository_snapshot, snapshot_difference


def test_suite_writes_nothing_to_data_or_the_repository(repo_guard):
    difference = snapshot_difference(repo_guard, repository_snapshot())
    assert not any(difference.values()), (
        "the suite wrote outside tmp_path: "
        f"added={difference['added']} removed={difference['removed']} "
        f"changed={difference['changed']}"
    )