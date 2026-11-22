"""TESTOPS-26: the summary is three lines a reader can scan.

The Product Owner asked for a finding statement and a proposed solution at the top, so a reader can
decide whether the case is worth their time. This module pins the shape of that block, the copy
rules around it, and runs the plain-English lint over every claim of a real run.

The corpus check has two arms. One drives the real pipeline over the fixture repository, so it is
deterministic and does not read the product's store. The other runs the same lint over the stored
cotw run (94 claims, 90 distinct / 1 unplaced / 1 gap / 2 review) when that store is present; it is
skipped in a clean checkout, because the store is a build artefact and not part of the repository.
"""
from __future__ import annotations

import html as htmllib
import re
import shutil
import sqlite3
from pathlib import Path
from typing import Any

import level_fixtures as fixtures
import pytest
from testops import blobs, queries
from testops.store import db
from testops.web import app
from testops.web import lint as english

ROOT = Path(__file__).resolve().parents[1]
STORED = ROOT / "data" / "testops.db"
STEPS = "Steps/PanelSteps.cs"

TS = "2020-01-01T00:00:00+00:00"
CASE = "case-scan"
SNAP = "snap-scan"
RUN = "run-scan"
REPO = "owner/test"
COMMIT = "a" * 40
PATH = "features/panel_api.feature"
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
NO_CHANGE = ('No change: keep the step "the panel is served" where it is; this level is the '
             'cheapest one that establishes it.')

VERDICTS = {
    "distinct": ("settled by the response the server sends", "I1", ["api"], "Checked"),
    "review": ("settled by the page the server sends", "KP", ["ui"],
               "Checked, but over-tested for what it asserts"),
    "gap": ("needs a browser", "I4", ["api"], "Not proved \\u2014 nothing runs a browser"),
    "unplaced": ("unclear what would settle it", "U", ["api"], "Cannot tell"),
}
SCAN = 'class="scan"'


def _seed(tmp_path, monkeypatch, verdict="review"):
    monkeypatch.setattr(blobs, "BLOB_DIR", tmp_path / "blobs")
    conn = db.connect(tmp_path / f"{verdict}.db")
    db.upsert_snapshot(conn, SNAP, "fixture", TS, {REPO: COMMIT}, schema_version=2)
    db.start_run(conn, RUN, "fixture", SNAP, "level_fitness", TS)

    label, code, span, _ = VERDICTS[verdict]
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

    fields: dict[str, Any] = dict(assertion_text="the panel is served", assertion_path=PATH,
                  assertion_line=LINE, assertion_commit=COMMIT,
                  interaction_label=label, interaction_code=code, span=list(span),
                  established_by="the words name the page as served",
                  sources_assessed=True, sources_missing=[],
                  proposed_action=(NO_CHANGE if verdict == "distinct" else ACTION))
    claim_id = db.add_claim(conn, RUN, "level_fitness", "0.8.0",
                            "scenario:features/panel_api.feature#the panel is served",
                            "The run only reads the response the server sends, so the assertion is "
                            "checked.", verdict, 0.5, [asserting, other], schema_version=2,
                            **fields)
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at,"
                 " summary) VALUES (?,?,?,?,?,?,?)",
                 (CASE, RUN, "fixture", "level_fitness", SNAP, TS, "{}"))
    conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                 " VALUES (?,?,?,?,?)",
                 (CASE, "scan", "high", "f" * 32, db.j([claim_id])))
    conn.commit()
    return conn, claim_id


def _render(conn) -> str:
    body = app.case_page(conn, CASE)
    assert body is not None
    return body.decode("utf-8")


def _block(html: str) -> str:
    match = re.search(r'<section class="scan">(.*?)</section>', html, re.S)
    assert match is not None, html[:400]
    return match.group(1)


