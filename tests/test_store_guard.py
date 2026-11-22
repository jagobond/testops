"""TESTOPS-35 AC3: the suite cannot open a product store for writing.

The live store is the Product Owner's evidence. A review session wrote a fixture into it because
nothing stood between a script and ``data/testops.db``; these tests stand there now.

The guard is installed for the whole session by ``conftest.store_guard``. What is checked here is
the guard's own behaviour: writable opens fail, the read-only declaration works and is enforced by
SQLite, and a store under ``tmp_path`` is untouched by any of it.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from support import (ROOT, StoreWriteRefused, protected_store_dirs, real_store_path)
from testops.store import db

MAIN_STORE = ROOT.parent / "testops" / "data" / "testops.db"


def test_writable_open_of_the_live_store_is_refused():
    """The exact call that would have written the fixture."""
    target = real_store_path()
    with pytest.raises(StoreWriteRefused) as caught:
        sqlite3.connect(target)
    assert "read-only" in str(caught.value)
    # A path under the protected directory that did not exist before the call still does not.
    absent = Path(protected_store_dirs()[0]) / "must-not-be-created.db"
    with pytest.raises(StoreWriteRefused):
        sqlite3.connect(absent)
    assert not absent.exists(), "the refused open created a store in data/"


def test_db_connect_with_no_path_is_refused():
    """``db.connect()`` with nothing is the live store; it must not even create ``data/``."""
    with pytest.raises(StoreWriteRefused):
        db.connect()


def test_the_main_checkout_store_is_protected_from_a_worktree():
    """A worktree has no ``data/`` of its own, so this is the directory that matters in CI here."""
    main_data = (ROOT.parent / "testops" / "data").resolve()
    assert main_data in protected_store_dirs()
    if MAIN_STORE.exists():
        with pytest.raises(StoreWriteRefused):
            sqlite3.connect(MAIN_STORE)


def test_a_temporary_store_is_allowed(tmp_path):
    """The whole suite works this way: a store under pytest's own directory."""
    conn = db.connect(tmp_path / "scratch.db")
    try:
        assert conn.execute("SELECT COUNT(*) FROM case_").fetchone()[0] == 0
    finally:
        conn.close()


def test_declared_read_only_open_is_allowed_and_sqlite_enforces_it(tmp_path):
    """The declared path: ``file:...?mode=ro``. The guard lets it through; SQLite refuses writes."""
    if not MAIN_STORE.exists():
        pytest.skip("the main checkout has no store to open read-only")
    conn = sqlite3.connect(f"file:{MAIN_STORE.as_posix()}?mode=ro", uri=True)
    try:
        assert conn.execute("SELECT COUNT(*) FROM case_").fetchone()[0] > 0
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("CREATE TABLE must_not_exist (x INTEGER)")
    finally:
        conn.close()


def test_a_uri_that_is_not_read_only_is_refused():
    """``file:`` alone is not a declaration: the mode is what the guard reads."""
    target = real_store_path()
    with pytest.raises(StoreWriteRefused):
        sqlite3.connect(f"file:{target.as_posix()}", uri=True)
