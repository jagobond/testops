"""TESTOPS-19: the case opens with the answer, and shows the code it is talking about.

Two findings from the Product Owner, and what each test pins - re-shaped by TESTOPS-23, which
replaced the summary block with one argument paragraph:

- AC1/AC3/AC4: the argument is the first content of the case, quotes the stored step with its
  Gherkin keyword, and ends with the stored proposed action. A claim with no recorded action says
  so rather than inventing one, and no sentence restates the analyser's essay.
- AC5/AC6/AC7/AC8: the asserting step and the step definition that runs it are rendered inline,
  read from the content-addressed blobs, HTML-escaped, with the asserted line marked; a blob this
  store does not hold produces the "recorded but not stored" sentence, never an empty box.
- AC9: rendering is a pure function of the store. A socket that raises is not reached.
- AC10: no claim row is read or written by any of this - the verdict set cannot move. The corpus
  replay is reported with the build; the suite's own store is built under ``tmp_path``.
"""
from __future__ import annotations

import html as htmllib
import re

import pytest
from testops import blobs, queries
from testops.store import db
from testops.web import app

TS = "2020-01-01T00:00:00+00:00"
CASE = "case-summary"
SNAP = "snap-summary"
RUN = "run-summary"
COMMIT = "a" * 40
OTHER_COMMIT = "b" * 40
REPO = "owner/test"
PATH = "features/panel_api.feature"
STEPS = "Steps/PanelSteps.cs"
LINE = 6
BINDING_LINE = 12

FEATURE = """\
Feature: panel API

  Scenario: the panel is served
    Given a panel exists
    When the panel is requested
    Then the panel is served
    And the response is fast

  Scenario: another one
    Given nothing
"""

STEPDEF = """\
using System.Threading.Tasks;

namespace Fixture;

public sealed class PanelSteps
{
    private World World = null!;

    [When("the panel is requested")]
    internal void WhenRequested() => World.Requested = true;

    [Then("the panel is served")]
    internal void ThenPanelServed() =>
        Assert.That(
            World.PanelServed,
            Is.True,
            "the panel was not served");

    [Then("the response is fast")]
    internal void ThenFast() => Assert.That(World.Fast, Is.True);
}
"""

STATEMENT = ("This test asserts that the panel is served. Only the response decides it, and this "
             "test reads that response, so the assertion holds.")
ACTION = 'Call the HTTP client for the step "the panel is served" instead of the browser.'


# --------------------------------------------------------------------------- fixtures

@pytest.fixture(autouse=True)
def _blob_store(tmp_path, monkeypatch):
    """Every blob goes under ``tmp_path``: the real store is never read or written."""
    monkeypatch.setattr(blobs, "BLOB_DIR", tmp_path / "blobs")


def _seed(tmp_path, *, statement=STATEMENT, action=ACTION, schema_version=2,
          feature_text=FEATURE, stepdef_text=STEPDEF, commit=COMMIT, line=LINE,
          binding_line=BINDING_LINE, feature_blob=True, stepdef_blob=True):
    conn = db.connect(tmp_path / "summary.db")
    db.upsert_snapshot(conn, SNAP, "fixture", TS, {REPO: commit},
                       schema_version=schema_version)
    db.start_run(conn, RUN, "fixture", SNAP, "level_fitness", TS)

    fields = {}
    support: list[int] = []
    if schema_version == 2:
        feature_sha = blobs.put(feature_text.encode()) if feature_blob else "0" * 64
        feature_id = db.add_artefact(conn, SNAP, f"github:{REPO}@{commit}:{PATH}", "feature",
                                     feature_sha)
        db.add_observation(conn, feature_id, "gherkin", "1.0.0",
                           "scenario:the panel is served", {"line": 3, "steps": 3})

        step_sha = blobs.put(stepdef_text.encode()) if stepdef_blob else "0" * 64
        step_id = db.add_artefact(conn, SNAP, f"github:{REPO}@{commit}:{STEPS}", "stepdef",
                                  step_sha)
        binding_id = db.add_observation(
            conn, step_id, "stepbinding", "1.0.0", "binding:then:the panel is served",
            {"pattern": "the panel is served", "verb": "Then", "class": "or", "layer": "ui",
             "suite": "panelsteps", "line": binding_line})
        support = [binding_id]
        fields = dict(assertion_text="the panel is served", assertion_path=PATH,
                      assertion_line=line, assertion_commit=commit,
                      interaction_label="needs a browser", interaction_code="I4",
                      span=["ui"], established_by="the words ask what only a browser works out",
                      sources_assessed=True, sources_missing=["jira"],
                      proposed_action=action)

    claim_id = db.add_claim(conn, RUN, "level_fitness", "0.8.0",
                            "scenario:features/panel_api.feature#the panel is served",
                            statement, "gap", 0.5, support,
                            schema_version=schema_version, **fields)
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at,"
                 " summary) VALUES (?,?,?,?,?,?,?)",
                 (CASE, RUN, "fixture", "level_fitness", SNAP, TS, "{}"))
    conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                 " VALUES (?,?,?,?,?)",
                 (CASE, statement[:160], "high", "f" * 32, db.j([claim_id])))
    conn.commit()
    return conn, claim_id


