"""TESTOPS-33: the case list says what the case is about, not what the step reads.

The Product Owner read the dashboard and said of the row he found there - "the suggestions list
should be" - that he would not click it, "as it is neither descriptive of the case claim, nor is it
a complete sentence". The row was the claim's raw ``assertion_text``, which is a step's words, not
a title.

A row now reads ``<judgement> — <subject>``. These tests pin the shape (AC1), the refusal of a
dangling head or tail (AC2), the 90-character ceiling with a word-boundary trim (AC3), the full
assertion remaining on the case page (AC4), the project grouping and the verdict badge (AC5), and
- over a run the real pipeline wrote (AC6) - that no row's link text is an assertion fragment.

Every store is built under ``tmp_path``. Nothing here reads the product's ``data/testops.db``, so a
re-run of an analyser cannot change what these tests assert.
"""
from __future__ import annotations

import html as htmllib
import re
import urllib.parse

import level_fixtures as fixtures
from testops import queries
from testops.store import db
from testops.web import app

TS = "2020-01-01T00:00:00+00:00"
SNAP = "snap-headline"
COMMIT = "a" * 40
PATH = "features/question_suggestions.feature"
SUGGESTIONS = "the suggestions list should be"
SUGGESTIONS_TITLE = "The same word is in different fields"

# A project heading, then one row: its case id and the link text the reader clicks.
ROW = re.compile(r'<h2 class="section">(.*?)</h2>|<li><a href="/case/([^"]+)">.*?'
                 r'<p class="claimtext">(.*?)</p>', re.S)

# The judgement each verdict makes, in the list's own words (AC1).
JUDGEMENT = {
    "distinct": "Checked",
    "review": "Checked, but over-tested",
    "duplicate": "Already asserted elsewhere",
    "gap": "Not proved",
    "unplaced": "Cannot tell",
}


# --------------------------------------------------------------------------- store fixtures

def _seed_case(conn, *, case_id: str, project: str = "reqoverflow", verdict: str = "duplicate",
               scenario: str | None = SUGGESTIONS_TITLE, assertion: str = SUGGESTIONS,
               findings: int = 1, created_at: str = TS, analyser: str = "level_fitness") -> int:
    """One snapshot, one run, one claim and one case - the minimum a list row needs."""
    run_id = f"run-{case_id}"
    db.upsert_snapshot(conn, SNAP, "fixture", TS, {"owner/test": COMMIT}, schema_version=2)
    db.start_run(conn, run_id, project, SNAP, analyser, created_at)
    subject = f"scenario:{PATH}#{scenario}" if scenario else f"issue:COTW-{case_id[-2:]}"
    claim_id = db.add_claim(
        conn, run_id, analyser, "0.8.0", subject,
        "This test asserts the step, and another scenario already asserts it.", verdict, 0.5, [],
        schema_version=2, assertion_text=assertion, assertion_path=PATH, assertion_line=17,
        assertion_commit=COMMIT, interaction_label="needs a browser", interaction_code="I4",
        span=["ui"], sources_assessed=True, sources_missing=[], proposed_action="Merge them.")
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at,"
                 " summary) VALUES (?,?,?,?,?,?,?)",
                 (case_id, run_id, project, analyser, SNAP, created_at, "{}"))
    if findings:
        conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                     " VALUES (?,?,?,?,?)",
                     (case_id, assertion[:160], "high", (case_id + "0" * 32)[:32], db.j([claim_id])))
    conn.commit()
    return claim_id


def _rows(body: str) -> list[dict]:
    """Every list row as ``{"project", "case", "headline"}``, in the order the page renders them."""
    project = ""
    rows: list[dict] = []
    for match in ROW.finditer(body):
        if match.group(1) is not None:
            project = htmllib.unescape(match.group(1))
        else:
            rows.append({"project": project, "case": urllib.parse.unquote(match.group(2)),
                         "headline": htmllib.unescape(match.group(3))})
    return rows


# --------------------------------------------------------------------------- AC1

