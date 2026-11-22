"""TESTOPS-6: the case page is an argument, and these are the eleven things it must say.

Every test builds its own store under ``tmp_path``. Nothing here reads the product's real
``data/testops.db``, so a re-run of the analyser can never change what these tests assert.

The page is rendered straight from a connection - no HTTP client, no fixture server - because the
ticket's first criterion is that a case page comes from the store, server-rendered, with no
JavaScript and no network at render time.
"""
from __future__ import annotations

import html as htmllib
import re
from typing import Any

from testops import queries
from testops.store import db
from testops.web import app

TS = "2020-01-01T00:00:00+00:00"
CASE = "case-page"
SNAP = "snap-page"
RUN = "run-page"
COMMIT = "a" * 40
OTHER_COMMIT = "b" * 40
PATH = "features/panel_api.feature"
LINE = 17
SECTIONS = (
    "1. What is asserted, and what settles it",
    "2. The step that is asserted",
    "3. The other steps in this scenario, for context",
    "4. What could not be checked",
    "5. Decision",
)
CODE = re.compile(r"\b(I[1-4]|KP)\b")


# --------------------------------------------------------------------------- store fixtures

def _seed(tmp_path, *, verdict="gap", code="I4", label="needs a browser", span=("api",),
          established_by="asserts an accessibility property the browser computes",
          missing=("jira", "ado"), path=PATH, line=LINE, commit=COMMIT, schema_version=2,
          statement="This test asserts that the panel is served. Only a browser works that out, "
                    "and this test only reads the responses the server sends instead, so nothing "
                    "checks it.",
          action='Move the step "the panel is served" into a test that drives a browser.',
          findings=1):
    """A snapshot, a run, one claim and a case - the minimum a case page needs."""
    conn = db.connect(tmp_path / "case-page.db")
    db.upsert_snapshot(conn, SNAP, "fixture", TS, {"owner/test": COMMIT},
                       schema_version=schema_version)
    db.start_run(conn, RUN, "fixture", SNAP, "level_fitness", TS)
    fields: dict[str, Any] = {}
    if schema_version == 2:
        fields = dict(
            assertion_text="each fact's citation is in an element reachable by an accessible name",
            assertion_path=path, assertion_line=line, assertion_commit=commit,
            interaction_label=label, interaction_code=code, span=list(span),
            established_by=established_by,
            sources_missing=None if missing is None else list(missing),
            proposed_action=action,
        )
    claim_id = db.add_claim(conn, RUN, "level_fitness", "0.8.0",
                            "scenario:features/panel_api.feature#the panel is served",
                            statement, verdict, 0.5, [], schema_version=schema_version, **fields)
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at, summary)"
                 " VALUES (?,?,?,?,?,?,?)",
                 (CASE, RUN, "fixture", "level_fitness", SNAP, TS, "{}"))
    if findings:
        conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                     " VALUES (?,?,?,?,?)",
                     (CASE, statement[:160], "high", "f" * 32, db.j([claim_id])))
    conn.commit()
    return conn, claim_id


def _add_artefact(conn, snapshot, uri, observations=()):
    artefact_id = db.add_artefact(conn, snapshot, uri, "feature", "0" * 40)
    for key, value in observations:
        db.add_observation(conn, artefact_id, "gherkin", "1.0.0", key, value)
    return artefact_id


def _text(body: bytes) -> str:
    """The words a browser shows, near enough for a contract test."""
    html = body.decode("utf-8")
    html = re.sub(r"<style>.*?</style>", " ", html, flags=re.S)
    html = re.sub(r"<head>.*?</head>", " ", html, flags=re.S)
    html = re.sub(r"<[^>]+>", " ", html)
    return " ".join(htmllib.unescape(html).split())


def _page(conn) -> str:
    body = app.case_page(conn, CASE)
    assert body is not None
    return body.decode("utf-8")


def _page_text(conn) -> str:
    return _text(app.case_page(conn, CASE))


# --------------------------------------------------------------------------- AC1

