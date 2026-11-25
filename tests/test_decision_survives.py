"""TESTOPS-37: a recorded decision has to survive the next run.

The Decision control is the tool's promise to the Product Owner: judge a finding once and the next
analysis over the same evidence stays quiet about it. Nothing tested that promise. The store wrote
suppression rows faithfully, and three gates in ``pipeline.py`` consulted them - at ``_emit`` (line
~101), in the duplication case loop (~246) and in the level-fitness case loop (~405) - with no test
touching any of them.

What is here:

  * an end-to-end test over the real ``run_level_fitness``: run, decide, run again over the same
    commit, and the decided finding is not raised - while the analyser still reaches the same
    verdict, so the quiet is the suppression and not a changed conclusion (AC1);
  * the same test reopens the case and runs a third time: the finding is raised again (AC2);
  * one focused test per gate, each built so that deleting that gate fails it (AC3);
  * the fingerprint contract the suppression rests on, pinned (AC4, with one correction reported
    in the build report: the line is deliberately NOT part of the identity - see the last two
    tests here, and the module documentation in ``level_fitness.py:674``);
  * the case page's sentence about reopening, checked against what the store then does (AC5).

Every store is ``tmp_path``; the collector is a fixture. No network, no checkout, no live store.
"""
from __future__ import annotations

import time

import level_fixtures as fixtures
import demo_service_fixtures as demo_service
from testops import blobs, cases, pipeline
from testops.analysers import duplication, level_fitness
from testops.collectors.github import Collected
from testops.config import Project, Repo
from testops.store import db
from testops.web import app

# Runs and snapshots are identified to the second (``run-{key}-levels-%Y%m%dT%H%M%S``), so two runs
# inside one second collide on the run's primary key. A second look is a second look in wall time
# too; the product never promises sub-second runs and neither does this suite.
GAP = 1.05


def _project(key: str = "fixture", test: str = "tests", product: str = "product") -> Project:
    return Project(key=key, product=Repo("o", product), test=Repo("o", test), jira_key="")


# --------------------------------------------------------------------------------------- harnesses

def _traced(monkeypatch, path, connect, statements: list[str]):
    """Make the pipeline's own connection record every statement it attempts.

    A gate whose only visible effect is "the case row is never even written" cannot be proven from
    the rows afterwards - the second gate in ``_emit`` deletes the case again. The trace is the
    observation that matters: no ``INSERT INTO case_`` is attempted at all.
    """
    def opener():
        conn = connect(path)
        conn.set_trace_callback(statements.append)
        return conn
    monkeypatch.setattr(pipeline.db, "connect", opener)


def _levels(monkeypatch, tmp_path, feature: str | None = None):
    path, connect = fixtures.stub_pipeline(monkeypatch, pipeline, tmp_path,
                                           feature=feature or fixtures.PIPELINE_FEATURE)
    statements: list[str] = []
    _traced(monkeypatch, path, connect, statements)
    return statements, lambda: connect(path)


def _duplication(monkeypatch, tmp_path):
    path, connect = demo_service.stub_pipeline(monkeypatch, pipeline, tmp_path)
    statements: list[str] = []
    _traced(monkeypatch, path, connect, statements)
    return statements, lambda: connect(path)


def _findings_for_run(conn, run_id: str) -> list[dict]:
    return [dict(row) for row in conn.execute(
        "SELECT f.id, f.case_id, f.fingerprint, f.claim_ids FROM finding f"
        " JOIN case_ c ON c.id = f.case_id WHERE c.run_id = ? ORDER BY f.id", (run_id,))]


def _case_row(conn, run_id: str, fingerprint: str) -> dict | None:
    row = conn.execute(
        "SELECT f.case_id, f.fingerprint, f.claim_ids FROM finding f"
        " JOIN case_ c ON c.id = f.case_id"
        " WHERE c.run_id = ? AND f.fingerprint = ?", (run_id, fingerprint)).fetchone()
    return dict(row) if row else None


def _decide_first_case(conn, run) -> tuple[str, str, str]:
    """Record a real decision on the first case a run raised; return (case, fingerprint, assertion).

    The assertion text is read back from the claim the finding points at, so the test can look for
    the same evidence on the next run rather than trusting the fingerprint it just computed.
    """
    case_id = run.case_ids[0]
    finding = conn.execute("SELECT fingerprint, claim_ids FROM finding WHERE case_id = ?",
                           (case_id,)).fetchone()
    assert finding is not None, f"case {case_id} raised no finding"
    claim_id = db.uj(finding["claim_ids"])[0]
    assertion = conn.execute("SELECT assertion_text FROM claim WHERE id = ?",
                             (claim_id,)).fetchone()["assertion_text"]
    cases.set_state(conn, case_id, "resolved", "harry", "checked by hand; covered elsewhere")
    return case_id, finding["fingerprint"], assertion


