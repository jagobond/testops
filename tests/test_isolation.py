"""AC10: the suite writes nothing to the repository, to ``data/``, or outside pytest's tmp_path.

The session-scoped ``repo_guard`` fixture (conftest.py) digests the working tree before the first
test and re-checks after the last, so this holds for every test in the run. This test names the
comparison explicitly.

TESTOPS-64: the comparison attributes before it accuses. A path whose blob differs between the
baseline commit and the commit at comparison was changed by a commit made during the run - a ticket
committed from another shell used to fail this test with "the suite wrote outside tmp_path". Such a
path is reported and does not fail. TESTOPS-66: the commit excuses the path only when the working
tree's digest equals the blob the commit holds; a mismatch fails and names the disagreement. A
staged-but-uncommitted change fails as staged, and git unavailability fails as unreadable rather than
accusing the suite. A path no commit accounts for still fails, and the message names it.
"""
from __future__ import annotations

from support import guard_report


def test_suite_writes_nothing_to_data_or_the_repository(repo_guard):
    report = guard_report(repo_guard)
    for line in report.summary():
        print(line)
    assert not report.failures, report.failure_message()
