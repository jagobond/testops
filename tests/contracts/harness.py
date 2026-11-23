"""The contract suite's own server, in its own temp directory (TESTOPS-53).

The suite used to default to the live server on 8791 and POST a ``contract-audit-<timestamp>``
project into the store the product is running from. A bare ``pytest`` on this repository therefore
wrote to the Product Owner's evidence. This module removes the possibility rather than warning
about it:

  * the store is **built here**, under pytest's temp directory, from the pinned seed in
    ``seed/`` - never opened from ``data/`` and never read from an environment variable;
  * the server is a **child process** launched with ``TESTOPS_DATA`` set to that temp directory
    and every inherited ``TESTOPS_*`` variable stripped, so nothing in the parent's environment
    can redirect it;
  * the child binds port **0** and reports the port it was given, so the suite talks to the socket
    it opened rather than to a port it guessed (on Windows a second binder on a chosen port can
    silently receive the traffic - the reason this is not "pick a free port, then connect");
  * :func:`require_disposable_store` refuses any store that is not under the system temp
    directory, and :func:`start_contract_server` calls it before it launches anything.

When the server cannot start, :class:`ServerUnavailable` says why and the suite skips. It never
falls back to a URL it was not given, and never guesses a host.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

SEED_JSON = HERE / "seed" / "seed.json"
SEED_BLOBS = HERE / "seed" / "blobs"

# The live deployment, named here only so a test can refuse it. Nothing in this suite connects to
# it: the harness binds 127.0.0.1 on a port the kernel chose.
LIVE_HOST = "100.121.128.21"
LIVE_PORT = 8791

HOST = "127.0.0.1"
START_TIMEOUT = 30.0
READY_TIMEOUT = 20.0

# The server the session started. ``None`` until the fixture runs and after it stops - there is no
# default address at module import, because a default is exactly what this ticket removed.
SERVER: "Server | None" = None

_TABLES_IN_INSERT_ORDER = (
    "project",
    "service",
    "snapshot",
    "artefact",
    "observation",
    "run",
    "claim",
    "case_",
    "finding",
    "case_state",
    "suppression",
    "inference",
)


class StoreNotDisposable(RuntimeError):
    """A store path outside the system temp directory was offered to the suite."""


class ServerUnavailable(RuntimeError):
    """The suite could not start the server it owns; the reason is the message."""


def under_temp(path) -> bool:
    """True when ``path`` resolves inside the system temp directory."""
    root = Path(tempfile.gettempdir()).resolve()
    target = Path(path).resolve()
    return target == root or root in target.parents


def require_disposable_store(data_dir) -> Path:
    """Refuse a store that is not under the temp directory.

    This is the fixture's own gate, not a warning: a disposable store is one the test run may
    create and delete, and only the system temp directory is guaranteed to be that.
    """
    target = Path(data_dir).resolve()
    if not under_temp(target):
        raise StoreNotDisposable(
            "refusing to point the contract suite at %s: it is not under the system temp "
            "directory (%s). The suite builds its own disposable store; it does not run against "
            "a persistent one." % (target, Path(tempfile.gettempdir()).resolve()))
    return target


def _read_seed() -> dict:
    return json.loads(SEED_JSON.read_text(encoding="utf-8"))


def _column_names(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute("PRAGMA table_info(%s)" % table)]


def build_seed_store(data_dir) -> Path:
    """Create a disposable store under ``data_dir`` from the pinned seed, and return it.

    The store is written to a fresh file: the seed is rows plus the blob files the pages need, not
    a database copied from a deployment. Nothing here reads ``data/`` or the environment.
    """
    data_dir = require_disposable_store(data_dir)
    db_path = data_dir / "testops.db"
    if db_path.exists():
        raise StoreNotDisposable("refusing to overwrite an existing store at %s" % db_path)
    data_dir.mkdir(parents=True, exist_ok=True)

    # The schema is the product's own DDL. The version is imported from the product rather than
    # written here, so a schema bump cannot leave the fixture claiming an old one.
    from testops.store import migrate

    schema = (ROOT / "testops" / "store" / "schema.sql").read_text(encoding="utf-8")
    seed = _read_seed()
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema)
        for table in _TABLES_IN_INSERT_ORDER:
            rows = seed.get(table) or []
            if not rows:
                continue
            valid = set(_column_names(conn, table))
            for row in rows:
                values = {k: v for k, v in row.items() if k in valid}
                columns = ", ".join(values)
                placeholders = ", ".join("?" for _ in values)
                conn.execute("INSERT INTO %s (%s) VALUES (%s)" % (table, columns, placeholders),
                             list(values.values()))
        conn.execute("INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('schema_version', ?)",
                     (str(migrate.CURRENT_VERSION),))
        conn.commit()
    finally:
        conn.close()

    blobs = data_dir / "blobs"
    for sha in seed.get("blobs") or []:
        target = blobs / sha[:2] / sha[2:]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((SEED_BLOBS / sha).read_bytes())
    return data_dir


class Server:
    """The child process and the address the kernel gave it."""

    def __init__(self, process: subprocess.Popen, port: int, store_dir: Path):
        self.process = process
        self.port = port
        self.store_dir = store_dir

    @property
    def base_url(self) -> str:
        return "http://%s:%d" % (HOST, self.port)

    def stop(self) -> None:
        process = self.process
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _wait_for_port(process: subprocess.Popen, timeout: float) -> int:
    """Read the ``PORT <n>`` line the child prints; raise ServerUnavailable with its output."""
    lines: list[str] = []
    found = threading.Event()

    def pump() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            lines.append(line.rstrip("\n"))
            if line.startswith("PORT "):
                found.set()

    reader = threading.Thread(target=pump, daemon=True)
    reader.start()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if found.wait(0.1):
            for line in lines:
                if line.startswith("PORT "):
                    try:
                        return int(line.split()[1])
                    except (IndexError, ValueError):
                        break
        if process.poll() is not None and not found.is_set():
            break
    raise ServerUnavailable(
        "the server process did not report a port (exit %r). Its output: %s"
        % (process.poll(), "\n".join(lines[-8:]) or "<none>"))


def _wait_for_ready(base_url: str, process: subprocess.Popen, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ServerUnavailable("the server exited (code %r) before it served a page"
                                    % process.returncode)
        try:
            with urllib.request.urlopen(base_url + "/", timeout=5) as response:
                if response.status == 200:
                    return
                last = "HTTP %s" % response.status
        except (urllib.error.URLError, OSError) as exc:
            last = repr(exc)
        time.sleep(0.15)
    raise ServerUnavailable("the server did not serve / within %.0fs (last error: %s)"
                            % (timeout, last))


def start_contract_server(data_dir, argv: list[str] | None = None) -> Server:
    """Build the store if needed and launch the product on a port the kernel chooses.

    ``argv`` exists so a test can prove the failure path by launching something that cannot serve.
    The normal call is not configurable: the same script, the same store, the same bind.
    """
    store_dir = require_disposable_store(data_dir)
    if not (store_dir / "testops.db").exists():
        build_seed_store(store_dir)

    command = argv or [sys.executable, str(HERE / "_server.py")]
    # Every inherited TESTOPS_* variable is dropped, not overridden: a parent shell pointing at a
    # persistent store must not be able to reach the child at all.
    env = {key: value for key, value in os.environ.items() if not key.startswith("TESTOPS_")}
    env.update({
        "TESTOPS_DATA": str(store_dir),
        "TESTOPS_ENV": str(store_dir / "no-such.env"),
        "PYTHONPATH": str(ROOT),
        "PYTHONNOUSERSITE": "1",
    })
    process = subprocess.Popen(command, cwd=str(ROOT), env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, bufsize=1)
    try:
        port = _wait_for_port(process, START_TIMEOUT)
        if port == LIVE_PORT:
            raise ServerUnavailable("the kernel handed out the live port %d; refusing to use it"
                                    % LIVE_PORT)
        server = Server(process, port, store_dir)
        _wait_for_ready(server.base_url, process, READY_TIMEOUT)
        return server
    except BaseException:
        Server(process, -1, store_dir).stop()
        raise
