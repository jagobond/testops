"""TESTOPS-36: a step two analysers both judged says so on both pages.

The Product Owner's finding: the level-fitness and duplication analysers examine the same asserting
step and hand the reader two competing instructions - rewrite the step, or keep one copy - and
neither page mentions the other exists. The decision (already taken) keeps them as separate claims;
what was missing is the relationship.

These tests build the two claims the way the pipeline writes them - one run per analyser, each with
its own snapshot over the same commit - and render both case pages from the store. Nothing is
re-analysed at render time: the cross-reference is a query over the stored ``assertion_path``,
``assertion_line`` and ``assertion_commit``.
"""
from __future__ import annotations

import html as htmllib
import re

from testops.store import db
from testops.web import app

TS = "2020-01-01T00:00:00+00:00"
COMMIT = "a" * 40
PATH = "ReqOverflow.Specs.API/Features/Home.feature"
LINE = 24
OTHER_PATH = "ReqOverflow.Specs.Controller/Features/Home.feature"
OTHER_LINE = 23
ASSERTION = "The latest question is shown on home page with details"
LEVEL_CASE = "case-level-01"
DUP_CASE = "case-dup-01"
ALONE_CASE = "case-level-02"


def _text(body: bytes) -> str:
    text = body.decode("utf-8")
    text = re.sub(r"<style>.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<head>.*?</head>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(htmllib.unescape(text).split())


def _seed(conn, *, snapshot, run, analyser, case_id, line, commit=COMMIT, path=PATH,
          verdict="review", established_by="", action="Rewrite the step."):
    # The same snapshot and run may already exist: these rows are the harness, not the claims.
    if conn.execute("SELECT 1 FROM run WHERE id = ?", (run,)).fetchone() is None:
        db.upsert_snapshot(conn, snapshot, "reqoverflow", TS, {"reqnroll/test": commit},
                           schema_version=2)
        db.start_run(conn, run, "reqoverflow", snapshot, analyser, TS)
    claim_id = db.add_claim(
        conn, run, analyser, "0.9.0", f"scenario:{path}#{ASSERTION}",
        f"This test asserts the step {ASSERTION}.", verdict, 0.8, [], schema_version=2,
        assertion_text=ASSERTION, assertion_path=path, assertion_line=line,
        assertion_commit=commit, established_by=established_by,
        sources_assessed=True, sources_missing=[], proposed_action=action)
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at,"
                 " summary) VALUES (?,?,?,?,?,?,?)",
                 (case_id, run, "reqoverflow", analyser, snapshot, TS, "{}"))
    conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                 " VALUES (?,?,?,?,?)",
                 (case_id, ASSERTION, "high", f"{claim_id:032d}", db.j([claim_id])))
    return claim_id


def _store(tmp_path):
    """Both analysers' cases for line 24, plus a step only level fitness reported."""
    conn = db.connect(tmp_path / "xref.db")
    _seed(conn, snapshot="snap-level", run="run-level", analyser="level_fitness",
          case_id=LEVEL_CASE, line=LINE, verdict="review", action="Rewrite the step.")
    _seed(conn, snapshot="snap-dup", run="run-dup", analyser="duplication",
          case_id=DUP_CASE, line=LINE, verdict="duplicate",
          established_by=(f"the scenario's steps match those of {OTHER_PATH}:{OTHER_LINE} after "
                          f"normalisation, tables and doc strings included, and its step "
                          f"definitions place this copy at api"),
          action="Raise this with the team: keep one.")
    _seed(conn, snapshot="snap-level", run="run-level", analyser="level_fitness",
          case_id=ALONE_CASE, line=40, verdict="review", action="Rewrite the step.")
    conn.commit()
    return conn


