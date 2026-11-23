"""Start the suite's own server for the whole contracts session (TESTOPS-53, TESTOPS-58).

The tests in this directory once pointed at the live deployment by default. They now point at a
server this fixture starts, on a port the kernel chose, over a store this fixture built under the
temp directory. When that cannot happen the suite skips with the reason; it never falls back.

TESTOPS-58: the temp directory is checked *before* pytest is asked for one. ``TMPDIR``/``TEMP``/
``TMP`` that resolve into the repository, the user's home or a checkout's ``data/`` make this
fixture skip - with the variable's name and the resolved path - rather than build a store there.
"""
from __future__ import annotations

import pytest

import harness


@pytest.fixture(scope="session", autouse=True)
def contract_server(tmp_path_factory):
    """The one server this suite talks to, or a skip that says why there is none."""
    problem = harness.TEMP_ROOT_PROBLEM or harness.temp_root_problem()
    if problem:
        pytest.skip("the contract suite will not build a store there: %s" % problem)
    store_dir = tmp_path_factory.mktemp("contract-store") / "data"
    try:
        server = harness.start_contract_server(store_dir)
    except (harness.ServerUnavailable, harness.StoreNotDisposable) as exc:
        pytest.skip("the contract suite could not start its own server: %s" % exc)
    harness.SERVER = server
    try:
        yield server
    finally:
        harness.SERVER = None
        server.stop()
