"""TESTOPS-5: sources are declared, not assumed.

The registry is what stops "nobody could look" collapsing into "we looked and there was nothing".
These tests pin the two states apart from stored rows in both directions, and pin the behaviour
that makes the declaration worth having: an available source that fails stops the run instead of
being quietly rewritten as absent.

Every store here is built under ``tmp_path`` through the product's own writers and read back through
the product's own read model. Nothing reads ``data/testops.db``, and nothing needs the network.
"""
from __future__ import annotations

import html as htmllib
import json
import os
import re

import level_fixtures as fixtures
import pytest
from testops import pipeline, queries, rebuild, sources
from testops.analysers import level_fitness
from testops.config import Project, Repo
from testops.store import db
from testops.web import app

TS = "2020-01-01T00:00:00+00:00"
COMMIT = "a" * 40


def _project(jira_key: str = "FIX", ado_org: str | None = "ORG") -> Project:
    return Project(key="fixture", product=Repo("o", "product"), test=Repo("o", "tests"),
                   jira_key=jira_key, ado_org=ado_org,
                   ado_project="proj" if ado_org else None)


def _run(tmp_path, monkeypatch, *, project: Project | None = None,
         registry: sources.Registry | None = None, token: str = "unused"):
    path, connect = fixtures.stub_pipeline(monkeypatch, pipeline, tmp_path)
    result = pipeline.run_level_fitness(project or _project(), token=token, registry=registry)
    return result, connect(path)


def _text(body: bytes | None) -> str:
    assert body is not None
    html = body.decode("utf-8")
    html = re.sub(r"<style>.*?</style>", " ", html, flags=re.S)
    html = re.sub(r"<head>.*?</head>", " ", html, flags=re.S)
    html = re.sub(r"<[^>]+>", " ", html)
    return " ".join(htmllib.unescape(html).split())


def _kind(registry: sources.Registry, source_id: str) -> sources.SourceKind:
    kind = registry.get(source_id)
    assert kind is not None, f"{source_id} is not declared"
    return kind


def _state(registry: sources.Registry, source_id: str) -> sources.SourceState:
    state = registry.state_of(source_id)
    assert state is not None, f"{source_id} is not declared"
    return state


# --------------------------------------------------------------------------- AC1

def test_every_source_declares_an_identity_and_the_capabilities_it_provides():
    registry = sources.registry()
    assert [kind.id for kind in registry] == ["github", "jira", "ado"]
    for kind in registry:
        assert kind.id and kind.title
        assert kind.capabilities
        assert kind.capabilities <= set(sources.CAPABILITIES)
    assert {kind.id for kind in registry.for_capability(sources.TEST_CODE)} == {"github"}
    assert {kind.id for kind in registry.for_capability(sources.REQUIREMENTS)} == {"jira", "ado"}
    assert {kind.id for kind in registry.for_capability(sources.TEST_EXECUTION)} == {"ado"}
    # GitHub is available through the existing collector; the MCP transport is deliberately not a
    # source kind, and the route is recorded so a later substitution is visible rather than implied.
    assert _state(registry, "github").state == sources.AVAILABLE
    assert _kind(registry, "github").route == "github-api"
    assert "MCP transport is out of scope" in _kind(registry, "github").note


def test_a_new_source_is_found_by_capability_without_touching_an_analyser():
    """The analyser names capabilities; the registry decides which source serves them."""
    fake = sources.SourceKind.absent(
        "confluence", "Confluence", (sources.REQUIREMENTS,),
        "this project's wiki is not configured for the run")
    registry = sources.Registry([*sources.registry(_project()), fake])

    assert fake in registry.for_capability(sources.REQUIREMENTS)
    missing = registry.missing(level_fitness.NEEDS | level_fitness.CONSULTS)
    assert missing == ["jira", "ado", "confluence"]
    claims = fixtures.analyse_fact_sheet(sources_missing=missing)
    assert claims
    assert all(claim.detail["sources_missing"] == missing for claim in claims)


def test_a_source_serving_two_needed_capabilities_is_counted_once():
    """GitHub provides code and test code; it is one repository, not two."""
    registry = sources.Registry([
        sources.SourceKind.available("github", "GitHub", (sources.CODE, sources.TEST_CODE),
                                     observed=7)])
    assessment = registry.assess(level_fitness.NEEDS)
    assert assessment.state == sources.FOUND
    assert assessment.observed == 7


# --------------------------------------------------------------------------- AC2

