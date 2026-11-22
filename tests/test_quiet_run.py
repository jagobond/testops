"""TESTOPS-22: a quiet run is not a resolved case.

The Product Owner opened a case for a run that raised nothing, read "Resolved", and asked whether a
test had decided it. Neither had: no duplicate coverage existed in that run, and no person had
recorded a decision. These tests pin the distinction, and both sides are rendered from stored rows
only - no live source, no config re-read, no count the store cannot prove.

The two cases below are built in one store, so the comparison in AC6 is between two pages rendered
from the same database by the same code.
"""
from __future__ import annotations

import html as htmllib
import re

from testops import blobs, cases, sources
from testops.analysers import duplication
from testops.store import db
from testops.web import app

TS = "2020-01-01T00:00:00+00:00"
SNAP = "snap-quiet"
RUN = "run-quiet"
QUIET = "case-quiet"
RESOLVED = "case-resolved"
COMMIT = "a" * 40
CSPROJ = "CotwBdd.csproj"
REMOVED = "features/old.feature"
LIVE = "features/live.feature"


def _text(body: bytes) -> str:
    html = body.decode("utf-8")
    html = re.sub(r"<style>.*?</style>", " ", html, flags=re.S)
    html = re.sub(r"<head>.*?</head>", " ", html, flags=re.S)
    html = re.sub(r"<[^>]+>", " ", html)
    return " ".join(htmllib.unescape(html).split())


def _registry(*, observed=2):
    """The registry a run records: GitHub available, Jira blocked by policy."""
    return sources.Registry([
        sources.SourceKind.available(sources.GITHUB, "GitHub",
                                     (sources.CODE, sources.TEST_CODE), observed=observed),
        sources.SourceKind.blocked(sources.JIRA, "Jira", (sources.REQUIREMENTS,),
                                   sources.QUILTER_NO_PAT, sources.QUILTER_POLICY),
    ])


def _meta(registry=None) -> dict:
    if registry is None:
        return {}                        # a snapshot from before the registry was recorded
    return {"sources_missing": registry.missing(duplication.NEEDS | duplication.CONSULTS),
            "sources": registry.record(),
            "analysers": {"duplication": {"needs": sorted(duplication.NEEDS),
                                          "consults": sorted(duplication.CONSULTS)}}}


def _feature(conn, path, scenarios):
    artefact_id = db.add_artefact(conn, SNAP, f"github:owner/test@{COMMIT}:{path}",
                                  "feature", "0" * 40)
    for line, name in enumerate(scenarios, start=1):
        db.add_observation(conn, artefact_id, "gherkin", "1.0.0", f"scenario:{name}",
                           {"line": line, "steps": 2, "signature": name.lower()})
    return artefact_id


