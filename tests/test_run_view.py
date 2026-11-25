"""TESTOPS-34: a case is a finding, and a run that raised nothing is a run.

The Product Owner read `case-demo-product-dup-20261120T194032` and asked what an open case telling him there
were no findings was doing there. It was a defect: every analysis run used to leave a `case_` row
behind, and the case list was padded with rows nobody could decide. A case carries a decision about
a finding; no finding, no case.

These tests pin the three surfaces the fix touches, from stored rows only:

  * the case list query cannot return a row with no finding (AC2) - and the row is still there
    (AC3), because evidence is not destroyed by ceasing to call it a case;
  * the run that raised nothing is reachable as a run, with its counts, commit and the sources it
    could not consult (AC1, AC4) - the TESTOPS-22 page, addressed by run id;
  * a run whose findings were all closed by decisions is still a real case, closed, and never
    reads like a run that raised nothing.

One store holds both runs, so every comparison is between pages rendered from the same database by
the same code.
"""
from __future__ import annotations

import html as htmllib
import re

from testops import blobs, cases, queries, sources
from testops.analysers import duplication
from testops.store import db
from testops.web import app

TS = "2020-01-01T00:00:00+00:00"
SNAP = "snap-quiet"
RUN = "run-quiet"
EMPTY_CASE = "case-quiet"
DECIDED_SNAP = "snap-decided"
DECIDED_RUN = "run-decided"
DECIDED_CASE = "case-decided"
COMMIT = "a" * 40
CSPROJ = "DemoProductTests.csproj"
REMOVED = "features/old.feature"
LIVE = "features/live.feature"

CSPROJ_TEXT = """<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <ReqnrollFeatureFile Remove="features/old.feature" />
  </ItemGroup>
</Project>"""


def _text(body: bytes) -> str:
    text = body.decode("utf-8")
    text = re.sub(r"<style>.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<head>.*?</head>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(htmllib.unescape(text).split())


def _badge(body: bytes) -> str:
    m = re.search(r'<span class="badge[^"]*">([^<]+)</span>', body.decode("utf-8"))
    return m.group(1).strip() if m else ""


def _registry() -> sources.Registry:
    """The registry a run records: GitHub available, Jira blocked by policy."""
    return sources.Registry([
        sources.SourceKind.available(sources.GITHUB, "GitHub",
                                     (sources.CODE, sources.TEST_CODE), observed=2),
        sources.SourceKind.blocked(sources.JIRA, "Jira", (sources.REQUIREMENTS,),
                                   sources.QUILTER_NO_PAT, sources.QUILTER_POLICY),
    ])


def _meta() -> dict:
    registry = _registry()
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


def _store(tmp_path, monkeypatch, decided: bool = True):
    """One quiet run (with the legacy empty case row) and, unless asked not to, one decided run."""
    monkeypatch.setattr(blobs, "BLOB_DIR", tmp_path / "blobs")
    conn = db.connect(tmp_path / "runs.db")
    db.upsert_snapshot(conn, SNAP, "fixture", TS, {"owner/test": COMMIT},
                       schema_version=2, meta=_meta())

    sha = blobs.put(CSPROJ_TEXT.encode("utf-8"))
    db.add_artefact(conn, SNAP, f"github:owner/test@{COMMIT}:{CSPROJ}", "build", sha)
    _feature(conn, LIVE, ("first lives", "second lives", "third lives"))
    _feature(conn, REMOVED, ("one dormant", "two dormant"))

    db.start_run(conn, RUN, "fixture", SNAP, duplication.name, TS)
    db.finish_run(conn, RUN, "ok", TS)
    # The shape the defect left in the store: a case row for a run that raised nothing.
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at,"
                 " summary) VALUES (?,?,?,?,?,?,?)",
                 (EMPTY_CASE, RUN, "fixture", duplication.name, SNAP, TS, "{}"))
    if not decided:
        conn.commit()
        return conn

    # A run that raised one finding, and a person resolved it. It is a real case, closed.
    db.upsert_snapshot(conn, DECIDED_SNAP, "fixture", TS, {"owner/test": COMMIT}, schema_version=2)
    db.start_run(conn, DECIDED_RUN, "fixture", DECIDED_SNAP, duplication.name, TS)
    db.finish_run(conn, DECIDED_RUN, "ok", TS)
    claim_id = db.add_claim(
        conn, DECIDED_RUN, duplication.name, "2.0.0",
        "scenario:features/live.feature#first lives",
        "The scenario asserts the same thing another copy already establishes.",
        "duplicate", 0.9, [], schema_version=2,
        assertion_text="it lives", assertion_path=LIVE, assertion_line=1,
        assertion_commit=COMMIT, interaction_label="settled by the response the server sends",
        span=["api"], established_by="the scenario's steps match another copy after normalisation",
        sources_assessed=False, proposed_action="Raise this with the team; keep one copy.")
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at,"
                 " summary) VALUES (?,?,?,?,?,?,?)",
                 (DECIDED_CASE, DECIDED_RUN, "fixture", duplication.name, DECIDED_SNAP, TS, "{}"))
    conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                 " VALUES (?,?,?,?,?)",
                 (DECIDED_CASE, "duplicate", "medium", "f" * 32, db.j([claim_id])))
    conn.commit()
    cases.set_state(conn, DECIDED_CASE, "resolved", "harry", "covered by the API test")
    return conn