def test_every_source_that_is_not_available_says_why_and_who_decided():
    registry = sources.registry()
    for kind in registry:
        if not kind.state.available:
            assert kind.state.reason.strip()
    for name in ("jira", "ado"):
        state = _state(registry, name)
        assert state.state == sources.BLOCKED
        assert state.blocked_by == sources.QUILTER_POLICY
        assert "policy forbids" in state.reason
        assert "personal access token" in state.reason


def test_a_state_with_no_reason_is_refused_rather_than_assumed():
    with pytest.raises(ValueError, match="must say why"):
        sources.SourceState(sources.BLOCKED, blocked_by="someone")
    with pytest.raises(ValueError, match="must say why"):
        sources.SourceState(sources.ABSENT)
    with pytest.raises(ValueError, match="who blocked it"):
        sources.SourceState(sources.BLOCKED, reason="no access")
    with pytest.raises(ValueError, match="unknown source state"):
        sources.SourceState("assumed", reason="because")
    # A source nobody could look at has no count at all - not a count of zero.
    with pytest.raises(ValueError, match="cannot have an observed count"):
        sources.SourceState(sources.BLOCKED, reason="no access", blocked_by="policy", observed=0)


def test_an_undeclared_source_is_not_an_empty_one():
    """``state_of`` returning None is "not declared", and using it is refused, not empty."""
    registry = sources.Registry([sources.SourceKind.available("github", "GitHub", (sources.CODE,))])
    assert registry.state_of("jira") is None
    with pytest.raises(sources.SourceNotAvailable, match="never declared"):
        registry.use("jira", lambda: [])


def test_a_probe_that_fails_is_a_failure_not_an_absence():
    """A probe returns a state or raises; nothing converts its failure into ``absent``."""
    def broken():
        raise RuntimeError("probe unavailable")

    with pytest.raises(RuntimeError, match="probe unavailable"):
        sources.SourceKind.probed("probed", "Probed source", (sources.CODE,), broken)

    kind = sources.SourceKind.probed(
        "probed", "Probed source", (sources.CODE,),
        lambda: sources.SourceState(sources.ABSENT, reason="not installed on this host"))
    assert kind.state.state == sources.ABSENT
    assert kind.state.reason == "not installed on this host"

    with pytest.raises(TypeError, match="not a SourceState"):
        sources.SourceKind.probed("probed", "Probed source", (sources.CODE,), lambda: {})


def test_a_project_that_names_no_tracker_declares_no_tracker_source():
    """A source the project does not name is absent from the question, not blocked by policy."""
    registry = sources.registry(_project(jira_key="", ado_org=None))
    assert [kind.id for kind in registry] == ["github"]
    assert registry.missing(level_fitness.NEEDS | level_fitness.CONSULTS) == []
    # ... and asking for requirements anyway is a blind spot with its own reason, not a zero.
    assessment = registry.assess({sources.REQUIREMENTS})
    assert assessment.state == sources.NOT_ASSESSABLE
    assert assessment.blind_spots[0].source == ""
    assert "no source is declared" in assessment.blind_spots[0].reason


# --------------------------------------------------------------------------- AC3

def test_every_run_records_the_registry_in_its_snapshot(tmp_path, monkeypatch):
    result, conn = _run(tmp_path, monkeypatch)
    try:
        meta = json.loads(conn.execute("SELECT meta FROM snapshot WHERE id = ?",
                                       (result.snapshot_id,)).fetchone()["meta"])
    finally:
        conn.close()

    assert set(meta["sources"]) == {"github", "jira", "ado"}
    assert meta["sources"]["github"]["state"] == "available"
    assert meta["sources"]["github"]["route"] == "github-api"
    assert meta["sources"]["jira"]["state"] == "blocked"
    assert meta["sources"]["jira"]["reason"] == sources.QUILTER_NO_PAT
    assert meta["sources"]["jira"]["blocked_by"] == sources.QUILTER_POLICY
    assert meta["sources"]["ado"]["state"] == "blocked"
    assert meta["analysers"]["level_fitness"]["needs"] == ["code", "test_code"]
    assert meta["analysers"]["level_fitness"]["consults"] == ["requirements"]
    assert meta["sources_missing"] == ["jira", "ado"]

    # A reader reconstructs the run's view from the record alone: no probe, no live source.
    rebuilt = sources.Registry.from_record(meta["sources"])
    assert [kind.id for kind in rebuilt] == ["github", "jira", "ado"]
    assert _state(rebuilt, "jira").state == sources.BLOCKED
    assert _state(rebuilt, "jira").reason == sources.QUILTER_NO_PAT


