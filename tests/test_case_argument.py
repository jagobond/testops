"""TESTOPS-23: the page tells the reader one argument, and these are the faults it removed.

The Product Owner read ``case-cotw-levels-20261122T011316-03`` and said "the verbiage is still not
right, but I'm not quite sure how to explain why yet". The ticket names seven faults; this module
pins each one, and then runs the prose lint the ticket defines over every claim of a real run.

The lint's rules, as AC1 and AC8 state them:

  1. no assertion text repeated across sections - the quoted step, keyword included, appears once in
     prose (snippet and figure content is evidence, not prose, and is excluded)
  2. no sentence containing "the words" - the analyser's view of the assertion is never the subject
  3. no fragment pseudo-headings - no paragraph opened by a bold label, and none of the old labels
     ("What settles it.", "Why it was classified this way:")
  4. one term for the test throughout - "the test", never "the run" doing the test's work
  5. no verdict label that states an absence - the old vocabulary appears nowhere on the page
  6. context lines are introduced as a group and kept out of the evidence section
  7. no reader-facing sentence refers to the analyser, its rules, its vocabulary or its process
  8. no double space, and no sentence longer than 45 words

The corpus check runs over a store built by the real pipeline in ``tmp_path``; the verdict matrix
seeds one case per verdict so the rules that only one verdict reaches are exercised too. Neither
reads the product's ``data/testops.db``, so a re-run of an analyser cannot change the result.
"""
from __future__ import annotations

import html as htmllib
import re
from typing import Any

import level_fixtures as fixtures
import pytest
from testops import blobs, queries
from testops.store import db
from testops.web import app

TS = "2020-01-01T00:00:00+00:00"
CASE = "case-argument"
SNAP = "snap-argument"
RUN = "run-argument"
REPO = "owner/test"
COMMIT = "a" * 40
PATH = "features/panel_api.feature"
STEPS = "Steps/PanelSteps.cs"
LINE = 6
BINDING_LINE = 6
OTHER_BINDING_LINE = 3

FEATURE = """\
Feature: panel API

  Scenario: the panel is served
    Given a panel exists
    When the panel is requested
    Then the panel is served
"""

STEPDEF = """\
public sealed class PanelSteps
{
    [When("the panel is requested")]
    internal void WhenRequested() => World.Requested = true;

    [Then("the panel is served")]
    internal void ThenPanelServed() => Assert.That(World.PanelServed, Is.True);
}
"""

ACTION = 'Call the HTTP client for the step "the panel is served" instead of the browser.'

# The verdict vocabulary the ticket replaces (AC7). None of it may reach the page.
RETIRED = ("Browser not needed", "Never actually proved", "Could not be judged", "Established",
           "Already covered", "Need a browser", "Not needed")

# Phrases that only make sense from inside the analyser (AC5, faults 3 and 5).
BANNED = ("the words", "classified this way", "the analyser", "the assertion is about",
          "answers to one run", "which instrument read", "the rule that", "this run only reads",
          "the run only reads", "the run drives", "the run opens")

VERDICTS = {
    # verdict, label, code, span, verdict label the reader must meet
    "distinct": ("settled by the response the server sends", "I1", ["api"], "Checked"),
    "review": ("settled by the page the server sends", "KP", ["ui"],
               "Checked, but over-tested for what it asserts"),
    "gap": ("needs a browser", "I4", ["api"], "Not proved \u2014 nothing runs a browser"),
    "unplaced": ("unclear what would settle it", "U", ["api"], "Cannot tell"),
    "duplicate": ("settled by the application's own controllers in-process", None, ["controller"],
                  "Checked, but this repeats another test"),
}


# --------------------------------------------------------------------------- prose, and the lint

