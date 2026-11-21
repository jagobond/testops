"""AC2: applying the schema to an empty database twice leaves an identical structure and raises nothing.

The dangerous shape of this is a migration that runs, records a version, and then runs again on the
next open because it recorded nothing or recorded the wrong place. So the assertion is on the whole
sqlite_master, not just on "it did not raise": a second pass that added an index or re-created a
table with a different definition would be a failure here.
"""
from __future__ import annotations

import sqlite3

from testops.store import db, migrate


def _structure(conn) -> list[tuple]:
    return [tuple(row) for row in conn.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
        " ORDER BY type, name")]


def test_schema_sql_applied_twice_is_unchanged(tmp_path):
    path = tmp_path / "raw.db"
    schema = db.SCHEMA.read_text(encoding="utf-8")

    conn = sqlite3.connect(path)
    try:
        conn.executescript(schema)
        first = _structure(conn)
        conn.executescript(schema)  # must not raise, must not change anything
        second = _structure(conn)
    finally:
        conn.close()

    assert first == second


def test_connecting_twice_leaves_an_identical_structure(tmp_path):
    path = tmp_path / "store.db"

    first_conn = db.connect(path)
    try:
        first = _structure(first_conn)
        first_version = migrate.stored_version(first_conn)
    finally:
        first_conn.close()

    second_conn = db.connect(path)
    try:
        second = _structure(second_conn)
        second_version = migrate.stored_version(second_conn)
    finally:
        second_conn.close()

    assert first == second
    assert first_version == second_version == migrate.CURRENT_VERSION