def _inserted_cases(statements: list[str]) -> list[str]:
    return [statement for statement in statements if "INSERT INTO case_" in statement]


# ------------------------------------------------------- AC1 / AC2: the decision survives, and undoes

def test_a_decided_finding_is_not_raised_by_the_next_run_and_reopening_brings_it_back(
        tmp_path, monkeypatch):
    """Run, decide, run, reopen, run - over one unchanged commit, through the real pipeline.

    The quiet second run must be quiet for the right reason: the analyser's claim is still ``gap``
    and its fingerprint is still the one the decision named, so only the suppression removed it. If
    the verdict had changed, the fingerprint would have changed with it and this test would fail.
    """
    _statements, connect = _levels(monkeypatch, tmp_path)
    project = _project()

    first = pipeline.run_level_fitness(project, token="unused")
    assert len(first.case_ids) == 2, first.stats

    conn = connect()
    try:
        case_id, decided_fp, assertion = _decide_first_case(conn, first)
        assert cases.suppressed(conn, decided_fp) is not None
    finally:
        conn.close()

    time.sleep(GAP)
    second = pipeline.run_level_fitness(project, token="unused")

    # AC1: the evidence was analysed again and still reaches the same actionable verdict.
    same_evidence = [claim for claim in second.claims
                     if claim.detail["assertion_text"] == assertion]
    assert len(same_evidence) == 1, "the second run stopped asserting what the first one did"
    claim = same_evidence[0]
    assert claim.verdict == "gap", "the verdict changed; this test cannot prove suppression"
    assert pipeline._fingerprint(level_fitness.name, claim) == decided_fp, \
        "the fingerprint moved, so the decision could not have been applied"

    # ... and yet it raised no case and no finding for it.
    conn = connect()
    try:
        assert decided_fp not in {finding["fingerprint"]
                                  for finding in _findings_for_run(conn, second.run_id)}
        assert _case_row(conn, second.run_id, decided_fp) is None
        assert cases.suppressed(conn, decided_fp) is not None
    finally:
        conn.close()
    assert len(second.case_ids) == 1, "the decided case came back"

    # AC2: reopening deletes the suppression, and the third run over the same commit reports it.
    conn = connect()
    try:
        cases.set_state(conn, case_id, "open", "harry", "changed my mind")
        assert cases.suppressed(conn, decided_fp) is None
    finally:
        conn.close()

    time.sleep(GAP)
    third = pipeline.run_level_fitness(project, token="unused")
    conn = connect()
    try:
        raised = _findings_for_run(conn, third.run_id)
    finally:
        conn.close()

    assert decided_fp in {finding["fingerprint"] for finding in raised}
    assert len(third.case_ids) == 2, "reopening did not put the decided finding back"


# ---------------------------------------------------------------- AC3: each gate, on its own terms

def test_the_emit_gate_refuses_a_suppressed_fingerprint(tmp_path):
    """``pipeline._emit``: the last gate, and the one that decides whether a finding exists.

    Without the gate ``_emit`` returns True and writes the finding. With it, the same claim - same
    verdict, same fingerprint - writes nothing, and says so by returning False.
    """
    claim = next(claim for claim in fixtures.analyse_fact_sheet(commit=fixtures.COMMIT)
                 if claim.verdict == "gap")
    fingerprint = pipeline._fingerprint(level_fitness.name, claim)

    conn = db.connect(tmp_path / "emit-gate.db")
    try:
        db.upsert_snapshot(conn, "snap-emit", "fixture", "2020-01-01T00:00:00+00:00",
                           {"o/tests": fixtures.COMMIT}, schema_version=2)
        db.start_run(conn, "run-emit", "fixture", "snap-emit", level_fitness.name,
                     "2020-01-01T00:00:00+00:00")
        db.add_claim(conn, "run-emit", level_fitness.name, level_fitness.version,
                     claim.subject_ref, claim.statement, claim.verdict, claim.confidence, [],
                     schema_version=2,
                     assertion_text=claim.detail["assertion_text"],
                     assertion_path=claim.detail["assertion_path"],
                     assertion_line=claim.detail["assertion_line"],
                     assertion_commit=claim.detail["assertion_commit"],
                     interaction_label=claim.detail["interaction_label"],
                     interaction_code=claim.detail["interaction_code"],
                     span=claim.detail["span"], established_by=claim.detail["established_by"],
                     sources_assessed=False,
                     proposed_action=claim.detail["proposed_action"])
        for case_id in ("case-emit-1", "case-emit-2"):
            conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id,"
                         " created_at, summary) VALUES (?,?,?,?,?,?,?)",
                         (case_id, "run-emit", "fixture", level_fitness.name, "snap-emit",
                          "2020-01-01T00:00:00+00:00", "{}"))
        conn.commit()

        # The control: the gate is not refusing everything.
        assert pipeline._emit(conn, "case-emit-1", level_fitness.name, claim) is True
        assert conn.execute("SELECT COUNT(*) FROM finding WHERE case_id = 'case-emit-1'"
                            ).fetchone()[0] == 1

        conn.execute("INSERT INTO suppression (fingerprint, state, actor, at, note)"
                     " VALUES (?,?,?,?,?)",
                     (fingerprint, "resolved", "harry", "2020-01-02T00:00:00+00:00", "known"))
        conn.commit()

        assert pipeline._emit(conn, "case-emit-2", level_fitness.name, claim) is False
        assert conn.execute("SELECT COUNT(*) FROM finding WHERE case_id = 'case-emit-2'"
                            ).fetchone()[0] == 0
    finally:
        conn.close()