DUPLICATE_FEATURE = """\
Feature: fact sheet
  Scenario: the fact sheet is served
    Given the fact sheet endpoint returns a sheet
    Then the response body carries stable fact anchors

  Scenario: the fact sheet is served again
    Given the fact sheet endpoint returns a sheet
    Then the response body carries stable fact anchors
"""


def test_a_duplication_run_records_the_registry_too(tmp_path, monkeypatch):
    """AC3 says every run, not only the level analyser's."""
    path, connect = fixtures.stub_pipeline(monkeypatch, pipeline, tmp_path,
                                           feature=DUPLICATE_FEATURE)
    result = pipeline.run_duplication(_project(), token="unused")
    conn = connect(path)
    try:
        meta = json.loads(conn.execute("SELECT meta FROM snapshot WHERE id = ?",
                                       (result.snapshot_id,)).fetchone()["meta"])
        rows = conn.execute("SELECT sources_missing FROM claim ORDER BY id").fetchall()
    finally:
        conn.close()

    assert rows, "the fixture must produce a duplicate claim"
    assert meta["sources"]["jira"]["state"] == "blocked"
    assert meta["analysers"]["duplication"]["needs"] == ["test_code"]
    assert all(json.loads(row["sources_missing"]) == ["jira", "ado"] for row in rows)


def test_a_snapshot_that_records_half_the_registry_cannot_be_rebuilt(tmp_path):
    """Declared sources without the analyser's needs cannot reproduce the assessment."""
    conn = db.connect(tmp_path / "half-registry.db")
    db.upsert_snapshot(
        conn, "snap-half", "fixture", TS, {"o/tests": COMMIT, "o/product": COMMIT},
        schema_version=2,
        meta={"arms": {"test": "o/tests", "product": "o/product"}, "sources_missing": [],
              "sources": sources.registry(_project()).record()})
    conn.commit()
    try:
        with pytest.raises(rebuild.SnapshotNotSelfContained, match="half of the source registry"):
            rebuild.load(conn, "snap-half")
    finally:
        conn.close()


# --------------------------------------------------------------------------- AC4

def test_a_claim_that_needs_an_absent_source_is_not_assessable_with_the_reason():
    registry = sources.Registry([
        sources.SourceKind.available(sources.GITHUB, "GitHub", (sources.CODE,), observed=3),
        sources.SourceKind.absent(
            "test-repo", "The test repository", (sources.TEST_CODE,),
            "the tests live in a repository this run cannot reach"),
    ])
    assessment = registry.assess(level_fitness.NEEDS)
    missing = registry.missing(level_fitness.NEEDS | level_fitness.CONSULTS)
    claims = fixtures.analyse_fact_sheet(sources_missing=missing, assessment=assessment)

    assert claims
    assert missing == ["test-repo"]
    for claim in claims:
        assert claim.detail["sources_missing"] == ["test-repo"]
        assert claim.detail["assessment"]["state"] == sources.NOT_ASSESSABLE
        spot = claim.detail["assessment"]["blind_spots"][0]
        assert spot["source"] == "test-repo"
        assert spot["state"] == sources.ABSENT
        assert spot["reason"] == "the tests live in a repository this run cannot reach"
        # The level verdict is a separate fact, and this ticket does not move it (AC9).
        assert claim.verdict in {"distinct", "gap", "review", "unplaced"}

    sentence = assessment.sentence()
    assert sentence.startswith("Cannot assess this claim")
    assert "the tests live in a repository this run cannot reach" in sentence


def test_sources_missing_is_derived_from_the_registry_not_a_hard_coded_list(tmp_path, monkeypatch):
    project = _project()
    fake = sources.SourceKind.absent(
        "confluence", "Confluence", (sources.REQUIREMENTS,),
        "this project's wiki is not configured for the run")
    registry = sources.Registry([*sources.registry(project), fake])
    result, conn = _run(tmp_path, monkeypatch, project=project, registry=registry)
    try:
        rows = conn.execute("SELECT sources_missing FROM claim ORDER BY id").fetchall()
        meta = json.loads(conn.execute("SELECT meta FROM snapshot WHERE id = ?",
                                       (result.snapshot_id,)).fetchone()["meta"])
    finally:
        conn.close()

    assert rows
    assert all(json.loads(row["sources_missing"]) == ["jira", "ado", "confluence"] for row in rows)
    assert meta["sources"]["confluence"]["state"] == "absent"
    assert meta["sources"]["confluence"]["reason"] == \
        "this project's wiki is not configured for the run"


# --------------------------------------------------------------------------- AC5

