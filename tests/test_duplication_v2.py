"""TESTOPS-21: duplication claims carry their own subject.

The Product Owner opened ``case-demo-service-dup-20261120T153431`` and saw eighteen findings that looked
identical and presented no finding. He was right. These tests pin the fix against the real corpus that
run analysed:

  * AC1 - every claim is v2 with the assertion's text, path, line and commit, a span, an interaction
    label and a proposed action, and the store's ``claim_v2_requires_provenance`` constraint is what
    accepted the rows;
  * AC2 - each statement names the scenario's own file:line, quotes what it asserts, and names the copy
    that already covers it with that copy's file:line; no two statements in a run are equal;
  * AC3 - eighteen findings are eighteen cases, one finding each - never one decision button for the
    whole run;
  * AC4 - the action raises the duplicate for the team and asks them to keep one copy, without
    condemning the test or recommending deletion;
  * AC5 - the evidence resolves from the claim's coordinates and the asserting step is shown inline.

The corpus is the stored run's own 108 test-suite files (see ``demo-service_fixtures``), so the numbers
are the Product Owner's numbers: 18 claims, 18 cases. TESTOPS-31 corrected one of them: two
QuestionSuggestions scenarios were declared duplicates on step text alone while their tables assert
different lists, so the corrected signature yields 17 claims and 17 cases. See
``test_duplication_tables`` for that pair pinned both ways.
"""
from __future__ import annotations

import html as htmllib
import json
import re

import demo_service_fixtures as corpus

CODE = re.compile(r"\b(I[1-4]|KP)\b")
CONDEMN = re.compile(r"\b(delete|remove|condemn|waste|redundant|should not exist)\b", re.I)


def _project():
    from testops.config import Project, Repo

    return Project(key="demo-service",
                   product=Repo("reqnroll", "demo-service"),
                   test=Repo("reqnroll", "demo-service"),
                   jira_key="")


def _run(tmp_path, monkeypatch):
    from testops import pipeline

    path, connect = corpus.stub_pipeline(monkeypatch, pipeline, tmp_path)
    result = pipeline.run_duplication(_project(), token="unused")
    return result, connect(path)


