"""Shared fixtures.

The only global obligation here is AC10: a session-scoped guard digests the repository before the
first test and compares it after the last one, so a write by *any* test fails the run regardless of
file or collection order.
"""
from __future__ import annotations

import pytest

from support import repository_snapshot, snapshot_difference


@pytest.fixture(scope="session", autouse=True)
def repo_guard():
    """Session-wide guard against writes to the repository or to ``data/``."""
    before = repository_snapshot()
    yield before
    difference = snapshot_difference(before, repository_snapshot())
    assert not any(difference.values()), f"a test wrote into the repository: {difference}"