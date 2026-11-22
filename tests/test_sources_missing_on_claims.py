"""AC6: every claim records which sources were never connected - or that nobody looked.

A missing source is never a zero. The caller supplies the list; the analyser copies it onto every
claim. A caller that supplies nothing produces no list at all, and the claim records the state that
describes: not assessed. It must not produce an explicit empty list, because an empty list reads as
"we looked and nothing was missing" - the guarantee TESTOPS-17 exists to stop a default producing.
"""
from __future__ import annotations

import json

import level_fixtures as fixtures


def test_the_callers_missing_sources_are_recorded_on_every_claim():
    claims = fixtures.analyse_fact_sheet(sources_missing=["jira", "ado"])
    assert claims
    for claim in claims:
        assert claim.detail["sources_assessed"] is True
        assert claim.detail["sources_missing"] == ["jira", "ado"]


def test_a_caller_that_passes_nothing_records_not_assessed_never_an_empty_list():
    claims = fixtures.analyse_fact_sheet()
    assert claims
    for claim in claims:
        assert claim.detail["sources_assessed"] is False
        assert claim.detail["sources_missing"] is None


def test_the_pipeline_names_the_requirement_sources_it_did_not_consult(tmp_path, monkeypatch):
    """A level run reads two repositories. Jira and ADO are recorded as absent, not as clean."""
    from testops import pipeline
    from testops.config import Project, Repo
    from testops.store import db

    path, connect = fixtures.stub_pipeline(monkeypatch, pipeline, tmp_path)
    project = Project(key="fixture", product=Repo("o", "product"), test=Repo("o", "tests"),
                      jira_key="FIX", ado_org="ORG", ado_project="proj")
    pipeline.run_level_fitness(project, token="unused")

    conn = connect(path)
    try:
        rows = conn.execute("SELECT sources_missing, proposed_action FROM claim").fetchall()
    finally:
        conn.close()

    assert rows
    for row in rows:
        assert json.loads(row["sources_missing"]) == ["jira", "ado"]
        assert row["proposed_action"]
