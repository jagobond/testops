"""AC5: ``sources_missing`` is an explicit list, and [] stays distinguishable from NULL on read.

"We consulted everything" and "we recorded nothing" are different claims, and only one of them is
true when an analysis ran without Jira. A store that spells both ``[]`` - or that folds ``[]`` into
NULL because empty is falsy - turns absence into a result, which is the failure AGENTS.md names
first.
"""
from __future__ import annotations

from support_fixtures import add_v2_claim, seed_run
from testops import queries
from testops.store import db


def _write(tmp_path, sources_missing):
    path = tmp_path / "blind-spots.db"
    conn = db.connect(path)
    try:
        run_id = seed_run(conn)
        claim_id = add_v2_claim(conn, run_id, sources_missing=sources_missing)
        conn.commit()
    finally:
        conn.close()
    return path, claim_id


def test_an_empty_list_is_stored_as_an_empty_list(tmp_path):
    path, claim_id = _write(tmp_path, [])
    conn = db.connect(path)
    try:
        stored = conn.execute("SELECT sources_missing FROM claim WHERE id = ?", (claim_id,)).fetchone()[0]
    finally:
        conn.close()
    assert stored == "[]", f"an empty list must be stored as [] not {stored!r}"


def test_null_is_stored_as_null(tmp_path):
    path, claim_id = _write(tmp_path, None)
    conn = db.connect(path)
    try:
        stored = conn.execute("SELECT sources_missing FROM claim WHERE id = ?", (claim_id,)).fetchone()[0]
    finally:
        conn.close()
    assert stored is None, f"an unrecorded list must stay NULL, found {stored!r}"


def test_empty_list_and_null_read_back_differently(tmp_path):
    """One file, two claims, one read model: [] and None must not converge."""
    path = tmp_path / "both.db"
    conn = db.connect(path)
    try:
        run_id = seed_run(conn)
        everything_consulted = add_v2_claim(conn, run_id, sources_missing=[])
        nothing_recorded = add_v2_claim(conn, run_id, sources_missing=None)
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
    assert consulted["sources_missing"] is not recorded["sources_missing"]


def test_a_named_source_list_round_trips_in_order(tmp_path):
    missing = ["jira", "ado"]
    path, claim_id = _write(tmp_path, missing)
    conn = db.connect(path)
    try:
        claim = queries.claim_read(conn, claim_id)
    finally:
        conn.close()
    assert claim["sources_missing"] == missing


def test_unparseable_json_fails_loudly_instead_of_looking_like_an_empty_list(tmp_path):
    path, claim_id = _write(tmp_path, [])
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