def _store(tmp_path, monkeypatch, *, registry="recorded", project=True):
    """One snapshot, one quiet run, and a second case a person resolved."""
    monkeypatch.setattr(blobs, "BLOB_DIR", tmp_path / "blobs")
    conn = db.connect(tmp_path / "quiet.db")
    meta = _meta(_registry()) if registry == "recorded" else _meta(None)
    db.upsert_snapshot(conn, SNAP, "fixture", TS, {"owner/test": COMMIT},
                       schema_version=2, meta=meta)

    if project:
        sha = blobs.put(CSPROJ_TEXT.encode("utf-8"))
        db.add_artefact(conn, SNAP, f"github:owner/test@{COMMIT}:{CSPROJ}", "build", sha)
    # The live file's three scenarios are what the run analysed. The removed file's two scenarios
    # were recorded by the extractor too, and must not be counted: the build does not run them.
    _feature(conn, LIVE, ("first lives", "second lives", "third lives"))
    _feature(conn, REMOVED, ("one dormant", "two dormant"))

    db.start_run(conn, RUN, "fixture", SNAP, duplication.name, TS)
    db.finish_run(conn, RUN, "ok", TS)

    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at,"
                 " summary) VALUES (?,?,?,?,?,?,?)",
                 (QUIET, RUN, "fixture", duplication.name, SNAP, TS, "{}"))
    # A genuinely resolved case: a finding, and a person's recorded decision about it. It has its
    # own run, so the quiet run's claim count stays what such a run really records: none.
    db.start_run(conn, RUN + "-resolved", "fixture", SNAP, duplication.name, TS)
    db.finish_run(conn, RUN + "-resolved", "ok", TS)
    claim_id = db.add_claim(
        conn, RUN + "-resolved", duplication.name, "2.0.0",
        "scenario:features/live.feature#first lives",
        "The scenario \"first lives\" at features/live.feature:1 asserts \"it lives\", which "
        "features/other.feature:4 already establishes over HTTP.",
        "duplicate", 0.9, [], schema_version=2,
        assertion_text="it lives", assertion_path=LIVE, assertion_line=1,
        assertion_commit=COMMIT, interaction_label="settled by the response the server sends",
        span=["api"], established_by="the scenario's steps match another copy after normalisation",
        sources_assessed=False, proposed_action="Raise this with the team; keep one copy.")
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at,"
                 " summary) VALUES (?,?,?,?,?,?,?)",
                 (RESOLVED, RUN + "-resolved", "fixture", duplication.name, SNAP, TS, "{}"))
    conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                 " VALUES (?,?,?,?,?)",
                 (RESOLVED, "duplicate", "medium", "f" * 32, db.j([claim_id])))
    conn.commit()
    cases.set_state(conn, RESOLVED, "resolved", "harry", "covered by the API test")
    return conn, claim_id


CSPROJ_TEXT = """<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <ReqnrollFeatureFile Remove="features/old.feature" />
  </ItemGroup>
</Project>"""


def _render(conn, case_id):
    body = app.case_page(conn, case_id)
    assert body is not None
    return body, _text(body)


def _heading(text: str) -> str:
    m = re.search(r"<h2>([^<]+)</h2>", text)
    return m.group(1).strip() if m else ""


def _badge(text: str) -> str:
    m = re.search(r'<span class="badge[^"]*">([^<]+)</span>', text)
    return m.group(1).strip() if m else ""


# --------------------------------------------------------------------------- AC1, AC3, AC5

def test_a_quiet_run_says_what_it_analysed_with_counts_the_store_proves(tmp_path, monkeypatch):
    conn, _ = _store(tmp_path, monkeypatch)
    try:
        body, text = _render(conn, QUIET)
    finally:
        conn.close()

    assert "No findings in this run" in text
    # 1 feature file kept, 3 of its scenarios; the removed file's 2 scenarios are not counted.
    assert "1 feature file and 3 scenarios" in text
    # 1 declared exclusion + the 3 built-in ignores, read from the stored project file.
    assert "4 exclusion patterns read from CotwBdd.csproj" in text
    assert "left 1 of 2 stored feature files outside the build" in text
    assert "recorded no claim about any of them" in text
    # AC5: the freshness line and the analyser name are still on the page.
    assert "test@aaaaaaaa" in text
    assert "Duplication" in text
    # The badge says what happened, not what somebody decided.
    assert _badge(body.decode("utf-8")) == "No findings"
    # No percentages: a store cannot prove one.
    assert "%" not in text


def test_the_counts_come_from_the_stored_project_file_not_from_a_live_read(tmp_path, monkeypatch):
    """The same reader the analyser uses: drop the Remove line and the dormant file is active."""
    conn, _ = _store(tmp_path, monkeypatch, project=False)
    try:
        _body, text = _render(conn, QUIET)
    finally:
        conn.close()
    # With no project file stored, no exclusion pattern can be claimed: the page says so and keeps
    # every recorded feature file in the build, exactly as the analyser would.
    assert "no project file is stored for this snapshot" in text
    assert "2 feature files and 5 scenarios" in text