def test_both_pages_name_the_other_and_link_to_it(tmp_path):
    """AC1, AC2, AC5: each page carries the section, a link, and what the two mean together."""
    conn = _store(tmp_path)
    try:
        level = app.case_page(conn, LEVEL_CASE).decode("utf-8")
        dup = app.case_page(conn, DUP_CASE).decode("utf-8")
    finally:
        conn.close()

    level_text, dup_text = _text(level.encode()), _text(dup.encode())

    # AC1: the section names the other analyser and links to its case.
    assert "Also reported by Duplication" in level_text
    assert f'href="/case/{DUP_CASE}"' in level
    assert "Also reported by Level fitness" in dup_text
    assert f'href="/case/{LEVEL_CASE}"' in dup

    # AC1: the line says what the other analyser found, from the stored claim.
    assert f"{OTHER_PATH}:{OTHER_LINE}" in level_text               # the copy the duplicate names
    assert "over-tested for what it asserts" in dup_text            # the level claim's verdict

    # AC2: one sentence saying what the two findings mean together, in the reader's terms.
    assert "fixing the level here does not remove the duplication" in level_text
    assert "deciding which copy to keep does not change the level" in dup_text

    # The section is short: two lines per analyser, no third paragraph.
    section = level.split('<aside class="xref">', 1)[1].split("</aside>", 1)[0]
    assert section.count("<p>") == 2

    # AC6: the verdicts are unchanged; the section sits beside the argument, not in its place.
    assert "Checked, but over-tested for what it asserts" in level_text
    assert "Checked, but this repeats another test" in dup_text


def test_a_step_reported_once_renders_without_the_section(tmp_path):
    """AC4: no counterpart, no section - nothing at all is added to the page."""
    conn = _store(tmp_path)
    try:
        alone = app.case_page(conn, ALONE_CASE).decode("utf-8")
        # A claim at the same line and path but a different commit is not the same step either.
        _seed(conn, snapshot="snap-other", run="run-other", analyser="duplication",
              case_id="case-other", line=40, commit="b" * 40, verdict="duplicate",
              established_by=f"the scenario's steps match those of {OTHER_PATH}:{OTHER_LINE}")
        alone_other_commit = app.case_page(conn, ALONE_CASE).decode("utf-8")
    finally:
        conn.close()

    # AC4: adding a claim at a different commit changed not one byte of the page.
    assert alone == alone_other_commit
    for page in (alone, alone_other_commit):
        assert "Also reported by" not in _text(page.encode())
        assert '<aside class="xref">' not in page
        assert "does not remove the duplication" not in _text(page.encode())


def test_a_counterpart_with_no_case_renders_nothing(tmp_path):
    """AC3: the reference comes from a stored claim with a case behind it, never a guess.

    The duplication claim is stored at the same coordinates but no finding and no case name it -
    it never raised, so there is no page to link to, and the level page stays silent.
    """
    conn = db.connect(tmp_path / "no-case.db")
    _seed(conn, snapshot="snap-level", run="run-level", analyser="level_fitness",
          case_id=LEVEL_CASE, line=LINE)
    db.upsert_snapshot(conn, "snap-dup", "reqoverflow", TS, {"reqnroll/test": COMMIT},
                       schema_version=2)
    db.start_run(conn, "run-dup", "reqoverflow", "snap-dup", "duplication", TS)
    db.add_claim(conn, "run-dup", "duplication", "0.9.0", f"scenario:{PATH}#{ASSERTION}",
                 "A duplicate.", "duplicate", 0.9, [], schema_version=2,
                 assertion_text=ASSERTION, assertion_path=PATH, assertion_line=LINE,
                 assertion_commit=COMMIT,
                 established_by=f"the scenario's steps match those of {OTHER_PATH}:{OTHER_LINE}",
                 sources_assessed=True, sources_missing=[], proposed_action="Keep one.")
    conn.commit()
    try:
        page = app.case_page(conn, LEVEL_CASE).decode("utf-8")
        claim = conn.execute("SELECT id FROM claim WHERE analyser = 'level_fitness'").fetchone()
        from testops import queries
        read = queries.claim_read(conn, claim["id"])
        assert read is not None
        references = queries.cross_references(conn, read)
    finally:
        conn.close()

    assert references == []
    assert "Also reported by" not in _text(page.encode())
    assert '<aside class="xref">' not in page
