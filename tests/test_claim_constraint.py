"""AC4: the store refuses a v2 claim with no assertion_path, assertion_line or assertion_commit.

The refusal has to come from the database. A check inside ``db.add_claim`` would be a rule that the
next writer - a script, a migration, a person with a sqlite prompt - does not have to obey, and the
claim model would then contain rows nobody can check while every test still passed. So the bypass
attempt below writes SQL directly and is refused by the same CHECK constraint.

Each case is paired with a positive control: a complete claim must be accepted, otherwise a
constraint that refuses everything would satisfy the refusals and prove nothing.
"""
from __future__ import annotations

import sqlite3

import pytest

from support_fixtures import PROVENANCE, add_v2_claim, seed_run
from testops.store import db

INSERT_SQL = (
    "INSERT INTO claim (run_id, analyser, analyser_version, subject_ref, statement, verdict,"
    " confidence, support, schema_version, assertion_text, assertion_path, assertion_line,"
    " assertion_commit) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"
)


def _conn(tmp_path, name="constraint.db"):
    conn = db.connect(tmp_path / name)
    seed_run(conn)
    return conn


@pytest.mark.parametrize("missing", ["assertion_path", "assertion_line", "assertion_commit"])
def test_add_claim_refuses_a_v2_claim_missing_one_coordinate(tmp_path, missing):
    conn = _conn(tmp_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            add_v2_claim(conn, "run-schema", **{missing: None})
        assert conn.execute("SELECT COUNT(*) FROM claim").fetchone()[0] == 0
    finally:
        conn.close()


@pytest.mark.parametrize("blank", ["assertion_path", "assertion_commit"])
def test_add_claim_refuses_a_v2_claim_whose_coordinate_is_a_blank_string(tmp_path, blank):
    """'' is not a path and not a commit. A constraint that only tested IS NOT NULL would pass this."""
    conn = _conn(tmp_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            add_v2_claim(conn, "run-schema", **{blank: "   "})
    finally:
        conn.close()


def test_the_refusal_comes_from_the_database_not_from_add_claim(tmp_path):
    """Write the INSERT by hand, skipping the store's Python entirely."""
    conn = _conn(tmp_path)
    try:
        with pytest.raises(sqlite3.IntegrityError) as refused:
            conn.execute(INSERT_SQL, ("run-schema", "level_fitness", "0.6.0",
                                      "scenario:a.feature#hand-written", "heading", "gap", 0.1, "[]",
                                      2, "Given it is written by hand", "features/a.feature", None, None))
        assert "claim_v2_requires_provenance" in str(refused.value)
        assert conn.execute("SELECT COUNT(*) FROM claim").fetchone()[0] == 0
    finally:
        conn.close()


def test_a_complete_v2_claim_is_accepted(tmp_path):
    """The positive control: without this, a CHECK that always aborted would pass every test above."""
    conn = _conn(tmp_path)
    try:
        claim_id = add_v2_claim(conn)
        row = conn.execute("SELECT * FROM claim WHERE id = ?", (claim_id,)).fetchone()
        assert row["schema_version"] == 2
        assert row["assertion_path"] == PROVENANCE["assertion_path"]
        assert row["assertion_line"] == PROVENANCE["assertion_line"]
        assert row["assertion_commit"] == PROVENANCE["assertion_commit"]
    finally:
        conn.close()


def test_a_v1_claim_needs_no_coordinates(tmp_path):
    """The other control: the constraint refuses v2 claims without coordinates, not history."""
    conn = _conn(tmp_path)
    try:
        claim_id = db.add_claim(conn, "run-schema", "level_fitness", "0.5.0",
                                "scenario:features/panel_api.feature#legacy", "old heading",
                                "distinct", 0.0, [])
        row = conn.execute("SELECT * FROM claim WHERE id = ?", (claim_id,)).fetchone()
        assert row["schema_version"] == 1
        assert row["assertion_path"] is None
    finally:
        conn.close()


def test_an_unknown_schema_version_is_refused(tmp_path):
    """A version the CHECK does not know is neither v1 nor v2; it cannot be read, so it is not stored."""
    conn = _conn(tmp_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(INSERT_SQL, ("run-schema", "level_fitness", "9.0.0",
                                      "scenario:a.feature#v3", "heading", "gap", 0.1, "[]",
                                      3, "Given it", "features/a.feature", 3, "c" * 40))
    finally:
        conn.close()