def test_a_project_file_whose_content_is_missing_is_cannot_say_not_zero(tmp_path, monkeypatch):
    conn, _ = _store(tmp_path, monkeypatch)
    try:
        conn.execute("UPDATE artefact SET blob_sha = ? WHERE kind = 'build'", ("9" * 64,))
        conn.commit()
        _body, text = _render(conn, QUIET)
    finally:
        conn.close()
    assert "cannot be counted from the store" in text
    assert "0 feature files" not in text


# --------------------------------------------------------------------------- AC4

def test_what_the_run_could_not_consult_comes_from_its_recorded_registry(tmp_path, monkeypatch):
    conn, _ = _store(tmp_path, monkeypatch)
    try:
        _body, text = _render(conn, QUIET)
    finally:
        conn.close()
    assert "What this run could not consult" in text
    assert "Jira" in text and "blocked by Quilter policy" in text
    assert "never consulted" in text


def test_a_snapshot_with_no_registry_says_so_and_names_no_source(tmp_path, monkeypatch):
    """AC4: a source is never named from today's config. This snapshot recorded none."""
    conn, _ = _store(tmp_path, monkeypatch, registry="unrecorded")

    def boom(*_a, **_k):
        raise AssertionError("the page re-read the live source configuration")

    monkeypatch.setattr(app.sources, "registry", boom)
    try:
        _body, text = _render(conn, QUIET)
    finally:
        conn.close()
    assert "recorded no source registry" in text
    assert "Jira" not in text
    assert "every source" not in text.lower()
    assert "cannot say which sources it could not consult" in text


# --------------------------------------------------------------------------- AC2, AC6

def test_a_quiet_run_and_a_resolved_case_never_share_wording(tmp_path, monkeypatch):
    conn, _ = _store(tmp_path, monkeypatch)
    try:
        quiet_body, quiet_text = _render(conn, QUIET)
        resolved_body, resolved_text = _render(conn, RESOLVED)
    finally:
        conn.close()

    quiet_html, resolved_html = quiet_body.decode("utf-8"), resolved_body.decode("utf-8")
    # AC2: "Resolved" only where a case_state resolved row exists.
    assert "Resolved" not in quiet_text
    assert "resolved:" not in quiet_text.lower()
    assert "Resolved by harry" in resolved_text
    assert "covered by the API test" in resolved_text
    assert "did not change what the run analysed" in resolved_text
    # AC6: different heading, different badge, different body.
    assert _heading(quiet_html) == "No findings in this run"
    assert _heading(resolved_html) == "Resolved"
    assert _heading(quiet_html) != _heading(resolved_html)
    assert _badge(quiet_html) != _badge(resolved_html)
    assert quiet_text != resolved_text
    assert "No findings in this run" not in resolved_text


def test_a_quiet_run_that_was_resolved_shows_both_facts_without_confusing_them(
        tmp_path, monkeypatch):
    conn, _ = _store(tmp_path, monkeypatch)
    try:
        cases.set_state(conn, QUIET, "resolved", "harry", "looked and agreed")
        body, text = _render(conn, QUIET)
    finally:
        conn.close()
    # The run is still described as a run ...
    assert "No findings in this run" in text
    # ... and the decision is named as a decision, with its who, when and note.
    assert "Resolved by harry" in text
    assert "looked and agreed" in text
    assert _badge(body.decode("utf-8")) == "Resolved"


def test_an_empty_case_with_no_decision_is_never_labelled_resolved(tmp_path):
    conn = db.connect(tmp_path / "empty.db")
    try:
        db.upsert_snapshot(conn, SNAP, "fixture", TS, {"owner/test": COMMIT}, schema_version=2)
        db.start_run(conn, RUN, "fixture", SNAP, duplication.name, TS)
        db.finish_run(conn, RUN, "ok", TS)
        conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at,"
                     " summary) VALUES (?,?,?,?,?,?,?)",
                     (QUIET, RUN, "fixture", duplication.name, SNAP, TS, "{}"))
        conn.commit()
        assert app.display_state("open", 0) == "No findings"
        assert app.display_state("resolved", 0) == "Resolved"
    finally:
        conn.close()