def _plain(fragment: str) -> str:
    return " ".join(htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


# --------------------------------------------------------------------------- AC1

def test_the_scan_block_is_a_headline_a_fault_and_an_action(tmp_path, monkeypatch):
    conn, _ = _seed(tmp_path, monkeypatch)
    try:
        html = _render(conn)
    finally:
        conn.close()

    block = _block(html)
    assert '<p class="judgement"><strong class="verdict hot">Checked, but over-tested for what ' \
           'it asserts</strong></p>' in block
    assert '<p class="wrong">' in block and block.index('class="wrong"') < block.index(
        'class="action"')
    assert '<p class="action"><span class="act">What to do</span>' in block
    # The headline is a judgement, not the category "review".
    assert ">review<" not in block


# --------------------------------------------------------------------------- AC2

def test_the_step_is_quoted_once_in_monospace_and_the_action_points_at_it(tmp_path, monkeypatch):
    conn, _ = _seed(tmp_path, monkeypatch)
    try:
        html = _render(conn)
    finally:
        conn.close()

    block = _block(html)
    text = _plain(block)
    assert '<code class="ident">Then the panel is served</code>' in block
    assert text.count("Then the panel is served") == 1, text
    action = re.search(r'<p class="action">(.*?)</p>', block, re.S)
    assert action is not None
    action_text = _plain(action.group(1))
    assert "this step" in action_text
    assert "the panel is served" not in action_text
    assert action_text == ("What to do Call the HTTP client for this step instead of the browser.")


# --------------------------------------------------------------------------- AC3

@pytest.mark.parametrize("verdict", sorted(VERDICTS))
def test_no_clause_of_six_words_repeats_inside_the_block(tmp_path, monkeypatch, verdict):
    conn, _ = _seed(tmp_path / verdict, monkeypatch, verdict=verdict)
    try:
        html = _render(conn)
    finally:
        conn.close()
    assert english.repeated_clause(english.opening_block(html)) is None


# --------------------------------------------------------------------------- AC4

def test_identifiers_render_in_monospace_everywhere(tmp_path, monkeypatch):
    conn, _ = _seed(tmp_path, monkeypatch)
    try:
        html = _render(conn)
    finally:
        conn.close()
    block = _block(html)
    assert '<code class="ident">HTTP client</code>' in block
    assert english.bare_identifiers(html, "Then the panel is served") == []


# --------------------------------------------------------------------------- AC5

@pytest.mark.parametrize("verdict", sorted(VERDICTS))
def test_one_typographic_quote_style(tmp_path, monkeypatch, verdict):
    conn, _ = _seed(tmp_path / verdict, monkeypatch, verdict=verdict)
    try:
        html = _render(conn)
    finally:
        conn.close()
    assert english.straight_quotes(html) == []


# --------------------------------------------------------------------------- AC7

@pytest.mark.parametrize("verdict", ["distinct", "review", "gap", "unplaced"])
def test_every_verdict_renders_an_action_line(tmp_path, monkeypatch, verdict):
    conn, claim_id = _seed(tmp_path / verdict, monkeypatch, verdict=verdict)
    try:
        html = _render(conn)
        claim = queries.claim_read(conn, claim_id)
    finally:
        conn.close()

    block = _block(html)
    assert english.lint(html, app.quoted_assertion(claim or {})) == []
    assert verdict == claim["verdict"]
    action = re.search(r'<p class="action">.*?</p>', block, re.S)
    assert action is not None, verdict
    match = re.match(r'<p class="action"><span class="act">What to do</span>(.*?)</p>',
                     action.group(0), re.S)
    assert match is not None
    text = match.group(1)
    assert _plain(text).endswith("."), (verdict, text)
    if verdict == "distinct":
        assert "No change" in text


# --------------------------------------------------------------------------- AC10

def test_punctuation_follows_a_code_span_with_no_space_between(tmp_path, monkeypatch):
    conn, _ = _seed(tmp_path, monkeypatch)
    try:
        html = _render(conn)
    finally:
        conn.close()

    assert '</code> ,' not in html
    assert '</code> .' not in html
    assert english.detached_punctuation(html) == []
    # The page does put the comma straight after the quoted step, which is the sentence AC10 saw.
    assert 'the panel is served</code>, but' in html


def test_the_punctuation_check_catches_a_detached_comma():
    problems = english.detached_punctuation('<p>The ids are stable</code> , but the page differs.</p>')
    assert problems == ["a space between a code span and ','"]


def _em_values(declaration: str) -> list[float]:
    """``padding:.05em .25em`` as four numbers, expanded the way CSS expands a shorthand."""
    values = [float(value.removesuffix("em")) for value in declaration.split()]
    if len(values) == 2:
        return [values[0], values[1], values[0], values[1]]
    return values


def test_the_code_span_paints_no_space_between_it_and_that_punctuation():
    """AC10 is a defect of the painted page: the span's horizontal padding was the gap.

    The markup never held a space, so the punctuation check alone would have passed on the broken
    page. This is the other half: whatever horizontal padding the span paints is cancelled by an
    equal negative margin, so a comma written against the span sits against its last glyph.
    """
    rule = re.search(r"code\.ident \{(.*?)\}", app.CSS, re.S)
    assert rule is not None
    padding = re.search(r"padding:([^;]+);", rule.group(1))
    margin = re.search(r"margin:([^;]+);", rule.group(1))
    assert padding is not None and margin is not None, rule.group(1)
    p_right, p_left = _em_values(padding.group(1))[1::2]
    m_right, m_left = _em_values(margin.group(1))[1::2]
    assert p_right == -m_right != 0, (p_right, m_right)
    assert p_left == -m_left != 0, (p_left, m_left)


# --------------------------------------------------------------------------- AC6

@pytest.mark.parametrize("word", sorted(english.BANNED))
def test_the_plain_english_lint_rejects_each_forbidden_word(word):
    assert english.plain_english(f"The step is {word} to read."), word


def test_the_plain_english_lint_rejects_a_sentence_over_45_words():
    long = " ".join(["word"] * 46) + "."
    assert any("46-word sentence" in problem for problem in english.plain_english(long))


def test_an_identifier_left_in_prose_fails_the_lint():
    html = ('<p class="wrong">The test drives HTTP client and reads data-fact-id.</p>'
            '<p class="action">Rewrite this step.</p>')
    problems = english.lint(html, None)
    assert any("HTTP client" in problem for problem in problems)
    assert any("data-fact-id" in problem for problem in problems)


def test_plain_english_lint_over_every_claim_of_a_real_pipeline_run(tmp_path, monkeypatch):
    """The lint runs on pages the real pipeline wrote, not on a hand-seeded row."""
    from testops import pipeline
    from testops.config import Project, Repo

    path, connect = fixtures.stub_pipeline(monkeypatch, pipeline, tmp_path)
    project = Project(key="fixture", product=Repo("o", "product"), test=Repo("o", "tests"),
                      jira_key="")
    pipeline.run_level_fitness(project, token="unused")
    conn = connect(path)
    try:
        rows = conn.execute("SELECT id, assertion_text FROM claim ORDER BY id").fetchall()
        assert rows
        checked = 0
        for row in rows:
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
                         (case_id, "lint", "high", f"{row['id']:032d}", db.j([row["id"]])))
            conn.commit()
            claim = queries.claim_read(conn, row["id"])
            html = app.case_page(conn, case_id).decode("utf-8")
            step = app.quoted_assertion(claim or {})
            assert english.plain_english(english.reader_text(html)) == [], row["assertion_text"]
            assert english.lint(html, step) == [], row["assertion_text"]
            checked += 1
    finally:
        conn.close()
    assert checked >= 2