def test_every_v2_case_renders_all_five_sections_in_order(tmp_path):
    conn, _ = _seed(tmp_path)
    try:
        text = _page_text(conn)
    finally:
        conn.close()
    positions = [text.find(s) for s in SECTIONS]
    assert all(p >= 0 for p in positions), f"missing section(s): {text}"
    assert positions == sorted(positions), "the five sections are out of order"


def test_the_page_is_server_rendered_with_no_javascript_and_no_network(tmp_path, monkeypatch):
    """No script tag, no fetch at render time: ``case_page`` is a pure function of the store."""
    conn, _ = _seed(tmp_path)
    try:
        body = _page(conn)
    finally:
        conn.close()
    assert "<script" not in body.lower()
    assert "fetch(" not in body
    assert "http://" not in body.replace("https://github.com", "")


# --------------------------------------------------------------------------- AC2

def test_the_permalink_uses_the_claims_own_commit(tmp_path):
    conn, _ = _seed(tmp_path, commit=OTHER_COMMIT)
    try:
        # The snapshot's tip is COMMIT; the claim was read at a different commit, and this row is
        # the store's only record of which repository that path belongs to.
        _add_artefact(conn, SNAP, f"github:owner/test@{OTHER_COMMIT}:{PATH}")
        conn.commit()
        body = _page(conn)
        claim = queries.finding_rows(conn, CASE)[0]["claims"][0]
    finally:
        conn.close()

    expected = (f"https://github.com/owner/test/blob/{OTHER_COMMIT}/features/panel_api.feature"
                f"#L{LINE}")
    assert claim["permalink"] == expected
    assert expected in body


def test_a_claim_from_an_older_commit_does_not_link_to_the_snapshot_tip(tmp_path):
    conn, _ = _seed(tmp_path, commit=OTHER_COMMIT)
    try:
        _add_artefact(conn, SNAP, f"github:owner/test@{OTHER_COMMIT}:{PATH}")
        conn.commit()
        claim = queries.finding_rows(conn, CASE)[0]["claims"][0]
    finally:
        conn.close()
    assert COMMIT not in claim["permalink"]
    assert "HEAD" not in claim["permalink"]
    assert "main" not in claim["permalink"]


# --------------------------------------------------------------------------- AC3

def test_evidence_is_resolved_from_the_claims_own_coordinates(tmp_path):
    conn, _ = _seed(tmp_path)
    try:
        # The claim's file, at the claim's commit, in the claim's snapshot: this is the evidence.
        _add_artefact(conn, SNAP, f"github:owner/test@{COMMIT}:{PATH}",
                      [("scenario:the panel is served", {"line": 14, "steps": 6})])
        # A different path that merely ends with the same file name.
        _add_artefact(conn, SNAP, f"github:owner/test@{COMMIT}:other/{PATH}",
                      [("scenario:an impostor", {"line": 99, "steps": 2})])
        # The same path at the same commit, but recorded by a different snapshot.
        db.upsert_snapshot(conn, "snap-other", "fixture", TS, {"owner/test": COMMIT})
        _add_artefact(conn, "snap-other", f"github:owner/test@{COMMIT}:{PATH}",
                      [("scenario:from another snapshot", {"line": 7, "steps": 1})])
        conn.commit()

        claim = queries.finding_rows(conn, CASE)[0]["claims"][0]
        evidence = claim["evidence"]
        page = _page(conn)
    finally:
        conn.close()

    keys = [e["key"] for e in evidence]
    assert keys == ["scenario:the panel is served"], keys
    assert "impostor" not in page
    assert "another snapshot" not in page


def test_the_like_lookup_cannot_come_back():
    """The old ``LIKE %feature%`` resolver is gone, so no v2 page can reach it again."""
    assert not hasattr(queries, "evidence_for_subject")


# --------------------------------------------------------------------------- AC4

def test_the_scenario_title_is_labelled_as_the_tests_own(tmp_path):
    conn, _ = _seed(tmp_path)
    try:
        text = _page_text(conn)
    finally:
        conn.close()
    # TESTOPS-23 AC3: the title is a footnote under the quote, labelled as the author's name.
    assert "Where this comes from:" in text
    assert "the test author\u2019s own name for the scenario, not a requirement" in text
    # Nothing on the page claims a requirement was checked: none was connected.
    assert not re.search(r"\b(requirement|acceptance criteria) (is|was) (met|satisfied|covered)\b",
                         text, re.I)


