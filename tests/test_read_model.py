"""AC6: one call returns statement, provenance and blind spots together.

A page cannot render a claim without its coordinates and its blind spots, so the read model must not
be able to return a claim without them. ``queries.claim_view`` is the only constructor of that
model, and ``finding_rows`` - the call the case page makes - goes through it.

The third test is the one that would fail if the provenance SELECT were dropped: it compares the
read model field by field against the stored row read separately.
"""
from __future__ import annotations

from support_fixtures import PROVENANCE, add_v2_claim, seed_run
from testops import queries
from testops.store import db

CASE = "case-read-model"


def _seed_case(conn, run_id: str) -> tuple[int, str]:
    conn.execute(
        "INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at, summary)"
        " VALUES (?,?,?,?,?,?,?)",
        (CASE, run_id, "fixture", "level_fitness", "snap-schema", "2020-01-01T00:00:00+00:00", "{}"),
    )
    return 0, CASE


def _store_with_finding(tmp_path):
    conn = db.connect(tmp_path / "read-model.db")
    run_id = seed_run(conn)
    claim_id = add_v2_claim(conn, run_id, sources_assessed=True, sources_missing=["jira", "ado"])
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at, summary)"
                 " VALUES (?,?,?,?,?,?,?)",
                 (CASE, run_id, "fixture", "level_fitness", "snap-schema",
                  "2020-01-01T00:00:00+00:00", "{}"))
    conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                 " VALUES (?,?,?,?,?)", (CASE, "the panel is served", "high", "f" * 32, db.j([claim_id])))
    conn.commit()
    return conn, claim_id


def test_finding_rows_returns_statement_provenance_and_blind_spots_together(tmp_path):
    conn, _ = _store_with_finding(tmp_path)
    try:
        findings = queries.finding_rows(conn, CASE)
    finally:
        conn.close()

    claim = findings[0]["claims"][0]
    assert {"statement", "provenance", "sources_missing", "sources_state"} <= set(claim)
    assert claim["statement"].startswith("The panel is asserted")
    assert claim["sources_missing"] == ["jira", "ado"]


def test_the_read_model_carries_every_provenance_field(tmp_path):
    conn, _ = _store_with_finding(tmp_path)
    try:
        claim = queries.finding_rows(conn, CASE)[0]["claims"][0]
    finally:
        conn.close()

    assert set(claim["provenance"]) == set(queries.PROVENANCE_FIELDS)
    assert set(queries.PROVENANCE_FIELDS) == {
        "assertion_text", "assertion_path", "assertion_line", "assertion_commit"}


def test_the_read_model_values_are_the_stored_values(tmp_path):
    """If the query stopped selecting a provenance column, this test - not the UI - would fail."""
    conn, claim_id = _store_with_finding(tmp_path)
    try:
        model = queries.claim_read(conn, claim_id)
        stored = conn.execute("SELECT * FROM claim WHERE id = ?", (claim_id,)).fetchone()
    finally:
        conn.close()

    for field in queries.PROVENANCE_FIELDS:
        assert model["provenance"][field] == stored[field], field
        assert model["provenance"][field] == PROVENANCE[field], field

    for field in ("statement", "interaction_label", "interaction_code", "span", "established_by",
                  "proposed_action", "sources_missing", "schema_version"):
        assert field in model, field


def test_a_v1_claim_in_a_case_still_carries_the_three_keys(tmp_path):
    """A page over a v1 claim must be able to say "not recorded" rather than fail or fill in blanks."""
    conn = db.connect(tmp_path / "read-model-v1.db")
    try:
        run_id = seed_run(conn, schema_version=1)
        claim_id = db.add_claim(conn, run_id, "level_fitness", "0.5.0",
                                "scenario:features/panel_api.feature#older", "older heading",
                                "distinct", 0.0, [])
        conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at, summary)"
                     " VALUES (?,?,?,?,?,?,?)",
                     (CASE, run_id, "fixture", "level_fitness", "snap-schema",
                      "2020-01-01T00:00:00+00:00", "{}"))
        conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                     " VALUES (?,?,?,?,?)", (CASE, "t", "high", "e" * 32, db.j([claim_id])))
        conn.commit()
        claim = queries.finding_rows(conn, CASE)[0]["claims"][0]
    finally:
        conn.close()

    assert set(claim["provenance"]) == set(queries.PROVENANCE_FIELDS)
    assert all(value is None for value in claim["provenance"].values())
    assert claim["sources_missing"] is None
