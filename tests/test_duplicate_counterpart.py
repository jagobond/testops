"""TESTOPS-32: a duplicate page shows the copy the claim names, not context in its place.

The Product Owner's finding: for a duplicate claim the statement names a counterpart at
``file:line``, and the page never shows it. What it showed instead was the context list - the other
steps in the claim's *own* scenario - which is correctly labelled as not evidence. The page withheld
the one piece of evidence the claim rests on.

These tests render the real corpus run (``reqoverflow_fixtures``), so the page is read from the
blobs and rows that run recorded, and not from a hand-written copy of a feature file.
"""
from __future__ import annotations

import html as htmllib
import re

import reqoverflow_fixtures as corpus

COPY_HEADING = "The copy this claim names"
CONTEXT_HEADING = "The other steps in this scenario, for context"

# The claim this test reads: the API copy of "The latest question is shown on home page with
# details", which names the Controller copy at this line.
CLAIM_PATH = "ReqOverflow.Specs.API/Features/Home.feature"
CLAIM_LINE = 24
COPY_WHERE = "ReqOverflow.Specs.Controller/Features/Home.feature:23"
COPY_ROW = "How to write better BDD scenarios?"


def _project():
    from testops.config import Project, Repo

    return Project(key="reqoverflow",
                   product=Repo("reqnroll", "Sample-ReqOverflow"),
                   test=Repo("reqnroll", "Sample-ReqOverflow"),
                   jira_key="")


def _run(tmp_path, monkeypatch):
    from testops import pipeline

    path, connect = corpus.stub_pipeline(monkeypatch, pipeline, tmp_path)
    result = pipeline.run_duplication(_project(), token="unused")
    return result, connect(path)


def _case_for(conn, path: str, line: int) -> str:
    """The case whose one claim asserts ``path`` at ``line``."""
    import json

    rows = conn.execute(
        "SELECT f.case_id, f.claim_ids FROM finding f").fetchall()
    for row in rows:
        for claim_id in json.loads(row["claim_ids"]):
            claim = conn.execute("SELECT assertion_path, assertion_line FROM claim WHERE id = ?",
                                 (claim_id,)).fetchone()
            if claim and claim["assertion_path"] == path and claim["assertion_line"] == line:
                return row["case_id"]
    raise AssertionError(f"no case for {path}:{line}")


def _text(body: bytes) -> str:
    text = body.decode("utf-8")
    text = re.sub(r"<style>.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<head>.*?</head>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(htmllib.unescape(text).split())


def test_a_duplicate_case_shows_the_copy_it_names(tmp_path, monkeypatch):
    """AC1, AC2, AC4, AC5: the copy's coordinates, its rows and its definition, before context."""
    from testops.web import app

    result, conn = _run(tmp_path, monkeypatch)
    try:
        case_id = _case_for(conn, CLAIM_PATH, CLAIM_LINE)
        body = app.case_page(conn, case_id)
    finally:
        conn.close()

    assert body is not None
    html = body.decode("utf-8")
    text = _text(body)

    # AC1/AC5: the copy's own file:line is on the page.
    assert COPY_WHERE in text, "the counterpart's file:line never appears"
    # AC1: it is a named section, not the context list, and it comes first.
    assert COPY_HEADING in text
    assert CONTEXT_HEADING in text, "the context list must still be shown too"
    assert html.index(COPY_HEADING) < html.index(CONTEXT_HEADING), \
        "the copy must come before the context list"
    # AC1: the copy's scenario title is named, and the definition that runs the step there.
    assert "The latest question is shown on home page with details" in text
    assert "The step definition that runs the copy\u2019s step there:" in text

    # AC2: the copy's own table row is inside the copy's excerpt, not merely somewhere on the page.
    figure = next((part.split("</figure>", 1)[0] for part in html.split('<figure class="snippet">')
                   if COPY_WHERE in part.split("</figcaption>", 1)[0]), None)
    assert figure, "the counterpart's scenario was not rendered as an excerpt"
    assert COPY_ROW in htmllib.unescape(figure)
    # The line the claim names is the one marked inside that excerpt.
    assert '<span class="sline hit">' in figure


def test_a_duplicate_case_says_so_when_the_copy_was_not_stored(tmp_path, monkeypatch):
    """AC3: a missing blob renders the recorded-but-not-stored sentence, naming the coordinates."""
    from pathlib import Path

    from testops import blobs
    from testops.web import app

    result, conn = _run(tmp_path, monkeypatch)
    try:
        case_id = _case_for(conn, CLAIM_PATH, CLAIM_LINE)
        sha = conn.execute(
            "SELECT blob_sha FROM artefact WHERE snapshot_id = ? AND uri LIKE ?",
            (result.snapshot_id, f"%:{COPY_WHERE.rsplit(':', 1)[0]}")).fetchone()["blob_sha"]
        Path(blobs._path(sha)).unlink()
        body = app.case_page(conn, case_id)
    finally:
        conn.close()

    assert body is not None
    text = _text(body)
    assert "The source was recorded but its content is not in this store" in text
    assert COPY_WHERE in text


def test_a_non_duplicate_case_renders_no_copy_section(tmp_path):
    """AC5: only a claim that names a copy gets the section."""
    from testops.store import db
    from testops.web import app

    ts = "2020-01-01T00:00:00+00:00"
    commit = "c" * 40
    path = "features/panel_api.feature"
    conn = db.connect(tmp_path / "gap.db")
    db.upsert_snapshot(conn, "snap-gap", "fixture", ts, {"owner/test": commit}, schema_version=2)
    db.start_run(conn, "run-gap", "fixture", "snap-gap", "level_fitness", ts)
    claim_id = db.add_claim(
        conn, "run-gap", "level_fitness", "0.8.0",
        "scenario:features/panel_api.feature#the panel is served",
        "This test asserts that the panel is served.", "gap", 0.5, [], schema_version=2,
        assertion_text="the panel is served", assertion_path=path, assertion_line=17,
        assertion_commit=commit, interaction_label="needs a browser", interaction_code="I4",
        span=["api"], established_by="asserts an accessibility property the browser computes",
        sources_missing=[], proposed_action="Move it.")
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at,"
                 " summary) VALUES (?,?,?,?,?,?,?)",
                 ("case-gap", "run-gap", "fixture", "level_fitness", "snap-gap", ts, "{}"))
    conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                 " VALUES (?,?,?,?,?)",
                 ("case-gap", "gap", "high", "d" * 32, db.j([claim_id])))
    conn.commit()
    try:
        body = app.case_page(conn, "case-gap")
    finally:
        conn.close()

    assert body is not None
    text = _text(body)
    assert COPY_HEADING not in text
    assert CONTEXT_HEADING in text