def test_each_verdict_reads_as_its_judgement_followed_by_the_scenario_title(tmp_path):
    conn = db.connect(tmp_path / "headline.db")
    try:
        # One case per project: the list holds the newest case per analyser, so a single project
        # would collapse five cases into one row.
        for verdict in JUDGEMENT:
            _seed_case(conn, case_id=f"case-{verdict}", project=f"p-{verdict}", verdict=verdict)
        rows = _rows(app.index(conn).decode("utf-8"))
    finally:
        conn.close()

    rendered = {row["case"]: row["headline"] for row in rows}
    for verdict, judgement in JUDGEMENT.items():
        headline = rendered[f"case-{verdict}"]
        assert headline == f"{judgement} \u2014 {SUGGESTIONS_TITLE}", headline


def test_a_claim_with_no_scenario_title_falls_back_to_its_normalised_step_text(tmp_path):
    """The step is the fallback subject, never the title: no keyword, no dangling tail (AC2)."""
    conn = db.connect(tmp_path / "fallback.db")
    try:
        _seed_case(conn, case_id="case-01", scenario=None)
        rows = _rows(app.index(conn).decode("utf-8"))
    finally:
        conn.close()

    assert len(rows) == 1
    headline = rows[0]["headline"]
    assert headline == "Already asserted elsewhere \u2014 the suggestions list"
    assert SUGGESTIONS not in headline


def test_the_defect_row_no_longer_reads_as_its_assertion(tmp_path):
    """The exact row the Product Owner refused to click, with and without a scenario title."""
    conn = db.connect(tmp_path / "defect.db")
    try:
        _seed_case(conn, case_id="case-title", scenario=SUGGESTIONS_TITLE)
        _seed_case(conn, case_id="case-plain", scenario=None, project="other")
        body = app.index(conn).decode("utf-8")
        rows = _rows(body)
        claim_texts = [rule for rule in conn.execute("SELECT assertion_text FROM claim")]
    finally:
        conn.close()

    assertions = {row["assertion_text"] for row in claim_texts}
    assert SUGGESTIONS in assertions
    assert len(rows) == 2
    for row in rows:
        headline = row["headline"]
        assert headline not in assertions, headline
        assert not headline.startswith(SUGGESTIONS), headline


# --------------------------------------------------------------------------- AC2

def test_a_headline_never_ends_on_a_word_that_cannot_end_a_phrase():
    """Refused, not printed: every subject here ends on the fragment the ticket names."""
    subjects = ["the suggestions list should be", "the panel at", "the page served with",
                "the citation, in", "the fact sheet is", "the row labelled the",
                "the response body carries", "with"]
    judgements = [None, *JUDGEMENT.values(), "Cannot tell"]
    for judgement in judgements:
        for subject in subjects:
            headline = app.case_headline(judgement, subject)
            if not headline:
                # Nothing but a dangling word to say, and no judgement to say it with: the list
                # falls back to the row's own label rather than printing the fragment.
                assert judgement is None, (judgement, subject)
                continue
            assert app.headline_problems(headline) == [], (judgement, subject, headline)
            assert not app.ends_in_fragment(headline), headline


def test_the_fragment_rule_bites_when_a_headline_is_handed_over_whole():
    """The refusal has teeth: a raw fragment is reported, not accepted."""
    assert app.headline_problems("the suggestions list should be")
    assert app.headline_problems("Not proved \u2014 the panel at")
    assert app.headline_problems("Checked \u2014 with")
    # A whole phrase passes.
    assert app.headline_problems("Not proved \u2014 The panel is served") == []


# --------------------------------------------------------------------------- AC3

def test_a_long_subject_is_trimmed_at_a_word_boundary_within_ninety_characters():
    title = ("The panel serves every sheet with the corpus unavailable and the stored paragraphs "
             "are shown without reading them from the corpus again")
    headline = app.case_headline("Checked, but over-tested", title)
    assert len(headline) <= app.HEADLINE_MAX == 90
    assert headline.endswith("\u2026"), headline
    trimmed = headline.split(" \u2014 ", 1)[1].rstrip("\u2026")
    # Never mid-word: what is left is a whole-word prefix of the title.
    assert title.startswith(trimmed) and title[len(trimmed)] == " ", headline
    assert app.headline_problems(headline) == []


def test_every_rendered_headline_fits_the_ceiling(tmp_path):
    conn = db.connect(tmp_path / "ceiling.db")
    try:
        _seed_case(conn, case_id="case-long", scenario="A " * 120 + "title")
        _seed_case(conn, case_id="case-short", project="other")
        rows = _rows(app.index(conn).decode("utf-8"))
    finally:
        conn.close()

    assert rows
    for row in rows:
        assert app.headline_problems(row["headline"]) == [], row["headline"]