def prose(html: str) -> str:
    """The reader's words: markup, styles and code excerpts removed; whitespace left alone.

    Code is excluded on purpose. A snippet is the source the claim is about, not a sentence the page
    wrote, and counting the asserted line there would make "quoted once" unsatisfiable.
    """
    text = re.sub(r"<style>.*?</style>", " ", html, flags=re.S)
    text = re.sub(r"<head>.*?</head>", " ", text, flags=re.S)
    text = re.sub(r"<pre.*?</pre>", " ", text, flags=re.S)
    text = re.sub(r"<figure.*?</figure>", " ", text, flags=re.S)
    text = re.sub(r"</(h1|h2|h3|p|li|blockquote|section|div|main)>", "\n", text)
    text = re.sub(r"<(h1|h2|h3|p|li|blockquote|section|div|main)[^>]*>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return htmllib.unescape(text)


def sentences(text: str) -> list[str]:
    flat = " ".join(line.strip() for line in text.splitlines() if line.strip())
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", flat) if part.strip()]


def lint(html: str, *, quoted: str | None = None) -> list[str]:
    """Every problem the ticket's lint finds on one rendered case page."""
    text = prose(html)
    problems: list[str] = []
    lower = text.lower()

    for phrase in BANNED:
        if phrase in lower:
            problems.append(f"analyser narration: {phrase!r}")

    for line in text.splitlines():
        if "  " in line.strip():
            problems.append(f"double space: {line!r}")
    for sentence in sentences(text):
        words = len(sentence.split())
        if words > 45:
            problems.append(f"a {words}-word sentence: {sentence!r}")

    if quoted:
        count = " ".join(text.split()).count(quoted)
        if count > 1:
            problems.append(f"the assertion is quoted {count} times: {quoted!r}")

    for old in RETIRED:
        if old in text:
            problems.append(f"retired verdict label: {old!r}")

    # A label wearing a sentence's clothes: "<p><strong>What settles it.</strong> ...".
    if re.search(r"<p[^>]*><strong>[^<]{0,80}(\.|:)</strong>", html):
        problems.append("fragment pseudo-heading")

    return problems


def case_text(conn, case_id: str = CASE) -> tuple[str, str]:
    body = app.case_page(conn, case_id)
    assert body is not None
    html = body.decode("utf-8")
    return html, prose(html)


# --------------------------------------------------------------------------- store fixture

def _seed(tmp_path, monkeypatch, *, verdict="review", label=None, code=None, span=None,
          action=ACTION, statement=None, sources_assessed=True, missing=(), schema_version=2):
    monkeypatch.setattr(blobs, "BLOB_DIR", tmp_path / "blobs")
    conn = db.connect(tmp_path / "argument.db")
    db.upsert_snapshot(conn, SNAP, "fixture", TS, {REPO: COMMIT}, schema_version=schema_version)
    db.start_run(conn, RUN, "fixture", SNAP, "level_fitness", TS)

    default_label, default_code, default_span, _word = VERDICTS.get(
        verdict, VERDICTS["review"])
    label = default_label if label is None else label
    code = default_code if code is None else code
    span = default_span if span is None else span
    statement = statement or ("The run only reads the responses the server sends, so the assertion "
                              "is checked as far as that answer speaks for the page.")

    fields: dict[str, Any] = {}
    support: list[int] = []
    if schema_version == 2:
        feature_id = db.add_artefact(conn, SNAP, f"github:{REPO}@{COMMIT}:{PATH}", "feature",
                                     blobs.put(FEATURE.encode()))
        db.add_observation(conn, feature_id, "gherkin", "1.0.0", "scenario:the panel is served",
                           {"line": 3, "steps": 3})
        step_id = db.add_artefact(conn, SNAP, f"github:{REPO}@{COMMIT}:{STEPS}", "stepdef",
                                  blobs.put(STEPDEF.encode()))
        other = db.add_observation(
            conn, step_id, "stepbinding", "1.0.0", "binding:when:the panel is requested",
            {"pattern": "the panel is requested", "verb": "When", "class": "PanelSteps",
             "layer": span[0], "suite": "panelsteps", "line": OTHER_BINDING_LINE})
        asserting = db.add_observation(
            conn, step_id, "stepbinding", "1.0.0", "binding:then:the panel is served",
            {"pattern": "the panel is served", "verb": "Then", "class": "PanelSteps",
             "layer": span[0], "suite": "panelsteps", "line": BINDING_LINE})
        support = [asserting, other]
        fields = dict(assertion_text="the panel is served", assertion_path=PATH,
                      assertion_line=LINE, assertion_commit=COMMIT,
                      interaction_label=label, interaction_code=code, span=list(span),
                      established_by="the words name the page as served",
                      sources_assessed=sources_assessed,
                      sources_missing=list(missing) if sources_assessed else None,
                      proposed_action=action)

    claim_id = db.add_claim(conn, RUN, "level_fitness", "0.8.0",
                            "scenario:features/panel_api.feature#the panel is served",
                            statement, verdict, 0.5, support,
                            schema_version=schema_version, **fields)
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at,"
                 " summary) VALUES (?,?,?,?,?,?,?)",
                 (CASE, RUN, "fixture", "level_fitness", SNAP, TS, "{}"))
    conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                 " VALUES (?,?,?,?,?)",
                 (CASE, statement[:160], "high", "f" * 32, db.j([claim_id])))
    conn.commit()
    return conn, claim_id


