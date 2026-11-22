"""TESTOPS-17 AC1: ``sources_missing`` is only a fact when an assessment was recorded with it.

"We consulted everything" and "we recorded nothing" are different claims, and only one of them is
true when an analysis ran without Jira. The store keeps NULL ("not assessed") and ``[]`` ("assessed,
nothing was missing") apart, and it keeps them apart *twice*: in the value, and in the
``sources_assessed`` flag that says whether the value was ever produced by looking. A store that
spells both ``[]`` - or that folds ``[]`` into NULL because empty is falsy - turns absence into a
result, which is the failure AGENTS.md names first.
"""
from __future__ import annotations

from support_fixtures import add_v2_claim, seed_run
from testops import queries
from testops.store import db


def _write(tmp_path, *, assessed, sources_missing=None):
    path = tmp_path / "blind-spots.db"
    conn = db.connect(path)
    try:
        run_id = seed_run(conn)
        claim_id = add_v2_claim(conn, run_id, sources_assessed=assessed,
                                sources_missing=sources_missing)
        conn.commit()
    finally:
        conn.close()
    return path, claim_id


def test_an_assessed_empty_list_is_stored_as_an_empty_list(tmp_path):
    path, claim_id = _write(tmp_path, assessed=True, sources_missing=[])
    conn = db.connect(path)
    try:
        stored = conn.execute("SELECT sources_missing, sources_assessed FROM claim WHERE id = ?",
                              (claim_id,)).fetchone()
    finally:
        conn.close()
    assert stored["sources_missing"] == "[]", f"an empty list must be stored as [] not {stored[0]!r}"
    assert stored["sources_assessed"] == 1


def test_a_claim_with_no_assessment_is_stored_as_null(tmp_path):
    path, claim_id = _write(tmp_path, assessed=False)
    conn = db.connect(path)
    try:
        stored = conn.execute("SELECT sources_missing, sources_assessed FROM claim WHERE id = ?",
                              (claim_id,)).fetchone()
    finally:
        conn.close()
    assert stored["sources_missing"] is None, f"an unassessed list must stay NULL, found {stored[0]!r}"
    assert stored["sources_assessed"] == 0


def test_the_two_states_read_back_differently(tmp_path):
    """One file, two claims, one read model: assessed-nothing-missing and unassessed must not converge."""
    path = tmp_path / "both.db"
    conn = db.connect(path)
    try:
        run_id = seed_run(conn)
        everything_consulted = add_v2_claim(conn, run_id, sources_assessed=True,
                                            sources_missing=[])
        nothing_recorded = add_v2_claim(conn, run_id, sources_assessed=False)
        conn.commit()
    finally:
        conn.close()

    conn = db.connect(path)
    try:
        consulted = queries.claim_read(conn, everything_consulted)
        recorded = queries.claim_read(conn, nothing_recorded)
    finally:
        conn.close()

    assert consulted["sources_missing"] == []
    assert isinstance(consulted["sources_missing"], list)
    assert recorded["sources_missing"] is None
    assert consulted["sources_state"] == queries.SOURCES_NONE_MISSING
    assert recorded["sources_state"] == queries.SOURCES_NOT_ASSESSED
    assert consulted["sources_missing"] is not recorded["sources_missing"]


def test_a_named_source_list_round_trips_in_order(tmp_path):
    missing = ["jira", "ado"]
    path, claim_id = _write(tmp_path, assessed=True, sources_missing=missing)
    conn = db.connect(path)
    try:
        claim = queries.claim_read(conn, claim_id)
    finally:
        conn.close()
    assert claim["sources_missing"] == missing
    assert claim["sources_assessed"] is True
    assert claim["sources_state"] == queries.SOURCES_SOME_MISSING


def test_a_list_passed_without_an_assessment_is_not_stored(tmp_path):
    """The caller supplies a list but never says a registry was consulted: it is a default, not a fact."""
    path, claim_id = _write(tmp_path, assessed=False, sources_missing=[])
    conn = db.connect(path)
    try:
        claim = queries.claim_read(conn, claim_id)
    finally:
        conn.close()
    assert claim["sources_assessed"] is False
    assert claim["sources_missing"] is None
    assert claim["sources_state"] == queries.SOURCES_NOT_ASSESSED


def test_unparseable_json_fails_loudly_instead_of_looking_like_an_empty_list(tmp_path):
    path, claim_id = _write(tmp_path, assessed=True, sources_missing=[])
    conn = db.connect(path)
    try:
        conn.execute("UPDATE claim SET sources_missing = 'not json' WHERE id = ?", (claim_id,))
        conn.commit()
        try:
            queries.claim_read(conn, claim_id)
        except ValueError as exc:
            assert "sources_missing" in str(exc)
        else:
            raise AssertionError("a corrupt blind-spot list was returned as if it were readable")
    finally:
        conn.close()