@pytest.mark.skipif(not STORED.exists(), reason="the product store is a build artefact")
def test_no_action_on_the_real_run_is_cut_into_a_stub():
    """TESTOPS-27 AC4: no action is truncated below 40 characters unless the whole action was.

    What is measured is the cut. The stored string is the corpus, and the cut is what the page does
    to it, so the floor is on the part of the stored action the page keeps: a cut that leaves
    "Move the step." or "Keep it." gives the reader half an instruction, and that is the failure
    the ticket exists for. The 94-claim run keeps 53 to 175 characters in every case, and
    never fewer than 40.

    The page also refers to the step as "this step", because the step itself is quoted directly
    above the action. That is a reference, not a truncation: the assertion below shows the line the
    reader gets is the whole kept head with the step's own words swapped for the reference, so the
    shortening is exactly the length of the step. That is why 90 of the 94 actions read "No change:
    keep this step where it is." - 38 characters, all of them the stored head. Where the page did
    not shorten by reference, the floor is applied to the reader's own text as well.

    The run is the one the neighbouring test pins, so a re-run of the analyser cannot move it.
    """
    conn = sqlite3.connect(f"file:{STORED.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        run = conn.execute(
            "SELECT run_id FROM claim WHERE analyser = 'level_fitness'"
            " GROUP BY run_id ORDER BY COUNT(*) DESC, run_id DESC LIMIT 1").fetchone()["run_id"]
        checked = 0
        for row in conn.execute("SELECT id FROM claim WHERE run_id = ? ORDER BY id", (run,)):
            claim = queries.claim_read(conn, row["id"]) or {}
            whole = (claim.get("proposed_action") or "").strip()
            if not whole:
                continue
            kept = whole.partition("; ")[0].strip()
            visible = app.action_line(claim, app.quoted_assertion(claim))
            where = f"{claim.get('assertion_text')!r} in run {run}"
            assert len(whole) < 40 or len(kept) >= 40, (
                f"the action was cut to {len(kept)} characters: kept {kept!r} out of {whole!r} "
                f"({where})")
            # Where the page shortened by reference, prove the reference is the only shortening:
            # the reader's line is the whole kept head with the step's own words swapped out.
            if "this step" in visible:
                step = (claim.get("provenance") or {}).get("assertion_text") or ""
                quoted = 'the step "%s"' % step
                assert quoted in kept, (
                    f"the page referred away a step the head does not quote: {kept!r}")
                assert visible == kept.replace(quoted, "this step").rstrip(".") + ".", (
                    f"the page shortened more than the step's own words: {visible!r} from {kept!r}")
            # An action the page did not shorten by reference is held to the floor as the reader
            # meets it, too.
            else:
                assert len(visible) >= 40, (
                    f"the reader's action is {len(visible)} characters: {visible!r} ({where})")
            checked += 1
    finally:
        conn.close()
    assert checked >= 90, f"the corpus held only {checked} actions"