# --------------------------------------------------------------------------- the seven faults

def test_the_claim_is_quoted_once_and_there_is_no_summary_block(tmp_path, monkeypatch):
    """Fault 1: quoted, restated, paraphrased. Now: one quote, one sentence about it."""
    conn, _ = _seed(tmp_path, monkeypatch)
    try:
        html, text = case_text(conn)
    finally:
        conn.close()

    assert 'class="summary"' not in html
    assert ("The test asserts the step \u201cThen the panel is served\u201d." in text)
    assert " ".join(text.split()).count("Then the panel is served") == 1
    # The analyser's essay, which restated the claim and the rule, is gone from the page.
    assert "The run only reads the responses the server sends" not in text


def test_provenance_is_a_labelled_footnote_under_the_quote_not_a_section(tmp_path, monkeypatch):
    """Fault 2: a numbered section about the name of a heading, between claim and reason."""
    conn, _ = _seed(tmp_path, monkeypatch)
    try:
        html, text = case_text(conn)
    finally:
        conn.close()

    assert "Where the name came from" not in text
    quote_at = html.index('class="argument"')
    provenance_at = html.index('class="meta provenance"')
    next_section = html.index('<h2 class="section">2.')
    assert quote_at < provenance_at < next_section
    assert f"features/panel_api.feature:{LINE}" in text
    assert "at commit aaaaaaaa" in text
    assert "the scenario \u201cthe panel is served\u201d" in text


def test_no_sentence_talks_about_the_words_or_the_classification(tmp_path, monkeypatch):
    """Faults 3 and 5: the sentence was the analyser's view, not the test's."""
    conn, _ = _seed(tmp_path, monkeypatch)
    try:
        html, text = case_text(conn)
    finally:
        conn.close()

    assert "the words" not in text
    assert "Why it was classified this way" not in text
    assert "the words name the page as served" not in text
    # What the rule found is stated as a fact about the claim.
    assert "That is settled by the page the server sends" in text


def test_no_fragment_pseudo_headings(tmp_path, monkeypatch):
    """Fault 4: "What settles it." and "Why it was classified this way:" as labels."""
    conn, _ = _seed(tmp_path, monkeypatch)
    try:
        html, text = case_text(conn)
    finally:
        conn.close()

    assert not re.search(r"<p[^>]*><strong>[^<]{0,80}(\.|:)</strong>", html)
    assert "What settles it." not in text


def test_the_test_is_called_the_test_throughout(tmp_path, monkeypatch):
    """Fault 5: "It drives", "the run drives", "the run only reads" - three names for one actor."""
    conn, _ = _seed(tmp_path, monkeypatch)
    try:
        _html, text = case_text(conn)
    finally:
        conn.close()

    assert "and the test drives a browser" in text
    assert "the run drives" not in text
    assert "the run only reads" not in text
    assert "It drives a browser." not in text