# --------------------------------------------------------------------------- AC4

def test_the_case_page_still_carries_the_full_assertion_text(tmp_path):
    conn = db.connect(tmp_path / "case.db")
    try:
        _seed_case(conn, case_id="case-full")
        body = app.case_page(conn, "case-full").decode("utf-8")
    finally:
        conn.close()

    assert SUGGESTIONS in body
    assert SUGGESTIONS_TITLE in body


# --------------------------------------------------------------------------- AC5

def test_the_list_groups_by_project_and_marks_an_unplaced_claim(tmp_path):
    conn = db.connect(tmp_path / "groups.db")
    try:
        # Two cases under one project (a different analyser each), so grouping has something to
        # group; a second project, so the headings have something to separate.
        _seed_case(conn, case_id="case-a1", project="alpha", verdict="distinct", created_at=TS)
        _seed_case(conn, case_id="case-a2", project="alpha", verdict="unplaced",
                   analyser="duplication", created_at="2020-01-02T00:00:00+00:00")
        _seed_case(conn, case_id="case-b1", project="beta", verdict="gap",
                   created_at="2020-01-03T00:00:00+00:00")
        body = app.index(conn).decode("utf-8")
        rows = _rows(body)
    finally:
        conn.close()

    assert len(rows) == 3
    # One heading per project, and every row sits under its own project's heading.
    headings = re.findall(r'<h2 class="section">(.*?)</h2>', body)
    assert sorted(headings) == ["alpha", "beta"], headings
    assert len(headings) == len(set(headings)), "a project is split across two headings"
    order = [row["project"] for row in rows]
    runs = [p for i, p in enumerate(order) if i == 0 or order[i - 1] != p]
    assert len(runs) == len(set(runs)), f"a project's rows are not together: {order}"
    judgements = {(row["project"], row["headline"].split(" \u2014 ", 1)[0]) for row in rows}
    assert judgements == {("alpha", "Checked"), ("alpha", "Cannot tell"), ("beta", "Not proved")}
    # The verdict badge says what the headline's judgement is, and an unplaced claim reads as one.
    assert '<span class="badge verdict soft">Cannot tell</span>' in body
    assert '<span class="badge verdict">Checked</span>' in body
    assert '<span class="badge verdict">Not proved</span>' in body


# --------------------------------------------------------------------------- AC6

def test_a_real_run_lists_no_row_whose_link_text_is_an_assertion_fragment(tmp_path, monkeypatch):
    """AC6: the list rendered from a run the real pipeline wrote, not a hand-made row."""
    from testops import pipeline
    from testops.config import Project, Repo

    path, connect = fixtures.stub_pipeline(monkeypatch, pipeline, tmp_path)
    # Two projects, so the list has more than one row to refuse: the newest case per analyser is
    # all the list shows, and one project would collapse to a single row.
    for key in ("fixture", "second"):
        project = Project(key=key, product=Repo("o", "product"), test=Repo("o", "tests"),
                          jira_key="")
        pipeline.run_level_fitness(project, token="unused")
    conn = connect(path)
    try:
        body = app.index(conn).decode("utf-8")
        rows = _rows(body)
        assertions = {row["assertion_text"] for row in
                      conn.execute("SELECT assertion_text FROM claim WHERE assertion_text IS NOT NULL")}
        titles = {row["subject_ref"].partition("#")[2] for row in
                  conn.execute("SELECT subject_ref FROM claim")}
        claims, _older = queries.latest_per_analyser(conn)
    finally:
        conn.close()

    assert len(rows) >= 2, "the real run raised no case to list"
    assert len(assertions) >= 2
    for row in rows:
        headline = row["headline"]
        # No whole phrase is refused, and no row is the raw assertion fragment the ticket names.
        assert app.headline_problems(headline) == [], headline
        assert headline not in assertions, headline
        assert " \u2014 " in headline, headline
        # The judgement comes from the verdict vocabulary the ticket lists.
        judgement = headline.split(" \u2014 ", 1)[0]
        assert judgement in JUDGEMENT.values(), headline
        # And the subject is the scenario the claim was recorded against.
        subject = headline.split(" \u2014 ", 1)[1]
        assert subject in titles, headline
    assert {row["verdict"] for row in claims} <= set(JUDGEMENT)
