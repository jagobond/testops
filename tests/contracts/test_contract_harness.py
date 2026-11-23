"""TESTOPS-53 AC3: pins the prohibition, so a live default cannot come back quietly.

Four separate facts are pinned here:

  * the suite's configured base is the loopback server this session started, never the live
    host/port, and never a URL read from the environment;
  * the store the server renders is under the system temp directory and is not the live store;
  * the fixture refuses a store that is not under the temp directory;
  * a server that cannot start is a skip with a reason (``ServerUnavailable`` that the session
    fixture turns into ``pytest.skip``), not a fallback to something else.

The source scan reads the suite file itself: if ``BASE = os.environ.get(...)`` with a live default
is reintroduced, this fails even though the environment happens to be harmless at the time.
"""
from __future__ import annotations

import sys
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import pytest

import harness

CONTRACTS = Path(__file__).resolve().parent


def test_the_configured_base_is_the_suite_s_own_loopback_server(contract_server):
    """The address in use is the child on 127.0.0.1, on a port that is not the live one."""
    parsed = urlparse(contract_server.base_url)
    assert parsed.hostname == harness.HOST, (
        "the contract suite is talking to %r, not the loopback server it started"
        % contract_server.base_url)
    assert parsed.port and parsed.port > 0
    assert parsed.port != harness.LIVE_PORT, (
        "the contract suite is pointed at the live port %d" % harness.LIVE_PORT)
    assert harness.LIVE_HOST not in contract_server.base_url
    assert harness.SERVER is contract_server


def test_the_store_under_test_is_disposable_and_not_the_live_store(contract_server):
    """The server's store is built in the temp directory, not opened from a checkout."""
    store_dir = Path(contract_server.store_dir).resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    assert store_dir == temp_root or temp_root in store_dir.parents, (
        "the contract server is rendering %s, which is not under the temp directory %s"
        % (store_dir, temp_root))
    live_store = (harness.ROOT / "data" / "testops.db").resolve()
    assert store_dir / "testops.db" != live_store
    assert (store_dir / "testops.db").is_file(), "the disposable store was not built"


def test_a_persistent_store_is_refused():
    """The fixture's own gate: a store outside temp is an error, not a warning."""
    for persistent in (harness.ROOT / "data", Path.home() / "testops-data"):
        with pytest.raises(harness.StoreNotDisposable):
            harness.require_disposable_store(persistent)
        with pytest.raises(harness.StoreNotDisposable):
            harness.build_seed_store(persistent)


def test_an_inherited_store_variable_cannot_redirect_the_server(tmp_path, monkeypatch):
    """A parent TESTOPS_DATA pointed at the live data directory is stripped, not inherited."""
    monkeypatch.setenv("TESTOPS_DATA", str(harness.ROOT / "data"))
    monkeypatch.setenv("TESTOPS_BASE", "http://%s:%d" % (harness.LIVE_HOST, harness.LIVE_PORT))
    store_dir = tmp_path / "poison-check" / "data"
    server = harness.start_contract_server(store_dir)
    try:
        with urllib.request.urlopen(server.base_url + "/runs", timeout=10) as response:
            body = response.read().decode("utf-8", "replace")
        assert "restfulbooker" in body, "the seeded store did not serve the runs index"
        assert "cotw" not in body, (
            "the server served the live store's runs, so an inherited TESTOPS_DATA reached it")
    finally:
        server.stop()


def test_a_server_that_cannot_start_is_unavailable_not_a_fallback(tmp_path):
    """The failure path the session fixture turns into a skip: a reason, never another URL."""
    argv = [sys.executable, "-c",
            "import sys; sys.stderr.write('no listener here\\n'); sys.exit(3)"]
    with pytest.raises(harness.ServerUnavailable, match="did not report a port"):
        harness.start_contract_server(tmp_path / "cannot-start" / "data", argv=argv)


def test_no_live_default_is_left_in_the_contract_suite():
    """The suite file must not name a deployment address or read a base URL from the environment."""
    source = (CONTRACTS / "test_page_contracts.py").read_text(encoding="utf-8")
    assert harness.LIVE_HOST not in source, (
        "the live host is written into the contract suite again: it must only be reachable "
        "through harness.LIVE_HOST as a name to refuse")
    assert str(harness.LIVE_PORT) not in source, (
        "the live port is written into the contract suite again")
    assert "TESTOPS_BASE" not in source, (
        "the contract suite reads a base URL from the environment again")
