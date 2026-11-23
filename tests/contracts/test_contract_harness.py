"""TESTOPS-53 AC3: pins the prohibition, so a live default cannot come back quietly.

Six separate facts are pinned here:

  * the suite's configured base is the loopback server this session started, never the live
    host/port, and never a URL read from the environment;
  * the store the server renders is under the trusted temp directory and is not the live store;
  * the fixture refuses a store that is not under the temp directory;
  * a server that cannot start is a skip with a reason (``ServerUnavailable`` that the session
    fixture turns into ``pytest.skip``), not a fallback to something else;
  * TESTOPS-58: the temp root is discovered without environment variables and captured once, and
    a temp variable moved into the repository, the home directory or a checkout's ``data/`` is
    refused by name - with the suite skipping rather than building a store there;
  * TESTOPS-58: ``PYTHONHOME`` inherited from the parent cannot stop the child server.

The source scan reads the suite file itself: if ``BASE = os.environ.get(...)`` with a live default
is reintroduced, this fails even though the environment happens to be harmless at the time.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import uuid
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
    temp_root = harness.temp_root()
    assert store_dir == temp_root or temp_root in store_dir.parents, (
        "the contract server is rendering %s, which is not under the trusted temp directory %s"
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


# TESTOPS-58 ------------------------------------------------------------------------------------


def test_the_trusted_temp_root_is_discovered_without_environment_variables(monkeypatch):
    """AC2: moving TMPDIR moves tempfile's answer, and the root the suite trusts does not move."""
    trusted = harness.temp_root()
    assert trusted.is_absolute(), "the trusted temp root is not an absolute path: %r" % trusted
    assert trusted == harness.TRUSTED_TEMP_ROOT

    elsewhere = Path.home() / (".testops-58-moved-%s" % uuid.uuid4().hex[:12])
    elsewhere.mkdir()
    try:
        monkeypatch.setenv("TMPDIR", str(elsewhere))
        monkeypatch.setattr(tempfile, "tempdir", None)  # drop tempfile's cache so TMPDIR is honoured

        assert Path(tempfile.gettempdir()).resolve() == elsewhere.resolve(), (
            "TMPDIR no longer moves tempfile.gettempdir(), so this test no longer proves anything")
        assert harness.temp_root() == trusted, (
            "the trusted temp root followed TMPDIR to %s" % harness.temp_root())
        assert not harness.under_temp(elsewhere), (
            "a store under the moved TMPDIR would be accepted as disposable")
        with pytest.raises(harness.StoreNotDisposable):
            harness.require_disposable_store(elsewhere / "data")
    finally:
        shutil.rmtree(elsewhere, ignore_errors=True)


def test_a_temp_variable_inside_the_repository_is_refused_by_name():
    """AC1: the refusal names the variable and the resolved path, for each forbidden location."""
    cases = {
        "TMPDIR": harness.ROOT / "build" / "junk",
        "TEMP": harness.ROOT / "data" / "junk",
        "TMP": Path.home() / "testops-tmp-attack",
    }
    for name, location in cases.items():
        problem = harness.temp_root_problem({name: str(location)})
        assert problem, "%s=%s was accepted as a disposable location" % (name, location)
        assert name in problem, "the refusal does not name %s: %s" % (name, problem)
        assert str(location.resolve()) in problem, (
            "the refusal does not name the resolved path %s: %s" % (location.resolve(), problem))

    # The OS's own temp directory is under the home directory on this host, and must stay usable.
    clean = harness.temp_root_problem({name: str(harness.temp_root())
                                       for name in harness.TEMP_VARIABLES})
    assert clean is None, "the suite's own temp directory was refused: %s" % clean
    # So must an environment with none of the variables set at all.
    assert harness.temp_root_problem({}) is None


def test_a_poisoned_temp_variable_makes_the_contract_suite_skip(tmp_path):
    """AC3, direction one: with a poison TMPDIR the suite skips and builds no store there.

    Run as a real interpreter, because the decision is taken at harness import - which is the
    point: nothing may get as far as creating pytest's temp directory.
    """
    poison = Path.home() / (".testops-58-poison-%s" % uuid.uuid4().hex[:12])
    poison.mkdir()
    try:
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("TESTOPS_") and key not in harness._LAUNCHER_ENV_DROP}
        env.update({"TMPDIR": str(poison), "PYTHONDONTWRITEBYTECODE": "1"})
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", str(CONTRACTS), "-q", "-rs", "--no-header",
             "-p", "no:cacheprovider"],
            cwd=str(tmp_path), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=300)
        output = completed.stdout
        assert completed.returncode == 0, (
            "poisoning TMPDIR made the suite fail instead of skip (exit %d):\n%s"
            % (completed.returncode, output[-3000:]))
        assert "skipped" in output, "the suite ran instead of skipping:\n%s" % output[-3000:]
        assert "TMPDIR" in output and str(poison.resolve()) in output, (
            "the skip reason does not name the variable and the path:\n%s" % output[-3000:])
        assert not list(poison.rglob("*.db")), (
            "a store was built inside the poisoned directory: %s"
            % [str(path) for path in poison.rglob("*.db")])
    finally:
        shutil.rmtree(poison, ignore_errors=True)


def test_an_inherited_pythonhome_cannot_stop_the_child_server(tmp_path, monkeypatch):
    """AC4: PYTHONHOME in the parent would kill the child before it binds; it is stripped."""
    monkeypatch.setenv("PYTHONHOME", str(tmp_path / "not-an-interpreter"))
    store_dir = tmp_path / "pythonhome-check" / "data"
    server = harness.start_contract_server(store_dir)
    try:
        with urllib.request.urlopen(server.base_url + "/runs", timeout=10) as response:
            assert response.status == 200
    finally:
        server.stop()

