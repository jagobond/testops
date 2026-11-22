"""AC7: N actionable claims produce N cases with one finding each; distinct claims produce none.

This drives the real ``run_level_fitness`` against a fake repository and a throwaway store. Grouping
claims into one case is exactly how a single decision came to silence two assertions, so the count
and the one-finding rule are asserted from the store, not from the returned object.
"""
from __future__ import annotations

import json

import level_fixtures as fixtures


def _run(tmp_path, monkeypatch, feature: str = fixtures.PIPELINE_FEATURE):
    from testops import pipeline
    from testops.config import Project, Repo
    from testops.store import db

    path, connect = fixtures.stub_pipeline(monkeypatch, pipeline, tmp_path, feature=feature)
    project = Project(key="fixture", product=Repo("o", "product"), test=Repo("o", "tests"),
                      jira_key="")
    result = pipeline.run_level_fitness(project, token="unused")
    return result, connect(path)


def test_three_claims_of_which_two_are_actionable_produce_two_cases(tmp_path, monkeypatch):
    result, conn = _run(tmp_path, monkeypatch)
    try:
        verdicts = [claim.verdict for claim in result.claims]
        assert verdicts.count("gap") == 2
        assert verdicts.count("distinct") == 1

        case_count = conn.execute("SELECT COUNT(*) FROM case_").fetchone()[0]
        finding_count = conn.execute("SELECT COUNT(*) FROM finding").fetchone()[0]
    finally:
        conn.close()

    assert case_count == 2, "one case per actionable claim"
    assert finding_count == 2, "distinct claims raise no finding"
    assert len(result.case_ids) == 2
    assert result.case_id == result.case_ids[0]


def test_every_case_holds_exactly_one_finding(tmp_path, monkeypatch):
    _result, conn = _run(tmp_path, monkeypatch)
    try:
        per_case = conn.execute(
            "SELECT case_id, COUNT(*) AS n FROM finding GROUP BY case_id").fetchall()
        claim_ids = [json.loads(row["claim_ids"]) for row in
                     conn.execute("SELECT claim_ids FROM finding").fetchall()]
    finally:
        conn.close()

    assert len(per_case) == 2
    assert {row["n"] for row in per_case} == {1}, "a case must never group two claims"
    assert all(len(ids) == 1 for ids in claim_ids)


def test_the_two_claims_of_one_scenario_get_two_separate_cases(tmp_path, monkeypatch):
    """The Product Owner's complaint: two claims in one scenario shared one decision button."""
    _result, conn = _run(tmp_path, monkeypatch)
    try:
        rows = conn.execute(
            """SELECT f.case_id, c.subject_ref, c.assertion_text
                 FROM finding f, claim c
                WHERE c.id IN (SELECT value FROM json_each(f.claim_ids))""").fetchall()
    finally:
        conn.close()

    assert len(rows) == 2
    assert len({row["case_id"] for row in rows}) == 2
    assert rows[0]["subject_ref"] == rows[1]["subject_ref"]      # same scenario
    assert rows[0]["assertion_text"] != rows[1]["assertion_text"]  # different assertions


def test_a_run_with_nothing_actionable_creates_no_case_and_no_finding(tmp_path, monkeypatch):
    only_distinct = """\
Feature: fact sheet
  Scenario: the fact sheet is served with anchors
    Given the fact sheet endpoint returns a sheet
    Then the response body carries stable fact anchors
"""
    result, conn = _run(tmp_path, monkeypatch, feature=only_distinct)
    try:
        case_count = conn.execute("SELECT COUNT(*) FROM case_").fetchone()[0]
        finding_count = conn.execute("SELECT COUNT(*) FROM finding").fetchone()[0]
    finally:
        conn.close()

    assert [claim.verdict for claim in result.claims] == ["distinct"]
    assert case_count == 0
    assert finding_count == 0
    assert result.case_ids == []
    assert result.case_id == ""


def test_the_written_claims_are_v2_with_their_coordinates(tmp_path, monkeypatch):
    _result, conn = _run(tmp_path, monkeypatch)
    try:
        rows = conn.execute("SELECT * FROM claim ORDER BY id").fetchall()
    finally:
        conn.close()

    assert len(rows) == 3
    for row in rows:
        assert row["schema_version"] == 2
        assert row["assertion_text"]
        assert row["assertion_path"] == "features/fact_sheet.feature"
        assert row["assertion_line"] > 0
        assert row["assertion_commit"] == fixtures.COMMIT
        assert row["interaction_label"]
        assert row["interaction_code"] in {"I1", "I2", "I3", "I4", "KP", "U"}
        assert row["proposed_action"]
        assert json.loads(row["sources_missing"]) == []
