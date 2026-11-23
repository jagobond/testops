"""Shared fixtures.

Two global obligations here:

  * AC10 of an earlier ticket: a session-scoped guard digests the repository before the first test
    and compares it after the last one, so a write by *any* test fails the run regardless of file
    or collection order.
  * TESTOPS-35 AC3: the suite cannot open a product store for writing. The guard refuses the
    connection itself, so a fixture script that reaches for ``data/testops.db`` fails at the line
    that reached for it rather than being noticed, if at all, by a digest an hour later. The only
    permitted access to a real store is a declared read-only open (``file:...?mode=ro``).
"""
from __future__ import annotations

import pytest

from support import (install_store_guard, repository_snapshot, snapshot_difference)
from wheel_build import build_wheel_for_session


@pytest.fixture(scope="session", autouse=True)
def store_guard():
    """TESTOPS-35 AC3: no test may open the live store for writing."""
    monkeypatch = install_store_guard()
    yield
    monkeypatch.undo()


@pytest.fixture(scope="session", autouse=True)
def repo_guard():
    """Session-wide guard against writes to the repository or to ``data/``."""
    before = repository_snapshot()
    yield before
    difference = snapshot_difference(before, repository_snapshot())
    assert not any(difference.values()), f"a test wrote into the repository: {difference}"


@pytest.fixture(scope="session")
def built_wheel(tmp_path_factory):
    """TESTOPS-48 AC4: one wheel per session, shared by packaging and distribution checks."""
    return build_wheel_for_session(tmp_path_factory)