def _registry_with_test_repo(state: sources.SourceState) -> sources.Registry:
    return sources.Registry([
        sources.SourceKind.available(sources.GITHUB, "GitHub", (sources.CODE,),
                                     observed=state.observed or 0),
        sources.SourceKind("test-repo", "The test repository", frozenset({sources.TEST_CODE}),
                           state),
    ])


BLOCKED = _registry_with_test_repo(sources.SourceState(
    sources.BLOCKED, reason="no access has been granted for this run",
    blocked_by="the platform team"))
EMPTY = _registry_with_test_repo(sources.SourceState(sources.AVAILABLE, observed=0))


def _store(root, name: str, registry: sources.Registry):
    """A snapshot, run, claim, case and finding - written through the product's own writers."""
    conn = db.connect(root / name / f"{name}.db")
    snapshot, run, case = f"snap-{name}", f"run-{name}", f"case-{name}"
    missing = registry.missing(level_fitness.NEEDS | level_fitness.CONSULTS)
    db.upsert_snapshot(
        conn, snapshot, "fixture", TS, {"o/tests": COMMIT}, schema_version=2,
        meta={"sources_missing": missing, "sources": registry.record(),
              "analysers": {"level_fitness": {"needs": sorted(level_fitness.NEEDS),
                                              "consults": sorted(level_fitness.CONSULTS)}}})
    db.start_run(conn, run, "fixture", snapshot, "level_fitness", TS)
    claim_id = db.add_claim(
        conn, run, "level_fitness", level_fitness.version,
        "scenario:features/fact_sheet.feature#the fact sheet is usable",
        "This test asserts that the fact sheet is served.", "distinct", 0.8, [],
        schema_version=2, assertion_text="the fact sheet is served",
        assertion_path="features/fact_sheet.feature", assertion_line=3,
        assertion_commit=COMMIT, interaction_label="settled by the data as stored",
        interaction_code="I1", span=["api"], established_by="the words name a guarantee",
        sources_missing=missing, proposed_action="No change.")
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at,"
                 " summary) VALUES (?,?,?,?,?,?,?)",
                 (case, run, "fixture", "level_fitness", snapshot, TS, "{}"))
    conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                 " VALUES (?,?,?,?,?)",
                 (case, "the fact sheet is served", "info", "a" * 32, db.j([claim_id])))
    conn.commit()
    return conn, case


def test_an_absent_source_and_an_empty_source_are_different_verdicts_and_sentences(tmp_path):
    """The crux, in both directions, read from stored rows and rendered by the product's page."""
    blocked_conn, blocked_case = _store(tmp_path, "blocked", BLOCKED)
    try:
        blocked_claim = queries.finding_rows(blocked_conn, blocked_case)[0]["claims"][0]
        blocked_text = _text(app.case_page(blocked_conn, blocked_case))
    finally:
        blocked_conn.close()

    empty_conn, empty_case = _store(tmp_path, "empty", EMPTY)
    try:
        empty_claim = queries.finding_rows(empty_conn, empty_case)[0]["claims"][0]
        empty_text = _text(app.case_page(empty_conn, empty_case))
    finally:
        empty_conn.close()

    assert blocked_claim["assessment"]["state"] == sources.NOT_ASSESSABLE
    assert empty_claim["assessment"]["state"] == sources.ZERO
    assert blocked_claim["assessment"]["state"] != empty_claim["assessment"]["state"]

    blocked_sentence = blocked_claim["assessment"]["sentence"]
    empty_sentence = empty_claim["assessment"]["sentence"]
    assert "Cannot assess" in blocked_sentence
    assert "no access has been granted for this run" in blocked_sentence
    assert "real zero" not in blocked_sentence
    assert "real zero" in empty_sentence
    assert "Cannot assess" not in empty_sentence

    # The page says it too: a reader does not need the read model to see the difference.
    assert "Cannot assess" in blocked_text
    assert "real zero" not in blocked_text
    assert "real zero" in empty_text
    assert "Cannot assess" not in empty_text

    # And the blind spot's reason reaches section 5, not just the badge.
    assert "The test repository \u2014 blocked by the platform team" in blocked_text
    assert "no access has been granted for this run" in blocked_text


def test_a_needed_capability_with_no_source_is_a_blind_spot_not_a_clean_sheet(tmp_path):
    """A capability nobody declared a source for has no source id - and still must be named."""
    no_test_code = sources.Registry([
        sources.SourceKind.available(sources.GITHUB, "GitHub", (sources.CODE,), observed=4)])
    assert no_test_code.missing(level_fitness.NEEDS | level_fitness.CONSULTS) == []

    conn, case = _store(tmp_path, "no-source", no_test_code)
    try:
        claim = queries.finding_rows(conn, case)[0]["claims"][0]
        text = _text(app.case_page(conn, case))
    finally:
        conn.close()

    assert claim["sources_missing"] == []
    assert claim["assessment"]["state"] == sources.NOT_ASSESSABLE
    assert "no source is declared that could provide it" in claim["assessment"]["sentence"]
    assert "Cannot assess" in text
    assert "test code \u2014 absent: no source is declared that could provide it" in text
    assert "Every source needed for this claim was available" not in text


