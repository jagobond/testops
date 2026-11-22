"""Support code for the suite: a content snapshot of the repository, and the store guard."""
from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Written by Python's import machinery and by pytest itself, not by a test.
_IGNORED_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "build", "dist"}
_IGNORED_SUFFIXES = (".pyc",)


def _digest(path: Path) -> tuple[int, str]:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return path.stat().st_size, h.hexdigest()


def repository_snapshot(root: Path = ROOT) -> dict[str, tuple[int, str]]:
    """Digest every tracked-by-content file in the repo, ignoring interpreter caches.

    Comparing two snapshots detects an added, removed or modified file anywhere in the working tree,
    which is what AC10 needs: a test may only write under pytest's ``tmp_path``.
    """
    out: dict[str, tuple[int, str]] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _IGNORED_DIRS)
        for name in sorted(filenames):
            if name.endswith(_IGNORED_SUFFIXES):
                continue
            path = Path(dirpath) / name
            out[path.relative_to(root).as_posix()] = _digest(path)
    return out


def snapshot_difference(before: dict[str, tuple[int, str]],
                        after: dict[str, tuple[int, str]]) -> dict[str, list[str]]:
    return {
        "added": sorted(set(after) - set(before)),
        "removed": sorted(set(before) - set(after)),
        "changed": sorted(k for k in set(before) & set(after) if before[k] != after[k]),
    }


# ---------------------------------------------------------------- the store guard
#
# TESTOPS-35. The suite has always been *meant* to write nothing but ``tmp_path``; before this
# guard, nothing enforced it at the connection. A review session's fixture reached the live store
# because a script could open ``data/testops.db`` and find a writable database. The repository
# digest below catches a file that changed by the end of the run, which is too late and too coarse:
# a test that opens the real store and only reads from it, or one whose write happens to be
# reverted, is invisible to a digest.
#
# So the guard refuses the open itself. The real store may be consulted read-only - two corpus
# tests do exactly that against a pinned snapshot - and a read-only open is declared by its URI
# (``file:...?mode=ro``), which SQLite enforces rather than this module. Anything else that
# resolves under a checkout's ``data/`` raises before SQLite sees the path.

class StoreWriteRefused(RuntimeError):
    """Raised when a test tries to open a product store outside a declared read-only mode."""


def protected_store_dirs() -> tuple[Path, ...]:
    """The ``data/`` directories a test must not open for writing.

    Two, because the suite is often run from a worktree: this checkout's (``TESTOPS_HOME``/data)
    and the main checkout's beside it. A worktree's own ``data/`` does not exist, which is exactly
    why protecting only it would have let this defect through.
    """
    from testops import config

    candidates = [ROOT / "data", ROOT.parent / "testops" / "data"]
    out: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in out:
            out.append(resolved)
    return tuple(out)


def real_store_path() -> Path:
    """The live store this checkout would write to, whether or not the file exists."""
    from testops import config

    return Path(config.settings().db_path).resolve()


def _is_protected(path: Path) -> bool:
    resolved = path.resolve()
    return any(resolved == root or root in resolved.parents for root in protected_store_dirs())


def _uri_target(database: str) -> tuple[Path, bool]:
    """The file a ``file:`` URI names, and whether the URI declares a read-only open."""
    text = database[len("file:"):] if database.startswith("file:") else database
    target, _, query = text.partition("?")
    read_only = any(part in ("mode=ro", "immutable=1") for part in query.split("&"))
    return Path(target), read_only


def guarded_connect(database, *args, **kwargs):
    """``sqlite3.connect`` that refuses a writable open of a product store.

    ``:memory:`` is allowed - it is not a file and cannot outlive the test. A ``file:`` URI with
    ``mode=ro`` or ``immutable=1`` is the declared read-only path, and SQLite enforces it.
    """
    if isinstance(database, bytes):
        database = database.decode("utf-8", "replace")
    if isinstance(database, (str, Path)):
        text = os.fspath(database)
        if text != ":memory:":
            target, read_only = _uri_target(text)
            if _is_protected(target) and not read_only:
                raise StoreWriteRefused(
                    f"a test tried to open the product store for writing: {target}\n"
                    "Copy it into pytest's tmp_path (shutil.copyfile) and write to the copy, or "
                    "open the original read-only with 'file:<path>?mode=ro', uri=True. A fixture "
                    "belongs in a copy; the live store is the Product Owner's evidence.")
    return _original_sqlite_connect(database, *args, **kwargs)


_original_sqlite_connect = sqlite3.connect


_original_db_connect = None


def guarded_db_connect(path=None):
    """``db.connect`` that refuses the real store before it creates its directory.

    ``db.connect`` calls ``p.parent.mkdir(parents=True, exist_ok=True)`` before SQLite is asked to
    open anything, so the sqlite-level guard alone would still let a test create ``data/``.
    """
    from testops import config

    target = Path(path) if path is not None else Path(config.settings().db_path)
    if _is_protected(target):
        raise StoreWriteRefused(
            f"a test tried to open the product store for writing: {target}\n"
            "Use db.connect(tmp_path / 'test.db') instead; the suite runs against a temporary "
            "store.")
    return _original_db_connect(path)  # type: ignore[misc]  # set by install_store_guard


def install_store_guard():
    """Patch both sqlite3 and ``testops.store.db`` for the session; returns the undo callable."""
    global _original_db_connect
    import pytest

    from testops.store import db as store_db

    if _original_db_connect is None:
        _original_db_connect = store_db.connect
    mp = pytest.MonkeyPatch()
    mp.setattr(sqlite3, "connect", guarded_connect)
    mp.setattr(store_db, "connect", guarded_db_connect)
    return mp