@pytest.mark.skipif(not STORED.exists(), reason="the product store is a build artefact")
def test_the_real_tails_still_drop_before_and_after_the_morphology_fix():
    """TESTOPS-27 AC9: the morphology fix must not turn the real corpus into kept noise.

    Measured on the pinned 94-claim run: every stored action has a tail after ``"; "``, and every
    one of those tails is a restatement. The test runs two rules over the same 94 strings - the
    bare-stem rule that was there before this change (``_bare_stem_drop``, kept here as the
    before) and the rule the page uses now (the after) - and demands the same count from both. The
    vocabulary in the stored tails is real: ``is being used`` and ``cannot be checked`` are
    participles of instruction verbs, and a rule that counted any inflection anywhere would keep
    them. Under that rule the drop count falls; under this one it does not, and the verdicts stay
    94 claims / 90 distinct / 1 unplaced / 1 gap / 2 review.
    """
    def _bare_stem_drop(tail: str) -> bool:
        words = app._words(tail)
        if not words:
            return True
        if words[0] not in app.CONTINUATION_OPENERS:
            return False
        return not any(word in app.INSTRUCTION_VERBS for word in words[1:])

    conn = sqlite3.connect(f"file:{STORED.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        run = conn.execute(
            "SELECT run_id FROM claim WHERE analyser = 'level_fitness'"
            " GROUP BY run_id ORDER BY COUNT(*) DESC, run_id DESC LIMIT 1").fetchone()["run_id"]
        counts = {row["verdict"]: row["n"] for row in conn.execute(
            "SELECT verdict, COUNT(*) AS n FROM claim WHERE run_id = ? GROUP BY verdict", (run,))}
        tails, before, after, kept_any = [], 0, 0, []
        for row in conn.execute("SELECT id FROM claim WHERE run_id = ? ORDER BY id", (run,)):
            claim = queries.claim_read(conn, row["id"]) or {}
            whole = (claim.get("proposed_action") or "").strip()
            head, sep, tail = whole.partition("; ")
            if not sep or not tail.strip():
                continue
            tail = tail.strip()
            tails.append(tail)
            before += _bare_stem_drop(tail)
            if app.second_half_is_instruction(tail):
                kept_any.append(tail)
            else:
                after += 1
    finally:
        conn.close()

    assert len(tails) == 94, f"the pinned run holds {len(tails)} tails, not 94"
    assert (before, after) == (94, 94), (
        f"drop counts moved with the morphology fix: before {before} dropped, after {after}; "
        f"kept tails were {sorted(set(kept_any))!r}")
    assert not kept_any, f"the fix kept {len(kept_any)} real tails: {sorted(set(kept_any))!r}"
    assert counts == {"distinct": 90, "unplaced": 1, "gap": 1, "review": 2}, counts


@pytest.mark.skipif(not STORED.exists(), reason="the product store is a build artefact")
def test_the_stored_cotw_corpus_keeps_its_verdicts_and_passes_the_lint(tmp_path, monkeypatch):
    """The real 94-claim run: same verdict counts, every page through the same lint."""
    copy = tmp_path / "corpus.db"
    shutil.copyfile(STORED, copy)
    monkeypatch.setattr(blobs, "BLOB_DIR", ROOT / "data" / "blobs")
    conn = sqlite3.connect(copy)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        run = conn.execute(
            "SELECT run_id FROM claim WHERE analyser = 'level_fitness'"
            " GROUP BY run_id ORDER BY COUNT(*) DESC, run_id DESC LIMIT 1").fetchone()["run_id"]
        counts = {row["verdict"]: row["n"] for row in conn.execute(
            "SELECT verdict, COUNT(*) AS n FROM claim WHERE run_id = ? GROUP BY verdict", (run,))}
        assert counts == {"distinct": 90, "unplaced": 1, "gap": 1, "review": 2}, (run, counts)

        for i, row in enumerate(conn.execute(
                "SELECT id FROM claim WHERE run_id = ? ORDER BY id", (run,))):
            case_id = f"probe-{row['id']}"
            context = conn.execute(
                "SELECT c.run_id, c.analyser, r.snapshot_id FROM claim c"
                " JOIN run r ON r.id = c.run_id WHERE c.id = ?", (row["id"],)).fetchone()
            conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id,"
                         " created_at, summary) VALUES (?,?,?,?,?,?,?)",
                         (case_id, context["run_id"], "cotw", context["analyser"],
                          context["snapshot_id"], TS, "{}"))
            conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                         " VALUES (?,?,?,?,?)",
                         (case_id, "probe", "high", f"P{i:031d}", db.j([row["id"]])))
            conn.commit()
            claim = queries.claim_read(conn, row["id"])
            html = app.case_page(conn, case_id).decode("utf-8")
            assert english.lint(html, app.quoted_assertion(claim or {})) == [], row["id"]
    finally:
        conn.close()
