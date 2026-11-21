"""AC4: schema.sql applied to a fresh temporary database creates every table the pipeline uses."""
from __future__ import annotations

import sqlite3

from testops.store import db

REQUIRED_TABLES = {
    "snapshot",
    "artefact",
    "observation",
    "run",
    "claim",
    "inference",
    "case_",
    "finding",
    "suppression",
    "case_state",
}


def _table_names(conn) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def test_schema_sql_creates_the_tables_the_pipeline_depends_on(tmp_path):
    schema = db.SCHEMA
    assert schema.is_file(), f"schema.sql not found at {schema}"

    conn = sqlite3.connect(tmp_path / "schema.db")
    try:
        conn.executescript(schema.read_text(encoding="utf-8"))
        names = _table_names(conn)
    finally:
        conn.close()

    assert REQUIRED_TABLES <= names, f"missing tables: {sorted(REQUIRED_TABLES - names)}"


def test_connect_applies_the_schema_to_a_fresh_database(tmp_path):
    conn = db.connect(tmp_path / "store.db")
    try:
        names = _table_names(conn)
    finally:
        conn.close()
    assert REQUIRED_TABLES <= names, f"missing tables: {sorted(REQUIRED_TABLES - names)}"