def _text(body: bytes) -> str:
    text = body.decode("utf-8")
    text = re.sub(r"<style>.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<head>.*?</head>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(htmllib.unescape(text).split())


def _html(conn) -> str:
    body = app.case_page(conn, CASE)
    assert body is not None
    return body.decode("utf-8")


# --------------------------------------------------------------------------- AC1

def test_the_argument_is_the_first_content_and_states_the_stored_rows(tmp_path):
    """TESTOPS-26 AC1/AC2: the first content is a scan block with judgement, fault and action.

    It opens with the verdict as a headline, quotes the step the file holds (keyword included)
    once, in monospace, and ends with the stored action on its own line.
    """
    conn, _ = _seed(tmp_path)
    try:
        body = _html(conn)
    finally:
        conn.close()

    scan = re.search(r'<section class="scan">(.*?)</section>', body, re.S)
    assert scan is not None, body[:400]
    block = scan.group(1)
    text = htmllib.unescape(re.sub(r"<[^>]+>", " ", block))
    text = " ".join(text.split())
    assert text.startswith("Not proved"), text
    assert '<code class="ident">Then the panel is served</code>' in block
    assert "What to do" in text
    assert text.endswith("Call the HTTP client for this step instead of the browser."), text
    assert "asserts the same" not in text
    # The block is the first content of section 1, before the evidence sections.
    assert body.index('class="scan"') < body.index('<h2 class="section">2. The step')


def test_the_argument_carries_no_decision_control(tmp_path):
    """Argument first, evidence next, decision last: the form may not ride on one paragraph."""
    conn, _ = _seed(tmp_path)
    try:
        body = _html(conn)
    finally:
        conn.close()
    scan = body.split('class="scan"', 1)[1].split("</section>", 1)[0]
    assert "<form" not in scan and "<button" not in scan


# --------------------------------------------------------------------------- AC2

def test_the_argument_does_not_repeat_the_claim_or_the_analysers_essay(tmp_path):
    """AC1: one argument, said once - the quote appears once in the prose, and not the statement."""
    conn, _ = _seed(tmp_path)
    try:
        body = _html(conn)
        text = _text(body.encode("utf-8"))
    finally:
        conn.close()

    prose = re.sub(r"<pre.*?</pre>", " ", body, flags=re.S)
    prose = htmllib.unescape(re.sub(r"<[^>]+>", " ", prose))
    prose = " ".join(prose.split())
    assert prose.count("Then the panel is served") == 1, prose
    # The stored statement is the analyser's essay; the page argues from the assertion instead.
    assert STATEMENT not in text
    assert "This test asserts that the panel is served." not in text


# --------------------------------------------------------------------------- AC3

def test_a_claim_with_no_action_says_so_and_still_opens_with_the_claim(tmp_path):
    conn, _ = _seed(tmp_path, schema_version=1, action=None)
    try:
        body = _html(conn)
        text = _text(body.encode("utf-8"))
    finally:
        conn.close()

    assert "No proposed action was recorded for this claim." in text
    # The claim as recorded is before the sentence about what is missing.
    assert text.index(STATEMENT) < text.index("No proposed action was recorded for this claim.")
    assert ACTION not in text


# --------------------------------------------------------------------------- AC4

def test_the_verdict_states_what_is_true_and_the_provenance_sits_under_the_quote(tmp_path):
    """AC7/AC3: a label that does not need inverting, and a labelled footnote, not a section."""
    conn, _ = _seed(tmp_path)
    try:
        body = _html(conn)
        text = _text(body.encode("utf-8"))
    finally:
        conn.close()

    assert "Not proved \u2014 nothing runs a browser" in text
    for old in ("Browser not needed", "Never actually proved", "Could not be judged",
                "Established", "Already covered"):
        assert old not in text, old
    assert "Where this comes from:" in text
    assert "2. Where the name came from" not in text
    assert f"features/panel_api.feature:{LINE}" in text
    assert f"{COMMIT[:8]}" in text
    assert "the scenario \u201cthe panel is served\u201d" in text


# --------------------------------------------------------------------------- AC5

def test_the_asserted_step_is_shown_inline_with_its_line_numbers(tmp_path):
    conn, _ = _seed(tmp_path)
    try:
        body = _html(conn)
        text = _text(body.encode("utf-8"))
    finally:
        conn.close()

    snippet = re.search(r'<figure class="snippet">(.*?)</figure>', body, re.S)
    assert snippet is not None
    block = snippet.group(1)
    # ±2 lines around line 6: 4..8, each with its own number.
    for number in range(4, 9):
        assert f'<span class="ln">{number}</span>' in block, number
    assert '<span class="sline hit"><span class="ln">6</span><mark class="hit">' in block
    assert "Then the panel is served" in text
    assert "Given a panel exists" in text          # context, before
    assert "And the response is fast" in text       # context, after
    assert "Scenario: another one" not in text      # outside ±2
    assert "view in repository" in text
    assert f"features/panel_api.feature:{LINE}" in text


def test_the_asserted_step_is_read_at_the_claims_own_commit(tmp_path):
    """A file at another commit is not this claim's evidence, even if the path matches."""
    conn, _ = _seed(tmp_path)
    try:
        # Same path, different commit, different content - the decoy that a suffix match would take.
        decoy = blobs.put(b"Feature: wrong\n\n  Scenario: wrong\n    Then the panel is served\n")
        db.add_artefact(conn, SNAP, f"github:{REPO}@{OTHER_COMMIT}:{PATH}", "feature", decoy)
        conn.commit()
        body = _html(conn)
    finally:
        conn.close()
    assert "Scenario: wrong" not in body
    assert "When the panel is requested" in body


# --------------------------------------------------------------------------- AC6

def test_the_step_definition_body_is_shown_and_marked_as_the_step_asserted(tmp_path):
    conn, _ = _seed(tmp_path)
    try:
        body = _html(conn)
        text = _text(body.encode("utf-8"))
    finally:
        conn.close()

    figures = re.findall(r'<figure class="snippet">(.*?)</figure>', body, re.S)
    assert len(figures) == 2, len(figures)
    step_definition = figures[1]
    assert "The step definition that runs it:" in text
    assert f"{STEPS}:{BINDING_LINE}" in text
    assert (f'<span class="sline hit"><span class="ln">{BINDING_LINE}</span>'
            f'<mark class="hit">' in step_definition)
    assert '[Then(&quot;the panel is served&quot;)]' in step_definition
    assert "internal void ThenPanelServed()" in text
    assert "the panel was not served" in text
    # The next step is not part of this body.
    assert "ThenFast" not in text


# --------------------------------------------------------------------------- AC7

def test_markup_in_the_sources_renders_as_text_in_both_snippets(tmp_path):
    hostile_feature = FEATURE.replace("Given a panel exists",
                                      'Given a <script>alert("feature")</script> exists')
    hostile_steps = STEPDEF.replace('"the panel was not served"',
                                    '"<script>alert(\'stepdef\')</script>"')
    conn, _ = _seed(tmp_path, feature_text=hostile_feature, stepdef_text=hostile_steps)
    try:
        body = _html(conn)
    finally:
        conn.close()

    assert "<script" not in body.lower()
    assert body.count("&lt;script&gt;") >= 2, "both snippets must escape their content"
    assert 'alert(&quot;feature&quot;)' in body
    assert "alert(&#x27;stepdef&#x27;)" in body
    assert 'alert("feature")' in _text(body.encode("utf-8"))


# --------------------------------------------------------------------------- AC8

def test_a_missing_blob_says_recorded_but_not_stored(tmp_path):
    conn, _ = _seed(tmp_path, feature_blob=False, stepdef_blob=False)
    try:
        body = _html(conn)
        text = _text(body.encode("utf-8"))
    finally:
        conn.close()

    assert "The source was recorded but its content is not in this store" in text
    assert text.count("The source was recorded but its content is not in this store") == 2
    assert "<pre class=\"snippet\"><code></code></pre>" not in body


def test_a_missing_blob_does_not_raise(tmp_path):
    conn, claim_id = _seed(tmp_path, feature_blob=False)
    try:
        # The read model answers, and names the absence rather than throwing at render time.
        claim = queries.claim_read(conn, claim_id)
        assert claim is not None
        assert claim["snippets"]["assertion"]["state"] == queries.SNIPPET_NOT_STORED
    finally:
        conn.close()


# --------------------------------------------------------------------------- AC9

def test_rendering_the_page_opens_no_socket(tmp_path, monkeypatch):
    import socket

    def refuse(*_args, **_kwargs):
        raise AssertionError("the case page attempted network access at render time")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    conn, _ = _seed(tmp_path)
    try:
        body = app.case_page(conn, CASE)
    finally:
        conn.close()
    assert body is not None
    assert b"the panel is served" in body