def test_the_duplication_case_gate_never_even_writes_the_suppressed_case(tmp_path, monkeypatch):
    """The gate in ``run_duplication`` before a case is inserted (line ~246).

    Deleting this gate does not change the case table - ``_emit`` would reject the finding and the
    loop would delete the case again - so the proof is the attempted write. The gate's job is that
    the decision is honoured before a case exists; a suppression that relies on a second gate
    undoing the first one's work is a suppression with two chances to fail.
    """
    statements, connect = _duplication(monkeypatch, tmp_path)
    project = _project("demo-service", "demo-service", "demo-service")

    first = pipeline.run_duplication(project, token="unused")
    assert len(first.case_ids) == len(set(first.case_ids)) > 0

    conn = connect()
    try:
        _case_id, decided_fp, _assertion = _decide_first_case(conn, first)
    finally:
        conn.close()

    start = len(statements)
    time.sleep(GAP)
    second = pipeline.run_duplication(project, token="unused")
    second_sql = statements[start:]

    conn = connect()
    try:
        survivors = _findings_for_run(conn, second.run_id)
    finally:
        conn.close()

    # One case is attempted per finding that survives. The suppressed claim is skipped before any
    # case row exists; with this gate deleted it is inserted and then deleted again, which the
    # trace sees and the case table does not.
    assert len(survivors) == first.stats["cases"] - 1
    assert len(_inserted_cases(second_sql)) == len(survivors), \
        "the suppressed case was written and then deleted; the case gate did not run"
    assert decided_fp not in {finding["fingerprint"] for finding in survivors}
    # The evidence is still analysed and still a duplicate; only the case is gone.
    assert any(pipeline._fingerprint(duplication.name, claim) == decided_fp
               for claim in second.claims)


def test_the_levels_case_gate_never_even_writes_the_suppressed_case(tmp_path, monkeypatch):
    """The same gate in ``run_level_fitness`` (line ~405)."""
    statements, connect = _levels(monkeypatch, tmp_path)
    project = _project()

    first = pipeline.run_level_fitness(project, token="unused")
    assert len(first.case_ids) == 2

    conn = connect()
    try:
        _case_id, decided_fp, _assertion = _decide_first_case(conn, first)
    finally:
        conn.close()

    start = len(statements)
    time.sleep(GAP)
    second = pipeline.run_level_fitness(project, token="unused")
    second_sql = statements[start:]

    conn = connect()
    try:
        survivors = _findings_for_run(conn, second.run_id)
    finally:
        conn.close()
    # One case is attempted per finding that survives; with the gate deleted the suppressed claim
    # is inserted and then deleted, so the attempts outnumber the survivors.
    assert len(survivors) == 1
    assert len(_inserted_cases(second_sql)) == len(survivors), \
        "the suppressed case was written and then deleted; the case gate did not run"
    assert decided_fp not in {finding["fingerprint"] for finding in survivors}
    assert len(second.case_ids) == 1
    assert any(pipeline._fingerprint(level_fitness.name, claim) == decided_fp
               for claim in second.claims)


# ------------------------------------------------------------------------------- AC4: the identity

def test_the_same_assertion_at_the_same_commit_gets_the_same_fingerprint_across_runs(
        tmp_path, monkeypatch):
    """What the decision is keyed on must not move between runs of one unchanged commit."""
    _statements, connect = _levels(monkeypatch, tmp_path)
    project = _project()

    first = pipeline.run_level_fitness(project, token="unused")
    time.sleep(GAP)
    second = pipeline.run_level_fitness(project, token="unused")

    def by_assertion(run):
        return {claim.detail["assertion_text"]: pipeline._fingerprint(level_fitness.name, claim)
                for claim in run.claims if claim.verdict in pipeline.RAISES}

    assert by_assertion(first) == by_assertion(second)
    assert len(by_assertion(first)) == 2

    conn = connect()
    try:
        stored = {finding["fingerprint"] for finding in _findings_for_run(conn, first.run_id)}
    finally:
        conn.close()
    assert stored == set(by_assertion(first).values())


