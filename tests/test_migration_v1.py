"""AC3: a database created at v1 still opens, and its claims read back as v1 with empty provenance.

Empty means absent. A v1 claim did not know where its assertion lived - that is a fact about the
claim, and the store must say so with NULL rather than something that reads like a value ("" or 0 or
a path later reconstructed from today's repository).

The rows are also asserted unchanged, because the temptation in a migration is to "fix up" the old
claims while the table is being rebuilt. They are evidence of what was claimed, not drafts.
"""
from __future__ import annotations

import sqlite3

import pytest

import v1_store
from testops import queries
from testops.store import db


def test_v1_store_opens_and_its_claim_reads_back_as_v1(tmp_path):
    path = tmp_path / "v1.db"
    v1_store.build(path)

    conn = db.connect(path)  # no exception is half the criterion
    try:
        row = conn.execute("SELECT * FROM claim WHERE id = ?", (v1_store.CLAIM_ID,)).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["schema_version"] == 1
    for field in queries.PROVENANCE_FIELDS:
        assert row[field] is None, f"a v1 claim must not gain a {field}"
    assert row["sources_missing"] is None
    assert row["span"] is None

    # Nothing about the claim itself was rewritten.
    assert row["id"] == v1_store.CLAIM_ID
    assert row["subject_ref"] == v1_store.SUBJECT
    assert row["statement"] == v1_store.STATEMENT
    assert row["verdict"] == v1_store.VERDICT
    assert row["confidence"] == v1_store.CONFIDENCE
    assert row["support"] == "[]"


def test_a_v1_claim_renders_through_the_read_model_without_invented_values(tmp_path):
    path = tmp_path / "v1-read.db"
    v1_store.build(path)

    conn = db.connect(path)
    try:
        claim = queries.claim_read(conn, v1_store.CLAIM_ID)
    finally:
        conn.close()

    assert claim["schema_version"] == 1
    assert claim["statement"] == v1_store.STATEMENT
    # Keys are present - a page can render and say "not recorded" - but every value is absent.
    assert set(claim["provenance"]) == set(queries.PROVENANCE_FIELDS)
    assert all(value is None for value in claim["provenance"].values()), claim["provenance"]
    assert claim["sources_missing"] is None


def test_migration_keeps_the_relationships_around_the_claim(tmp_path):
    path = tmp_path / "v1-links.db"
    v1_store.build(path)

    conn = db.connect(path)
    try:
        inference = conn.execute(
            "SELECT i.output FROM inference i JOIN claim c ON c.id = i.claim_id WHERE c.id = ?",
            (v1_store.CLAIM_ID,)).fetchone()
        finding = conn.execute("SELECT claim_ids FROM finding WHERE case_id = ?",
                               (v1_store.CASE,)).fetchone()
        broken = conn.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        conn.close()

    assert inference is not None, "the rebuilt claim table lost its inference rows"
    assert finding is not None
    assert finding["claim_ids"] == "[1]"
    assert broken == []


def test_the_migrated_claim_table_is_shaped_like_a_new_one(tmp_path):
    migrated_path = tmp_path / "migrated.db"
    v1_store.build(migrated_path)

    fresh_path = tmp_path / "fresh.db"

    def definition(path):
        conn = sqlite3.connect(path)
        try:
            columns = [tuple(row[1:]) for row in conn.execute("PRAGMA table_info(claim)")]
            sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'claim'").fetchone()[0]
        finally:
            conn.close()
        return columns, sql

    migrated_conn = db.connect(migrated_path)
    migrated_conn.close()
    fresh_conn = db.connect(fresh_path)
    fresh_conn.close()

    migrated_columns, migrated_sql = definition(migrated_path)
    fresh_columns, fresh_sql = definition(fresh_path)

    assert migrated_columns == fresh_columns
    # ALTER TABLE ... RENAME quotes the table name in the stored SQL; the shape is the assertion.
    assert migrated_sql.replace('"claim"', "claim") == fresh_sql
    assert "claim_v2_requires_provenance" in migrated_sql


def test_the_migrated_store_refuses_an_unprovenanced_v2_claim(tmp_path):
    """The rebuild is the only place the constraint could be lost. Check it is live afterwards."""
    path = tmp_path / "v1-then-v2.db"
    v1_store.build(path)

    conn = db.connect(path)
    try:
        # A complete v2 claim is accepted, and takes an id after the v1 row: the copied ids kept the
        # AUTOINCREMENT sequence honest instead of resetting it under the surviving rows.
        new_id = db.add_claim(conn, v1_store.RUN, "level_fitness", "0.6.0",
                              "scenario:features/panel_api.feature#new", "heading", "gap", 0.1, [],
                              schema_version=2,
                              assertion_text="Then the panel shows the total",
                              assertion_path="features/panel_api.feature",
                              assertion_line=31, assertion_commit="b" * 40)
        assert new_id > v1_store.CLAIM_ID
    finally:
        conn.close()

    conn = db.connect(path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            db.add_claim(conn, v1_store.RUN, "level_fitness", "0.6.0",
                         "scenario:features/panel_api.feature#no-coords", "heading", "gap", 0.1, [],
                         schema_version=2, assertion_text="Given something")
    finally:
        conn.close()