def _text(body: bytes) -> str:
    text = body.decode("utf-8")
    text = re.sub(r"<style>.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<head>.*?</head>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(htmllib.unescape(text).split())


# --------------------------------------------------------------------------- AC1

def test_every_claim_is_v2_with_its_assertion_coordinates(tmp_path, monkeypatch):
    result, conn = _run(tmp_path, monkeypatch)
    try:
        rows = conn.execute("SELECT * FROM claim ORDER BY id").fetchall()
        snapshot = conn.execute("SELECT schema_version FROM snapshot WHERE id = ?",
                                (result.snapshot_id,)).fetchone()
    finally:
        conn.close()

    assert len(rows) == 17
    assert snapshot["schema_version"] == 2, "a duplication snapshot now records the claim schema it wrote"
    for row in rows:
        assert row["schema_version"] == 2
        assert row["assertion_text"].strip()
        assert row["assertion_path"].strip()
        assert row["assertion_line"] > 0
        assert row["assertion_commit"] == corpus.COMMIT
        assert json.loads(row["span"])
        assert row["interaction_label"].strip()
        assert row["proposed_action"].strip()
        # The database's own constraint, not a Python guard, is what accepted these rows.
        assert row["assertion_path"] and row["assertion_line"] and row["assertion_commit"]


def test_the_claim_coordinates_point_at_the_step_that_asserts(tmp_path, monkeypatch):
    result, conn = _run(tmp_path, monkeypatch)
    try:
        first = conn.execute("SELECT * FROM claim ORDER BY id LIMIT 1").fetchone()
        text = corpus.texts()[first["assertion_path"]]
    finally:
        conn.close()

    line = text.splitlines()[first["assertion_line"] - 1]
    assert first["assertion_text"] in line
    assert line.strip().lower().startswith(("then", "and", "but", "*"))


# --------------------------------------------------------------------------- AC2

def test_every_statement_is_distinct_and_names_its_copy(tmp_path, monkeypatch):
    result, conn = _run(tmp_path, monkeypatch)
    try:
        rows = [dict(row) for row in conn.execute("SELECT * FROM claim ORDER BY id")]
    finally:
        conn.close()

    statements = [row["statement"] for row in rows]
    assert len(statements) == 17
    assert len(set(statements)) == 17, "two findings share a statement"

    for row in rows:
        statement = row["statement"]
        assert row["assertion_text"] in statement
        assert f"{row['assertion_path']}:{row['assertion_line']}" in statement
        # The copy that already establishes it, with that copy's own file:line.
        other = re.search(r"([\w./-]+\.feature):(\d+)", statement.split(" which ", 1)[1])
        assert other, statement
        other_path, other_line = other.group(1), int(other.group(2))
        other_text = corpus.texts()[other_path]
        assert other_line <= len(other_text.splitlines())
        # The copy may live in the same file (two scenarios in one suite) and even on the same line
        # number in a different suite - but never at this claim's own coordinates.
        assert f"{other_path}:{other_line}" != f"{row['assertion_path']}:{row['assertion_line']}"


def test_the_two_copies_of_one_claim_say_what_each_actually_does(tmp_path, monkeypatch):
    """The old statement named the verdict; the new one names the instrument and the assertion."""
    result, conn = _run(tmp_path, monkeypatch)
    try:
        rows = conn.execute(
            "SELECT statement FROM claim WHERE subject_ref LIKE ? ORDER BY id",
            ("%DemoService.Specs.API/Features/Authentication.feature#%",)).fetchall()
    finally:
        conn.close()

    assert len(rows) == 1
    statement = rows[0]["statement"]
    assert "calls the HTTP client" in statement
    assert "the login attempt should be successful" in statement
    assert "DemoService.Specs.Controller/Features/Authentication.feature:8" in statement
    assert "this copy drives api" not in statement


# --------------------------------------------------------------------------- AC3

def test_every_finding_is_its_own_case_with_one_finding_each(tmp_path, monkeypatch):
    result, conn = _run(tmp_path, monkeypatch)
    try:
        claim_count = conn.execute("SELECT COUNT(*) FROM claim").fetchone()[0]
        case_count = conn.execute("SELECT COUNT(*) FROM case_").fetchone()[0]
        finding_count = conn.execute("SELECT COUNT(*) FROM finding").fetchone()[0]
        per_case = conn.execute(
            "SELECT case_id, COUNT(*) AS n FROM finding GROUP BY case_id").fetchall()
        claim_ids = [json.loads(row["claim_ids"]) for row in
                     conn.execute("SELECT claim_ids FROM finding").fetchall()]
        case_ids = [row["id"] for row in conn.execute("SELECT id FROM case_ ORDER BY id")]
    finally:
        conn.close()

    assert claim_count == 17
    assert case_count == 17
    assert finding_count == 17
    assert len(result.case_ids) == 17
    assert result.case_id == result.case_ids[0]
    assert len(case_ids) == len(set(case_ids)), "case ids must be unique"
    assert {row["n"] for row in per_case} == {1}, "a case must never group two findings"
    assert all(len(ids) == 1 for ids in claim_ids)
    # No case carries two findings - the defect was one case carrying all of them.
    assert max(row["n"] for row in per_case) == 1


def test_each_case_page_shows_only_its_own_claim(tmp_path, monkeypatch):
    from testops.web import app

    result, conn = _run(tmp_path, monkeypatch)
    try:
        html_pages = []
        for case_id in result.case_ids:
            body = app.case_page(conn, case_id)
            assert body is not None
            html_pages.append(body.decode("utf-8"))
        pages = [_text(body.encode("utf-8")) for body in html_pages]
        statements = [row["statement"] for row in conn.execute(
            "SELECT statement FROM claim ORDER BY id")]
        assertions = [row["assertion_text"] for row in conn.execute(
            "SELECT assertion_text FROM claim ORDER BY id")]
    finally:
        conn.close()

    assert len(pages) == 17
    assert len(assertions) == 17
    for page, html, assertion in zip(pages, html_pages, assertions):
        # TESTOPS-23: the page quotes its own claim's step, with the keyword the file gives it.
        assert assertion
        assert assertion in page, assertion
        argument = re.search(r'<section class="scan">(.*?)</section>', html, re.S)
        assert argument is not None
        assert assertion in htmllib.unescape(argument.group(1))
    # The analyser's essay is no longer reader-facing prose on any page.
    for page in pages:
        for statement in statements:
            assert statement not in page


# --------------------------------------------------------------------------- AC4

def test_the_action_raises_the_duplicate_for_the_team_and_keeps_one(tmp_path, monkeypatch):
    result, conn = _run(tmp_path, monkeypatch)
    try:
        actions = [row["proposed_action"] for row in conn.execute(
            "SELECT proposed_action FROM claim ORDER BY id")]
    finally:
        conn.close()

    assert len(actions) == 17
    for action in actions:
        assert action.startswith("Raise this with the team:")
        assert action.endswith("keep one.")
        assert not CODE.search(action), f"debugging shorthand reached a reader: {action!r}"
        assert not CONDEMN.search(action), f"action condemns the test or recommends deletion: {action!r}"


def test_an_intra_level_duplicate_also_names_its_copy_and_keeps_one(tmp_path, monkeypatch):
    """The same-level branch is a different sentence, with the same reader guarantees."""
    from testops import pipeline
    import level_fixtures
    from testops.config import Project, Repo

    feature = """\
Feature: fact sheet
  Scenario: the fact sheet is served
    Given the fact sheet endpoint returns a sheet
    Then the response body carries stable fact anchors

  Scenario: the fact sheet is served again
    Given the fact sheet endpoint returns a sheet
    Then the response body carries stable fact anchors
"""
    path, connect = level_fixtures.stub_pipeline(monkeypatch, pipeline, tmp_path, feature=feature)
    result = pipeline.run_duplication(
        Project(key="fixture", product=Repo("o", "product"), test=Repo("o", "tests"), jira_key=""),
        token="unused")
    conn = connect(path)
    try:
        row = conn.execute("SELECT * FROM claim").fetchone()
    finally:
        conn.close()

    assert len(result.claims) == 1
    assert row["schema_version"] == 2
    assert "the response body carries stable fact anchors" in row["statement"]
    assert "features/fact_sheet.feature:8" in row["statement"]          # this claim's own assertion
    assert "features/fact_sheet.feature:4" in row["statement"]          # the copy it duplicates
    assert row["proposed_action"].startswith("Raise this with the team:")
    assert row["proposed_action"].endswith("keep one.")


# --------------------------------------------------------------------------- AC5

def test_evidence_resolves_from_the_claims_coordinates(tmp_path, monkeypatch):
    from testops import queries

    result, conn = _run(tmp_path, monkeypatch)
    try:
        claim = queries.claim_read(conn, result.claims[0].claim_id)
    finally:
        conn.close()

    assert claim is not None
    evidence = claim["evidence"]
    assert evidence, "the claim's own coordinates must resolve to recorded evidence"
    assert evidence[0].get("asserted") is True, "the asserting step's binding is shown first"

    assertion = claim["snippets"]["assertion"]
    assert assertion["state"] == queries.SNIPPET_OK
    assert assertion["line"] == claim["provenance"]["assertion_line"]
    marked = [row for row in assertion["lines"] if row["asserted"]]
    assert len(marked) == 1

    definition = claim["snippets"]["step_definition"]
    assert definition["state"] == queries.SNIPPET_OK
    assert definition["line"] > 0


# --------------------------------------------------------------------------- AC6

def test_a_v1_duplication_case_keeps_the_recorded_before_provenance_wording(tmp_path):
    """Old runs are not backfilled: the page says so, and the old statement is still readable."""
    from testops.store import db
    from testops.web import app

    conn = db.connect(tmp_path / "legacy.db")
    db.upsert_snapshot(conn, "snap-legacy", "demo-service", "2026-11-20T15:34:30+00:00",
                       {corpus.REPO_SLUG: corpus.COMMIT}, schema_version=1,
                       meta={"sources_missing": ["jira"]})
    db.start_run(conn, "run-legacy", "demo-service", "snap-legacy", "duplication",
                 "2026-11-20T15:34:31+00:00")
    statement = ("asserts the same claim as 1 cheaper copy(ies) at controller; this copy drives api")
    claim_id = db.add_claim(conn, "run-legacy", "duplication", "1.1.0",
                            "scenario:DemoService.Specs.API/Features/Authentication.feature"
                            "#User logs in with valid credentials",
                            statement, "duplicate", 0.9, [], schema_version=1,
                            sources_assessed=True, sources_missing=["jira"])
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at, summary)"
                 " VALUES (?,?,?,?,?,?,?)",
                 ("case-legacy", "run-legacy", "demo-service", "duplication", "snap-legacy",
                  "2026-11-20T15:34:31+00:00", "{}"))
    conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                 " VALUES (?,?,?,?,?)",
                 ("case-legacy", statement[:160], "medium", "a" * 32, db.j([claim_id])))
    conn.commit()
    try:
        body = app.case_page(conn, "case-legacy")
    finally:
        conn.close()

    assert body is not None
    page = _text(body)
    assert "recorded before provenance was captured" in page
    assert statement in page