# --------------------------------------------------------------------------- AC2, AC3

def test_the_case_list_query_cannot_return_a_case_with_no_finding(tmp_path, monkeypatch):
    conn = _store(tmp_path, monkeypatch)
    try:
        rows = cases.list_cases(conn, None, 500)
        by_project = cases.list_cases(conn, "fixture", 500)
        # AC3: the row is not deleted; it is evidence, and it is simply not a case.
        stored = conn.execute("SELECT COUNT(*) FROM case_ WHERE id = ?",
                              (EMPTY_CASE,)).fetchone()[0]
    finally:
        conn.close()

    assert [row["id"] for row in rows] == [DECIDED_CASE]
    assert [row["id"] for row in by_project] == [DECIDED_CASE]
    assert all(row["findings"] >= 1 for row in rows)
    assert EMPTY_CASE not in {row["id"] for row in rows}
    assert stored == 1, "the empty case row was destroyed; evidence must survive"


def test_a_case_whose_findings_were_all_closed_is_still_a_case(tmp_path, monkeypatch):
    """A decision closes a case; it does not make the case disappear, and it is not a quiet run."""
    conn = _store(tmp_path, monkeypatch)
    try:
        rows = {row["id"]: row for row in cases.list_cases(conn, None, 500)}
    finally:
        conn.close()

    assert DECIDED_CASE in rows
    assert rows[DECIDED_CASE]["state"] == "resolved"
    assert rows[DECIDED_CASE]["findings"] == 1


def test_the_runs_view_lists_the_quiet_run_and_the_home_page_does_not_list_its_row(tmp_path, monkeypatch):
    conn = _store(tmp_path, monkeypatch)
    try:
        index = _text(app.index(conn))
        runs = _text(app.runs_index(conn))
        listed = queries.list_runs(conn)
    finally:
        conn.close()

    # The case list is not padded with a row nobody can act on.
    assert EMPTY_CASE not in index
    # The run is still reachable, and the runs view carries its counts, commit and blind spots.
    assert RUN in runs
    assert "No findings" in runs
    assert "test@aaaaaaaa" in runs
    assert "Could not consult Jira" in runs
    row = next(r for r in listed if r["id"] == RUN)
    assert (row["claims"], row["findings"], row["case_count"]) == (0, 0, 0)


def test_the_empty_home_page_points_at_the_run_it_just_described(tmp_path, monkeypatch):
    """With no cases at all, the home page names the newest run and links to its page."""
    conn = _store(tmp_path, monkeypatch, decided=False)
    try:
        body = app.index(conn)
        text = _text(body)
    finally:
        conn.close()

    assert "No cases are open" in text
    assert "Open the run" in text
    assert f"/run/{RUN}" in body.decode("utf-8")
    assert 'href="/runs"' in body.decode("utf-8")


# --------------------------------------------------------------------------- AC1, AC4

