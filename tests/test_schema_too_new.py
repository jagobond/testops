"""AC8: migration is forward only. A store written by a newer build is refused, loudly.

The failure this prevents is the quiet one: a v2 build opening a v3 store, reading what it recognises
and writing v2 rows into it. The newer store then contains rows from a build that did not understand
it, and the next correct build has to guess which is which.

So: a store above ``migrate.CURRENT_VERSION`` must not open, must not be modified, and must not have
a single row written to it. The positive control matters as much - a ``connect()`` that always raised
would satisfy the refusal tests.
"""
from __future__ import annotations

import hashlib
import sqlite3

import pytest

from support_fixtures import add_v2_claim, seed_run
from testops.store import db, migrate


def _digest(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _store_written_by_a_newer_build(tmp_path, version: int = migrate.CURRENT_VERSION + 1):
    """A v2-shaped store that claims to be from the future, as a newer writer would leave it."""
    path = tmp_path / "future.db"
    conn = db.connect(path)
    try:
        run_id = seed_run(conn)
        add_v2_claim(conn, run_id)
        conn.commit()
        conn.execute("UPDATE schema_meta SET value = ? WHERE key = 'schema_version'", (str(version),))
        conn.commit()
    finally:
        conn.close()
    return path, version


def test_a_store_from_a_newer_build_is_refused(tmp_path):
    path, version = _store_written_by_a_newer_build(tmp_path)

    with pytest.raises(db.SchemaTooNewError) as refused:
        db.connect(path)

    # Loud, and it says what it found: the operator can tell "too new" from "corrupt".
    assert str(version) in str(refused.value)
    assert str(migrate.CURRENT_VERSION) in str(refused.value)


def test_the_refusal_happens_before_anything_is_written(tmp_path):
    path, version = _store_written_by_a_newer_build(tmp_path)
    before = _digest(path)

    with pytest.raises(db.SchemaTooNewError):
        db.connect(path)

    assert _digest(path) == before, "the store was modified by a build that could not read it"
    assert not (tmp_path / "future.db-journal").exists()


def test_the_newer_store_keeps_its_version_and_makes_no_room_for_v2_rows(tmp_path):
    path, version = _store_written_by_a_newer_build(tmp_path)

    with pytest.raises(db.SchemaTooNewError):
        db.connect(path)

    conn = sqlite3.connect(path)  # the raw file, bypassing the refused open
    try:
        recorded = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()[0]
        claims = conn.execute("SELECT COUNT(*) FROM claim").fetchone()[0]
    finally:
        conn.close()

    assert recorded == str(version), "the version was down-migrated"
    assert claims == 1, "a v2 row was appended to a store this build cannot read"


def test_a_store_at_the_current_version_opens(tmp_path):
    """Positive control: without this, a connect() that always raised would pass the tests above."""
    path = tmp_path / "current.db"
    conn = db.connect(path)
    try:
        assert migrate.stored_version(conn) == migrate.CURRENT_VERSION
    finally:
        conn.close()


def test_a_v1_store_is_readable_rather_than_refused(tmp_path):
    """The other side of forward-only: older is fine, newer is not."""
    import v1_store

    path = tmp_path / "old.db"
    v1_store.build(path)
    conn = db.connect(path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM claim").fetchone()[0] == 1
        assert migrate.stored_version(conn) == migrate.CURRENT_VERSION
    finally:
        conn.close()


def test_a_version_that_cannot_be_read_is_refused_rather_than_guessed(tmp_path):
    path = tmp_path / "garbled.db"
    conn = db.connect(path)
    try:
        conn.execute("UPDATE schema_meta SET value = 'two' WHERE key = 'schema_version'")
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(db.SchemaCorruptError):
        db.connect(path)