# --------------------------------------------------------------------------- AC6

def test_an_available_source_that_fails_stops_the_run_and_keeps_its_declared_state():
    registry = sources.Registry([
        sources.SourceKind.available("flaky", "The flaky source", (sources.CODE,))])

    def boom():
        raise RuntimeError("connection reset")

    with pytest.raises(sources.SourceFailed) as raised:
        registry.use("flaky", boom)
    assert "declared available" in str(raised.value)
    assert "connection reset" in str(raised.value)
    assert _state(registry, "flaky").state == sources.AVAILABLE


def test_a_blocked_source_is_refused_before_it_is_used():
    registry = sources.registry()
    called = []
    with pytest.raises(sources.SourceNotAvailable, match="declared blocked"):
        registry.use("jira", lambda: called.append(True))
    assert called == []
    assert _state(registry, "jira").state == sources.BLOCKED


def test_the_pipeline_fails_loudly_when_a_source_declared_available_fails(tmp_path, monkeypatch):
    path, connect = fixtures.stub_pipeline(monkeypatch, pipeline, tmp_path)

    def boom(repo, token, role="product"):
        raise RuntimeError("network down")

    monkeypatch.setattr(pipeline.github, "collect", boom)
    with pytest.raises(sources.SourceFailed):
        pipeline.run_level_fitness(_project(), token="unused")

    conn = connect(path)
    try:
        snapshots = conn.execute("SELECT COUNT(*) FROM snapshot").fetchone()[0]
        claims = conn.execute("SELECT COUNT(*) FROM claim").fetchone()[0]
    finally:
        conn.close()
    assert snapshots == 0, "a failed run must not leave a snapshot claiming the source was absent"
    assert claims == 0


# --------------------------------------------------------------------------- AC7

def test_the_case_page_names_the_reason_a_source_could_not_be_checked(tmp_path, monkeypatch):
    result, conn = _run(tmp_path, monkeypatch)
    try:
        assert result.case_ids
        text = _text(app.case_page(conn, result.case_ids[0]))
    finally:
        conn.close()

    assert "Not connected when this claim was checked" in text
    assert "Jira" in text
    assert "blocked by Quilter policy" in text
    assert "no credentials can be created for it" in text
    assert "personal access token" in text
    assert "Azure DevOps" in text


def test_a_project_with_no_tracker_says_requirements_could_not_be_checked(tmp_path, monkeypatch):
    """No source at all for a consulted capability is still a blind spot, not "all available"."""
    result, conn = _run(tmp_path, monkeypatch, project=_project(jira_key="", ado_org=None))
    try:
        assert result.case_ids
        text = _text(app.case_page(conn, result.case_ids[0]))
    finally:
        conn.close()

    assert "Every source needed for this claim was available" not in text
    assert "requirements \u2014 absent: no source is declared that could provide it" in text


# --------------------------------------------------------------------------- AC8

def test_no_source_needs_a_secret_to_be_declared(monkeypatch):
    """A source is declared from identity and policy; a credential is never part of the record."""
    for name in list(os.environ):
        monkeypatch.delenv(name, raising=False)

    registry = sources.registry()
    assert len(registry) == 3
    record = registry.record()

    keys: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                keys.add(key.lower())
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(record)
    for word in ("token", "secret", "password", "credential", "api_key", "pat"):
        assert not any(word in key for key in keys), (word, sorted(keys))

    payload = json.dumps(record, sort_keys=True)
    assert "ghp_" not in payload
    assert "Bearer" not in payload


def test_the_run_writes_no_credential_into_the_snapshot(tmp_path, monkeypatch):
    secret = "SECRET-TOKEN-DO-NOT-STORE"
    result, conn = _run(tmp_path, monkeypatch, token=secret)
    try:
        stored = "\n".join(
            (row[0] or "") for row in conn.execute("SELECT meta FROM snapshot"))
        stored += "\n".join(
            (row[0] or "") for row in conn.execute("SELECT artefact_versions FROM snapshot"))
        stored += "\n".join(
            (row[0] or "") for row in conn.execute("SELECT statement FROM claim"))
    finally:
        conn.close()
    assert secret not in stored
