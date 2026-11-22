"""AC7: the emission gate in pipeline._emit turns a gap into exactly one finding, and distinct into none."""
from __future__ import annotations

from testops import cases, pipeline
from testops.analysers.base import Claim
from testops.store import db

RUN_ID = "run-emit"
CASE_ID = "case-emit"


def _case(conn) -> str:
    '''Seed the minimum rows _emit's foreign keys require (run -> case_).'''
    db.start_run(conn, RUN_ID, "fixture", "snap-emit", "level_fitness",
                 "2020-01-01T00:00:00+00:00")
    conn.execute(
        "INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at, summary)"
        " VALUES (?,?,?,?,?,?,?)",
        (CASE_ID, RUN_ID, "fixture", "level_fitness", "snap-emit",
         "2020-01-01T00:00:00+00:00", "{}"),
    )
    return CASE_ID


def _finding_count(conn, case_id: str) -> int:
    return conn.execute("SELECT COUNT(*) FROM finding WHERE case_id = ?", (case_id,)).fetchone()[0]


def test_distinct_claim_raises_no_finding(tmp_path):
    conn = db.connect(tmp_path / "emit.db")
    try:
        case_id = _case(conn)
        claim = Claim(subject_ref="scenario:a.feature#served", statement="the page is served",
                      verdict="distinct", detail={"claim": "KP"})
        emitted = pipeline._emit(conn, case_id, "level_fitness", claim)
        conn.commit()
        assert emitted is False
        assert _finding_count(conn, case_id) == 0
    finally:
        conn.close()


def test_gap_claim_raises_exactly_one_finding(tmp_path):
    conn = db.connect(tmp_path / "emit.db")
    try:
        case_id = _case(conn)
        claim = Claim(subject_ref="scenario:a.feature#needs-browser",
                      statement="I4 claim needs a browser to be established",
                      verdict="gap", detail={"claim": "I4"})
        emitted = pipeline._emit(conn, case_id, "level_fitness", claim)
        conn.commit()
        assert emitted is True
        assert _finding_count(conn, case_id) == 1

        row = conn.execute("SELECT fingerprint FROM finding WHERE case_id = ?", (case_id,)).fetchone()
        assert row["fingerprint"] == cases.fingerprint("level_fitness", claim.subject_ref, "I4")
    finally:
        conn.close()