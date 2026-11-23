"""The contract suite's own server, in its own temp directory (TESTOPS-53).

The suite used to default to the live server on 8791 and POST a ``contract-audit-<timestamp>``
project into the store the product is running from. A bare ``pytest`` on this repository therefore
wrote to the Product Owner's evidence. This module removes the possibility rather than warning
about it:

  * the store is **built here**, under pytest's temp directory, from the pinned seed in
    ``seed/`` - never opened from ``data/`` and never read from an environment variable;
  * the server is a **child process** launched with ``TESTOPS_DATA`` set to that temp directory
    and every inherited ``TESTOPS_*`` variable stripped, so nothing in the parent's environment
    can redirect it; ``PYTHONHOME`` and its relatives are stripped as well, because they stop the
    child before the harness can say anything useful;
  * the child binds port **0** and reports the port it was given, so the suite talks to the socket
    it opened rather than to a port it guessed (on Windows a second binder on a chosen port can
    silently receive the traffic - the reason this is not "pick a free port, then connect");
  * :func:`require_disposable_store` refuses any store that is not under the system temp
    directory, and :func:`start_contract_server` calls it before it launches anything;
  * the temp root itself is **discovered without environment variables** (the OS known folder on
    Windows, the platform defaults elsewhere) and captured once at import, because
    ``tempfile.gettempdir()`` honours ``TMPDIR``/``TEMP``/``TMP`` - TESTOPS-58.

The claim this module makes is deliberately narrower than TESTOPS-53's first draft. What is
guaranteed: the suite cannot be pointed at a **persistent evidence store** - the store path is
handed to the child by the fixture, never read from the environment, and a temp variable that
resolves into the repository, the user's home or any checkout's ``data/`` makes the suite skip.
What is *not* guaranteed: the choice of junk directory. A ``TMPDIR`` pointing at some other
persistent directory (say ``D:/scratch``) still moves the store there, because the operating
system has no temp directory besides the one it names; the worst outcome is a disposable store
left behind in a directory nobody treats as evidence.

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


# The variables ``tempfile.gettempdir()`` consults. They are checked for *poisoning*, not trusted
# to name the root (TESTOPS-58): the T53 review moved the root with TMPDIR and the suite built its
# store inside the Projects directory.
TEMP_VARIABLES = ("TMPDIR", "TEMP", "TMP")

# Variables that redirect or break the *interpreter* in the child. PYTHONHOME makes the child die
# before it can bind ("No module named 'encodings'"), which reads like a harness failure; the T53
# review found it is not stripped. PYTHONPATH is dropped here and set again explicitly below.
_LAUNCHER_ENV_DROP = (
    "PYTHONHOME",
    "PYTHONPATH",
    "PYTHONSTARTUP",
    "PYTHONUSERBASE",
    "PYTHONOPTIMIZE",
    "PYTHONEXECUTABLE",
)


def _windows_temp_root() -> Path:
    """``%LocalAppData%\\Temp`` via the shell known folder, which ignores TMPDIR/TEMP/TMP."""
    import ctypes
    import struct
    import uuid

    class _GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
                    ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_ubyte * 8)]

    guid = _GUID()
    known = uuid.UUID("{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}")  # FOLDERID_LocalAppData
    guid.Data1, guid.Data2, guid.Data3 = struct.unpack("<IHH", known.bytes_le[:8])
    ctypes.memmove(guid.Data4, known.bytes[8:], 8)

    address = ctypes.c_wchar_p()
    result = ctypes.windll.shell32.SHGetKnownFolderPath(
        ctypes.byref(guid), 0, None, ctypes.byref(address))
    if result != 0 or not address.value:
        raise OSError(0xFFFF & result, "SHGetKnownFolderPath(LocalAppData) failed")
    try:
        return Path(address.value) / "Temp"
    finally:
        ctypes.windll.ole32.CoTaskMemFree(address)


def _posix_temp_root() -> Path:
    """The platform default, asked with TMPDIR/TEMP/TMP removed from the environment."""
    saved = {name: os.environ.pop(name) for name in TEMP_VARIABLES if name in os.environ}
    previous = tempfile.tempdir
    tempfile.tempdir = None
    try:
        return Path(tempfile.gettempdir())
    finally:
        os.environ.update(saved)
        tempfile.tempdir = previous


def _discover_temp_root() -> tuple["Path | None", "str | None"]:
    try:
        candidate = _windows_temp_root() if os.name == "nt" else _posix_temp_root()
    except Exception as exc:  # noqa: BLE001 - any failure means "cannot name a temp root"
        return None, ("the system temp directory could not be discovered without environment "
                      "variables: %r" % (exc,))
    if not candidate.is_absolute():
        return None, "the system temp directory resolved to a relative path: %r" % (candidate,)
    return candidate.resolve(), None


# Discovered once, at import, before pytest or anything else has a chance to move it. A test pins
# that moving TMPDIR afterwards leaves this value alone.
TRUSTED_TEMP_ROOT, TEMP_ROOT_ERROR = _discover_temp_root()


def _checkout_data_dirs() -> list[Path]:
    """``data/`` of this checkout and of any sibling checkout of the same repository."""
    dirs = [ROOT / "data"]
    try:
        siblings = sorted(ROOT.parent.glob("testops*"))
    except OSError:
        siblings = []
    for sibling in siblings:
        if sibling.resolve() != ROOT.resolve() and (sibling / "data").is_dir():
            dirs.append(sibling / "data")
    return [path.resolve() for path in dirs]


def _forbidden_reason(path: Path) -> "str | None":
    """Why ``path`` is not a disposable location, or ``None`` when it is one."""
    root = ROOT.resolve()
    if path == root or root in path.parents:
        return "the repository under test (%s)" % root
    for data in _checkout_data_dirs():
        if path == data or data in path.parents:
            return "a checkout's data/ directory (%s)" % data
    home = Path.home().resolve()
    if TRUSTED_TEMP_ROOT is not None and (
            path == TRUSTED_TEMP_ROOT or TRUSTED_TEMP_ROOT in path.parents):
        return None  # the OS's own temp directory lives under home on Windows; it is allowed
    if path == home or home in path.parents:
        return "the user's home directory (%s)" % home
    return None


def temp_root_problem(environ=None) -> "str | None":
    """The refusal message when a temp variable points at a persistent location, else ``None``.

    AC1 of TESTOPS-58. ``environ`` exists so a test can prove the decision for a mapping without
    mutating the process environment; the suite calls it with the real environment.
    """
    env = os.environ if environ is None else environ
    for name in TEMP_VARIABLES:
        raw = env.get(name)
        if not raw:
            continue
        try:
            resolved = Path(raw).expanduser().resolve()
        except OSError:
            continue
        reason = _forbidden_reason(resolved)
        if reason:
            return ("%s=%r resolves to %s, inside %s. The contract suite builds a disposable store "
                    "and refuses to build one there." % (name, raw, resolved, reason))
    return None


# Captured once at import, so the fixture can skip before pytest creates a temp directory.
TEMP_ROOT_PROBLEM = temp_root_problem()


def temp_root() -> Path:
    """The temp root the suite trusts: discovered from the OS, never from a variable."""
    if TRUSTED_TEMP_ROOT is None:
        raise StoreNotDisposable(TEMP_ROOT_ERROR or "the system temp directory is unknown")
    return TRUSTED_TEMP_ROOT


def under_temp(path) -> bool:
    """True when ``path`` resolves inside the trusted temp root."""
    root = temp_root()
    target = Path(path).resolve()
    return target == root or root in target.parents


def require_disposable_store(data_dir) -> Path:
    """Refuse a store that is not under the trusted temp directory.

    This is the fixture's own gate, not a warning: a disposable store is one the test run may
    create and delete, and only the system temp directory is guaranteed to be that. A temp
    variable that has been moved into the repository, the home directory or a checkout's
    ``data/`` is refused before the path check, and the refusal names the variable and the path.
    """
    problem = temp_root_problem()
    if problem:
        raise StoreNotDisposable("refusing to start the contract suite: %s" % problem)
    target = Path(data_dir).resolve()
    if not under_temp(target):
        raise StoreNotDisposable(
            "refusing to point the contract suite at %s: it is not under the trusted temp "
            "directory (%s), which this run discovered from the operating system rather than "
            "from an environment variable." % (target, temp_root()))
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
    # persistent store must not be able to reach the child at all. PYTHONHOME and its relatives
    # are dropped too (TESTOPS-58 AC4): PYTHONHOME makes the child die before it can bind, which
    # looks like a harness failure rather than the environment error it is.
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("TESTOPS_") and key not in _LAUNCHER_ENV_DROP}
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