def test_the_quiet_run_page_survives_reached_by_run_id(tmp_path, monkeypatch):
    """AC4: the TESTOPS-22 page, now addressed by the thing it describes."""
    conn = _store(tmp_path, monkeypatch)
    try:
        body, status = app.run_response(conn, RUN)
    finally:
        conn.close()

    text = _text(body)
    assert status == 200
    assert "No findings in this run" in text
    # The counts, from the stored project file and the recorded observations.
    assert "1 feature file and 3 scenarios" in text
    assert "4 exclusion patterns read from DemoProductTests.csproj" in text
    assert "left 1 of 2 stored feature files outside the build" in text
    assert "recorded no claim about any of them" in text
    # The commit, the analyser and what the run could not consult.
    assert "test@aaaaaaaa" in text
    assert "Duplication" in text
    assert "What this run could not consult" in text
    assert "Jira" in text and "blocked by Quilter policy" in text
    # It says why there is no case to open, and names the run in the URL's own terms.
    assert "created no case" in text
    assert RUN in text
    assert _badge(body) == "No findings"
    assert "%" not in text


def test_the_legacy_case_row_still_renders_and_points_at_its_run(tmp_path, monkeypatch):
    """AC3: the shared URL still explains itself, and names where the run now lives."""
    conn = _store(tmp_path, monkeypatch)
    try:
        body, status = app.case_response(conn, EMPTY_CASE)
    finally:
        conn.close()

    text = _text(body)
    assert status == 200
    assert "This row raised no finding, so it is not a case." in text
    assert f"/run/{RUN}" in body.decode("utf-8")
    assert "No findings in this run" in text


# --------------------------------------------------------------------------- the distinction

def test_a_run_that_raised_nothing_never_reads_like_a_closed_case(tmp_path, monkeypatch):
    conn = _store(tmp_path, monkeypatch)
    try:
        quiet_body, quiet_status = app.run_response(conn, RUN)
        decided_body, decided_status = app.run_response(conn, DECIDED_RUN)
    finally:
        conn.close()

    quiet, decided = _text(quiet_body), _text(decided_body)
    assert (quiet_status, decided_status) == (200, 200)
    assert "No findings in this run" in quiet
    assert "No findings in this run" not in decided
    # The decided run is described as a run that raised something, with its case linked.
    assert "This run raised 1 finding" in decided
    assert DECIDED_CASE in decided
    assert "Resolved" in decided
    assert "Every case this run raised has been decided" in decided
    assert "closed" in decided and "not a clean bill" in decided
    # The badges cannot be confused either.
    assert _badge(quiet_body) == "No findings"
    assert _badge(decided_body) == "All decided"


def test_a_run_with_no_findings_has_no_cases_and_one_with_a_finding_does(tmp_path, monkeypatch):
    conn = _store(tmp_path, monkeypatch)
    try:
        assert queries.cases_for_run(conn, RUN) == []
        assert [c["id"] for c in queries.cases_for_run(conn, DECIDED_RUN)] == [DECIDED_CASE]
        runs = {r["id"]: r for r in queries.list_runs(conn)}
    finally:
        conn.close()

    assert runs[RUN]["findings"] == 0
    assert runs[DECIDED_RUN]["findings"] == 1
    assert runs[DECIDED_RUN]["case_count"] == 1
    assert runs[DECIDED_RUN]["decided_cases"] == 1
    # AC5: the claim the decided run wrote is still counted, and its verdict is untouched.
    assert runs[DECIDED_RUN]["claims"] == 1


# --------------------------------------------------------------------------- stale ids

def test_a_run_id_the_store_does_not_hold_answers_404_with_a_page(tmp_path, monkeypatch):
    conn = _store(tmp_path, monkeypatch)
    try:
        body, status = app.run_response(conn, "run-never-existed")
    finally:
        conn.close()

    assert status == 404
    text = _text(body)
    assert "This run is no longer in the store" in text
    assert "pruned by retention" in text


def test_a_run_naming_an_unregistered_analyser_answers_404_and_names_it(tmp_path, monkeypatch):
    conn = _store(tmp_path, monkeypatch)
    try:
        db.start_run(conn, "run-fixture", "review", SNAP, "x", TS)
        db.finish_run(conn, "run-fixture", "ok", TS)
        conn.commit()
        body, status = app.run_response(conn, "run-fixture")
        listed = [r["id"] for r in queries.list_runs(conn)]
    finally:
        conn.close()

    assert status == 404
    page = body.decode("utf-8")
    assert "not one this build can run" in page
    assert "analyser <span class=\"code\">x</span>" in page
    assert "run-fixture" not in listed