def test_moving_the_assertion_down_the_file_keeps_its_fingerprint(tmp_path, monkeypatch):
    """AC4 said a moved line yields a different fingerprint. The product deliberately does the
    opposite, and this test pins what it does.

    ``level_fitness`` builds the identity from the scenario reference, the interaction and the
    assertion's words - never the line (``level_fitness.py:674``: "never its line, so reformatting
    the file does not resurrect a judged case"). That is the behaviour the Decision control needs:
    if the line were part of the key, editing a comment above an assertion would resurrect every
    decision about it. This test proves the line moved and the fingerprint did not, so the deviation
    from the ticket's wording is real and not an untested assumption.

    What does distinguish two findings is the subject: the same words in another scenario or file
    are a different fingerprint, which the second test here pins.
    """
    shifted = fixtures.FEATURE_TEXT.replace(
        "  Scenario: the fact sheet is usable with a screen reader\n",
        "  Scenario: the fact sheet is usable with a screen reader\n"
        "    # a comment added above the asserting steps shifts every line below it\n")

    first_claims = [claim for claim in fixtures.analyse_fact_sheet(commit=fixtures.COMMIT)
                    if claim.verdict == "gap"]
    shifted_claims = [claim for claim in fixtures.analyse_text(
        shifted, fixtures.api_bindings(), commit=fixtures.COMMIT) if claim.verdict == "gap"]

    def by_text(claims):
        return {claim.detail["assertion_text"]: claim for claim in claims}

    before, after = by_text(first_claims), by_text(shifted_claims)
    assert set(before) == set(after)
    for text, claim in before.items():
        assert claim.detail["assertion_line"] != after[text].detail["assertion_line"], \
            "the fixture did not actually move the assertion"
        assert pipeline._fingerprint(level_fitness.name, claim) == \
            pipeline._fingerprint(level_fitness.name, after[text]), \
            "a moved line changed the fingerprint; reformatting would resurrect decisions"


def test_the_same_words_in_another_scenario_are_a_different_fingerprint():
    """The discrimination the suppression does rely on: subject plus evidence, not just words."""
    other_scenario = fixtures.FEATURE_TEXT.replace(
        "  Scenario: the fact sheet is usable with a screen reader\n",
        "  Scenario: the fact sheet is usable from a tablet\n")
    original = fixtures.analyse_fact_sheet(commit=fixtures.COMMIT)
    moved = fixtures.analyse_text(other_scenario, fixtures.api_bindings(), commit=fixtures.COMMIT)

    def fingerprint_for(claims, text):
        claim = next(claim for claim in claims if claim.detail["assertion_text"] == text)
        return pipeline._fingerprint(level_fitness.name, claim)

    text = fixtures.ASSERTING_TEXTS[0]
    assert fingerprint_for(original, text) != fingerprint_for(moved, text)


# --------------------------------------------------- AC5: the page's promise, checked in the store

def test_the_case_page_promise_that_reopening_makes_it_report_again_holds(
        tmp_path, monkeypatch):
    """The words the Product Owner reads are the behaviour this suite now proves.

    The terminal page says: "Reopening deletes the suppression for this case, so the next run raises
    it again. No other case is affected." This test reads that promise off the page, performs the
    reopen, runs again, and checks both halves: the case comes back, and the other case was never
    suppressed in the first place.
    """
    _statements, connect = _levels(monkeypatch, tmp_path)
    project = _project()

    first = pipeline.run_level_fitness(project, token="unused")
    conn = connect()
    try:
        case_id, decided_fp, _assertion = _decide_first_case(conn, first)
        page = app.case_page(conn, case_id)
        assert page is not None
        text = _text(page)
    finally:
        conn.close()

    assert "Reopening deletes the suppression for this case, so the next run raises it again." in text
    assert "hidden from future runs" in text

    conn = connect()
    try:
        cases.set_state(conn, case_id, "open", "harry")
        reopened = _text(app.case_page(conn, case_id))
    finally:
        conn.close()
    assert "hidden from future runs" not in reopened
    assert "Deletes the suppression" not in reopened

    time.sleep(GAP)
    second = pipeline.run_level_fitness(project, token="unused")
    conn = connect()
    try:
        raised = {finding["fingerprint"] for finding in _findings_for_run(conn, second.run_id)}
    finally:
        conn.close()

    assert decided_fp in raised
    # No other case was affected: the second finding is unrelated and still raises.
    assert len(second.case_ids) == 2


def _text(body: bytes) -> str:
    import html as htmllib
    import re

    page = body.decode("utf-8")
    page = re.sub(r"<style>.*?</style>", " ", page, flags=re.S)
    page = re.sub(r"<head>.*?</head>", " ", page, flags=re.S)
    page = re.sub(r"<[^>]+>", " ", page)
    return " ".join(htmllib.unescape(page).split())