@pytest.mark.parametrize("verdict", sorted(VERDICTS))
def test_the_verdict_label_states_what_is_true(tmp_path, monkeypatch, verdict):
    """Fault 6 and AC7: a label a reader can act on, never a negation to invert."""
    conn, _ = _seed(tmp_path, monkeypatch, verdict=verdict)
    try:
        _html, text = case_text(conn)
    finally:
        conn.close()

    assert VERDICTS[verdict][3] in text
    for old in RETIRED:
        assert old not in text, old
    # The shorthand survives, in the footnote, with its code.
    assert "Debugging shorthand" in text


def test_context_steps_are_introduced_together_and_kept_out_of_the_evidence(tmp_path, monkeypatch):
    """Fault 7: four observation lines, three of them context, all at equal weight."""
    conn, _ = _seed(tmp_path, monkeypatch)
    try:
        html, text = case_text(conn)
    finally:
        conn.close()

    assert "These are the other steps in the same scenario" in text
    assert "They are not evidence for this claim" in text
    context = html.split('<h2 class="section">3.', 1)[1]
    assert '<ul class="ev context">' in context
    # The asserting step's own definition is section 2's evidence, not a bullet in section 3.
    assert "The step definition that runs it:" in html
    items = re.findall(r"<li>(.*?)</li>", context, re.S)
    assert items
    assert all("step definition for \u201cthe panel is served\u201d" not in item for item in items), items
    # The shared instrument is said once, not repeated at the end of every line.
    assert "each of them uses a browser" in text
    assert "that drives a browser" not in text


# --------------------------------------------------------------------------- AC1/AC8: the lint

def test_every_verdict_passes_the_prose_lint(tmp_path, monkeypatch):
    for verdict in sorted(VERDICTS):
        conn, claim_id = _seed(tmp_path / verdict, monkeypatch, verdict=verdict)
        try:
            claim = queries.claim_read(conn, claim_id)
            body = app.case_page(conn, CASE)
            assert body is not None
            html = body.decode("utf-8")
        finally:
            conn.close()
        assert lint(html, quoted=app.quoted_assertion(claim or {})) == [], verdict


def test_every_claim_of_a_real_run_passes_the_lint(tmp_path, monkeypatch):
    """AC8: the lint runs over every claim a real pipeline run wrote, not a hand-made row."""
    from testops import pipeline
    from testops.config import Project, Repo

    path, connect = fixtures.stub_pipeline(monkeypatch, pipeline, tmp_path)
    project = Project(key="fixture", product=Repo("o", "product"), test=Repo("o", "tests"),
                      jira_key="")
    pipeline.run_level_fitness(project, token="unused")
    conn = connect(path)
    try:
        rows = conn.execute("SELECT id, assertion_text FROM claim ORDER BY id").fetchall()
        assert rows, "the pipeline run wrote no claims"
        pages = []
        for row in rows:
            # One page per claim, including the distinct ones that raise no case: this store is
            # under tmp_path, so wrapping a claim in a case here cannot touch a product artefact.
            context = conn.execute(
                "SELECT c.run_id, c.analyser, r.snapshot_id FROM claim c"
                " JOIN run r ON r.id = c.run_id WHERE c.id = ?", (row["id"],)).fetchone()
            case_id = f"lint-{row['id']}"
            conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id,"
                         " created_at, summary) VALUES (?,?,?,?,?,?,?)",
                         (case_id, context["run_id"], "fixture", context["analyser"],
                          context["snapshot_id"], TS, "{}"))
            conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                         " VALUES (?,?,?,?,?)",
                         (case_id, "lint", "high", f"{row['id']:032d}",
                          db.j([row["id"]])))
            conn.commit()
            claim = queries.claim_read(conn, row["id"])
            body = app.case_page(conn, case_id)
            assert body is not None
            pages.append((row["assertion_text"], body.decode("utf-8"),
                          app.quoted_assertion(claim or {})))
        index = app.index(conn).decode("utf-8")
    finally:
        conn.close()

    assert len(pages) >= 2
    for assertion, html, quoted in pages:
        assert lint(html, quoted=quoted) == [], assertion
    # The home list says what each claim asserts; it is not a third place for the analyser's essay.
    assert lint(index) == []
    assert "The run only reads" not in index