# --------------------------------------------------------------------------- AC5

def test_every_evidence_link_carries_a_statement_of_what_it_shows(tmp_path):
    conn, _ = _seed(tmp_path)
    try:
        _add_artefact(conn, SNAP, f"github:owner/test@{COMMIT}:{PATH}",
                      [("scenario:the panel is served", {"line": 14, "steps": 6})])
        conn.commit()
        body = _page(conn)
    finally:
        conn.close()

    items = re.findall(r"<li>(.*?)</li>", body, re.S)
    assert items, "no evidence rendered"
    for item in items:
        assert "<a href=" in item, f"evidence item is not a link: {item!r}"
        assert " \u2014 " in item, f"evidence link has no statement: {item!r}"
    assert "the scenario \u201cthe panel is served\u201d begins at line 14, 6 steps" in body


# --------------------------------------------------------------------------- AC6

def test_codes_appear_only_in_a_labelled_footnote_below_the_decision(tmp_path):
    conn, _ = _seed(tmp_path)
    try:
        body = _page(conn)
    finally:
        conn.close()

    primary, _, footnote = body.partition("Debugging shorthand")
    assert footnote, "the footnote is missing"
    assert not CODE.search(_text(primary.encode("utf-8") + b"</main></body></html>")), \
        f"a code leaked into primary text: {primary[-400:]!r}"
    assert "I4" in footnote and "gap" in footnote
    # The footnote is below the decision form, not above it.
    assert body.index("</form>") < body.index("Debugging shorthand")


def test_the_home_page_carries_no_codes(tmp_path):
    conn, _ = _seed(tmp_path)
    try:
        body = app.index(conn).decode("utf-8")
    finally:
        conn.close()
    assert not CODE.search(_text(body.encode("utf-8")))


# --------------------------------------------------------------------------- AC7

def test_span_label_and_rule_render_as_reader_words_not_data(tmp_path):
    conn, _ = _seed(tmp_path, span=("api", "ui"), code="I4", label="needs a browser",
                    established_by="asserts an accessibility property the browser computes")
    try:
        text = _page_text(conn)
    finally:
        conn.close()
    assert '["api", "ui"]' not in text
    assert "['api', 'ui']" not in text
    assert '"span"' not in text
    # TESTOPS-23: the argument states the fact the rule found, never the rule or its vocabulary.
    assert "Nothing but a browser settles it, and the test drives a browser." in text
    assert "Why it was classified this way" not in text
    assert "the words" not in text
    assert "asserts an accessibility property the browser computes" not in text


# --------------------------------------------------------------------------- AC8

def test_the_decision_is_for_this_case_only_and_says_what_rides_on_it(tmp_path):
    conn, _ = _seed(tmp_path)
    try:
        text = _page_text(conn)
    finally:
        conn.close()
    assert "1 finding rides on this decision" in text
    assert "applies to this case only" in text
    assert "reopening deletes the suppression" in text.lower()


def test_reopening_deletes_the_suppression_and_the_page_says_so(tmp_path):
    from testops import cases

    conn, _ = _seed(tmp_path)
    try:
        cases.set_state(conn, CASE, "resolved", "harry", "known")
        terminal_text = _page_text(conn)
        assert "hidden from future runs" in terminal_text
        assert "Reopening deletes the suppression for this case" in terminal_text

        cases.set_state(conn, CASE, "open", "harry")
        assert conn.execute("SELECT COUNT(*) FROM suppression"
                            " WHERE fingerprint = ?", ("f" * 32,)).fetchone()[0] == 0
    finally:
        conn.close()


# --------------------------------------------------------------------------- AC9

def test_a_v1_claim_says_provenance_was_not_captured_instead_of_failing(tmp_path):
    conn, _ = _seed(tmp_path, verdict="duplicate", code=None, label=None, span=None,
                    established_by=None, missing=None, path=None, line=None, commit=None,
                    schema_version=1, statement="Two scenarios assert the same thing.",
                    action=None)
    try:
        body = app.case_page(conn, CASE)
    finally:
        conn.close()
    assert body is not None
    text = _text(body)
    assert "recorded before provenance was captured" in text
    # The claim is still shown, as it was recorded: no invented quote and no invented step.
    assert "The claim as recorded was: \u201cTwo scenarios assert the same thing.\u201d" in text
    assert "The test asserts the step" not in text
    assert "Whether any source needed for this claim was missing was not recorded" not in text
    assert ("Nothing was checked against any source for this claim, so nothing here says its "
            "sources were clean." in text)
    assert "No proposed action was recorded for this claim." in text


