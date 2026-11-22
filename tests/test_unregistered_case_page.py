"""TESTOPS-35 AC2: a case nothing in this build could have raised answers 404.

The fixture case ``rev-duplicate`` carries ``analyser = 'x'``. Before this, the page rendered it
like any other: an argument about the Product Owner's code that no analyser had made. Now the
store's own row is not enough - the analyser on it has to be one this build can run - and the
answer is the TESTOPS-30 page, served with the status that says the evidence is not here.
"""
from __future__ import annotations

from testops import queries
from testops.store import db
from testops.web import app

TS = "2026-11-22T00:00:00+00:00"
SNAP = "snap-page"
FIXTURE_CASE = "rev-duplicate"
REAL_CASE = "case-real-01"


def _store(tmp_path):
    conn = db.connect(tmp_path / "page.db")
    db.upsert_snapshot(conn, SNAP, "fixture", TS, {"o/test": "c" * 40}, schema_version=2)
    for run_id in ("run-real", "run-fixture"):
        db.start_run(conn, run_id, "fixture", SNAP, "level_fitness", TS)
    fixture_claim = db.add_claim(conn, "run-fixture", "x", "0", "scenario:f.feature#fixture",
                                 "fixture", "gap", 0.5, [], schema_version=1)
    # Both cases carry a finding. Since TESTOPS-34 a row with no finding is not a case and no list
    # returns it, so a control without one would prove nothing about the unregistered-analyser rule.
    real_claim = db.add_claim(
        conn, "run-real", "level_fitness", "0.8.0", "scenario:features/panel.feature#the panel",
        "The panel is asserted over HTTP, and nothing runs a browser.", "gap", 0.5, [],
        schema_version=2, assertion_text="the panel is served",
        assertion_path="features/panel.feature", assertion_line=3, assertion_commit="c" * 40,
        interaction_label="needs a browser", interaction_code="I4", span=["api"],
        established_by="asserts a property the browser computes",
        sources_assessed=True, sources_missing=[], proposed_action="Run it in a browser.")
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at,"
                 " summary) VALUES (?,?,?,?,?,?,?)",
                 (REAL_CASE, "run-real", "fixture", "level_fitness", SNAP, TS, "{}"))
    conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                 " VALUES (?,?,?,?,?)", (REAL_CASE, "gap", "high", "e" * 32, db.j([real_claim])))
    # Created later, so it would be the newest case in its project and appear on the dashboard.
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at,"
                 " summary) VALUES (?,?,?,?,?,?,?)",
                 (FIXTURE_CASE, "run-fixture", "review", "x", SNAP,
                  "2026-11-22T12:00:00+00:00", "{}"))
    conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                 " VALUES (?,?,?,?,?)",
                 (FIXTURE_CASE, "fixture", "high", "d" * 32, db.j([fixture_claim])))
    conn.commit()
    return conn


def test_unregistered_case_answers_404_with_the_stale_page(tmp_path):
    conn = _store(tmp_path)
    try:
        body, status = app.case_response(conn, FIXTURE_CASE)
        assert status == 404
        page = body.decode("utf-8")
        assert "This case is no longer in the store" in page
        assert FIXTURE_CASE in page
        assert "not one this build can run" in page
        assert "analyser <span class=\"code\">x</span>" in page
        # It must not claim retention pruned it: the row is still there, and the reason differs.
        assert "pruned by retention" not in page
    finally:
        conn.close()


def test_registered_case_still_renders(tmp_path):
    conn = _store(tmp_path)
    try:
        body, status = app.case_response(conn, REAL_CASE)
        assert status == 200
        # It renders its finding: the control for the test above is a case that carries one.
        assert b"the panel is served" in body
    finally:
        conn.close()


def test_unknown_id_keeps_the_old_retention_wording(tmp_path):
    conn = _store(tmp_path)
    try:
        body, status = app.case_response(conn, "never-existed")
        assert status == 404
        assert "pruned by retention" in body.decode("utf-8")
    finally:
        conn.close()


def test_dashboard_does_not_list_the_fixture_case(tmp_path):
    conn = _store(tmp_path)
    try:
        listed, _older = queries.latest_per_analyser(conn)
        assert FIXTURE_CASE not in [row["id"] for row in listed]
        assert REAL_CASE in [row["id"] for row in listed]
        index = app.index(conn).decode("utf-8")
        assert FIXTURE_CASE not in index
        assert REAL_CASE in index
    finally:
        conn.close()