# --------------------------------------------------------------------------- AC10

def test_a_case_with_no_findings_is_described_as_a_run_not_a_decision(tmp_path):
    """TESTOPS-22 AC1: zero findings is a fact about the run, never a person's decision."""
    conn, _ = _seed(tmp_path, findings=0)
    try:
        text = _page_text(conn)
    finally:
        conn.close()
    assert "No findings in this run" in text
    assert "This case is resolved" not in text
    assert "Resolved" not in text
    assert "What this run could not consult" in text


def test_the_empty_home_page_reports_freshness_not_all_clear(tmp_path):
    conn = db.connect(tmp_path / "empty-home.db")
    try:
        db.upsert_snapshot(conn, SNAP, "fixture", TS, {"owner/test": COMMIT}, schema_version=2)
        db.start_run(conn, RUN, "fixture", SNAP, "level_fitness", TS)
        db.finish_run(conn, RUN, "ok", TS)
        conn.commit()
        text = _text(app.index(conn))
    finally:
        conn.close()
    assert "No cases are open" in text
    assert "Last analysed" in text
    assert "test@aaaaaaaa" in text  # the commit, to eight characters
    assert "all clear" not in text.lower()


# --------------------------------------------------------------------------- AC11

def test_the_case_list_shows_what_the_claim_asserts_not_a_truncated_title(tmp_path):
    """The index gets its words from the claim, so a heading cannot end mid-sentence.

    TESTOPS-23: the first line is the asserted step, in the test's own words - not the analyser's
    essay about it, and never finding.title.
    """
    conn = db.connect(tmp_path / "index.db")
    db.upsert_snapshot(conn, SNAP, "fixture", TS, {"owner/test": COMMIT}, schema_version=2)
    db.start_run(conn, RUN, "fixture", SNAP, "level_fitness", TS)
    db.finish_run(conn, RUN, "ok", TS)
    statement = ("This test asserts that each fact's citation is in an element reachable by an "
                 "accessible name. Only a browser works that out, and this test only reads the "
                 "responses the server sends instead, so nothing checks it.")
    claim_id = db.add_claim(
        conn, RUN, "level_fitness", "0.8.0", "scenario:features/panel_api.feature#the panel",
        statement, "gap", 0.5, [], schema_version=2, assertion_text="the panel",
        assertion_path=PATH, assertion_line=LINE, assertion_commit=COMMIT,
        interaction_label="needs a browser", interaction_code="I4", span=["api"],
        established_by="asserts an accessibility property the browser computes",
        sources_missing=[], proposed_action="Move it.")
    # A title that is not the statement: if the index ever falls back to finding.title, this shows.
    title = "TRUNCATED TITLE THAT MUST NOT BE RENDERED"
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at, summary)"
                 " VALUES (?,?,?,?,?,?,?)",
                 (CASE, RUN, "fixture", "level_fitness", SNAP, TS, "{}"))
    conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                 " VALUES (?,?,?,?,?)", (CASE, title, "high", "e" * 32, db.j([claim_id])))
    conn.commit()

    try:
        body = app.index(conn).decode("utf-8")
        text = _text(body.encode("utf-8"))
        rows, _ = queries.latest_per_analyser(conn)
    finally:
        conn.close()

    assert rows[0]["assertion"] == "the panel"
    assert rows[0]["statement"] == statement
    assert "the panel" in text
    assert title not in text
    assert statement not in text, "the index shows the analyser's essay, not the claim"
    # The whole asserted step, as one piece of anchor text: no truncation, no mid-sentence ending.
    m = re.search(r'<p class="claimtext">(.*?)</p>', body, re.S)
    assert m and htmllib.unescape(m.group(1)).strip() == "the panel"
