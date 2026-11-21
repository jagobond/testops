"""TESTOPS-14: a levels run records both arms, and every claim carries its observations.

What is asserted here, from the store rather than from the returned objects:

- AC1: the run writes artefacts for the test arm as well as the product arm, and the snapshot it
  wrote is sufficient to rebuild the claim set with no other snapshot and no network.
- AC2: a claim's coordinates find the feature file it was analysed from, in its own snapshot.
- AC3: a claim whose steps bound carries support - observation ids that resolve to the step-binding
  rows - and a claim whose steps bound nothing carries an explicit ``[]``, never NULL.
- AC4: the case page renders those observations with a sentence saying what each shows, instead of
  "no observations at these coordinates".
- AC5: rebuilding from the snapshot id alone reproduces the original claims exactly, support ids
  included, because the ids are read back from the snapshot's own rows.

Every test builds its own store under ``tmp_path`` through the real ``run_level_fitness`` and the
in-memory repository fixture; nothing reads ``data/testops.db``.
"""
from __future__ import annotations

import json
import re

import level_fixtures as fixtures
import pytest
import v1_store
from testops import pipeline, queries, rebuild
from testops.config import Project, Repo
from testops.links import GITHUB
from testops.store import db
from testops.web import app

UNBOUND_FEATURE = """\
Feature: fact sheet

  Scenario: nothing here is bound
    Given a fact sheet exists
    Then the sky is blue
"""

# The product arm is a different repository at a different commit - as it is in life. The shared
# stub hands both arms the same Collected, which would make "which repository is this path in" a
# question with two true answers and prove nothing about the read model.
PRODUCT_COMMIT = "b" * 40


def _run(tmp_path, monkeypatch, *, feature: str = fixtures.PIPELINE_FEATURE,
         jira_key: str = ""):
    from testops.collectors.github import Collected

    path, connect = fixtures.stub_pipeline(monkeypatch, pipeline, tmp_path, feature=feature)
    files = {"features/fact_sheet.feature": ("sha-feature", "feature"),
             "steps/FactSheetSteps.cs": ("sha-steps", "stepdef")}
    monkeypatch.setattr(
        pipeline.github, "collect",
        lambda repo, token, role="product", commit=None: Collected(
            commit=fixtures.COMMIT if role == "test" else PRODUCT_COMMIT, files=files))
    project = Project(key="fixture", product=Repo("o", "product"), test=Repo("o", "tests"),
                      jira_key=jira_key)
    result = pipeline.run_level_fitness(project, token="unused")
    return result, connect(path), project


def _artefacts(conn, snapshot_id):
    return [{"uri": row["uri"], "kind": row["kind"], "meta": json.loads(row["meta"])}
            for row in conn.execute("SELECT uri, kind, meta FROM artefact WHERE snapshot_id = ?"
                                    " ORDER BY id", (snapshot_id,))]


def _claims(conn, run_id):
    return [dict(row) for row in conn.execute("SELECT * FROM claim WHERE run_id = ? ORDER BY id",
                                              (run_id,))]


def _observation(conn, observation_id):
    row = conn.execute(
        """SELECT o.extractor, o.key, o.value, a.uri, a.kind, a.snapshot_id
             FROM observation o JOIN artefact a ON a.id = o.artefact_id WHERE o.id = ?""",
        (observation_id,)).fetchone()
    return None if row is None else dict(row)


def _identity(claim) -> str:
    """The whole claim, detail included - support ids are part of what must be reproduced."""
    return json.dumps({"subject": claim.subject_ref, "statement": claim.statement,
                       "verdict": claim.verdict, "confidence": claim.confidence,
                       "detail": claim.detail}, sort_keys=True)


# --------------------------------------------------------------------------- AC1

def test_a_levels_run_records_artefacts_for_both_arms(tmp_path, monkeypatch):
    result, conn, _ = _run(tmp_path, monkeypatch)
    try:
        artefacts = _artefacts(conn, result.snapshot_id)
    finally:
        conn.close()

    roles = {a["meta"].get("role") for a in artefacts}
    assert roles == {"test", "product"}, roles
    test_files = [a for a in artefacts if a["meta"]["role"] == "test"]
    assert any(a["kind"] == "feature" and a["uri"].endswith(":features/fact_sheet.feature")
               for a in test_files), "the feature every claim is about was not recorded"
    assert any(a["kind"] == "stepdef" for a in test_files), "the step definitions were not recorded"


def test_the_snapshot_alone_is_enough_to_rebuild_the_claim_set(tmp_path, monkeypatch):
    result, conn, _ = _run(tmp_path, monkeypatch)
    try:
        snapshots = conn.execute("SELECT COUNT(*) FROM snapshot").fetchone()[0]
        claims, stats, snapshot = rebuild.rebuild(conn, result.snapshot_id)
    finally:
        conn.close()

    assert snapshots == 1, "the rebuild must not depend on a second snapshot being present"
    assert snapshot.test_commit == fixtures.COMMIT
    assert stats["features"] == 1
    assert [_identity(c) for c in claims] == [_identity(c) for c in result.claims]


def test_the_snapshot_records_what_the_run_could_not_consult(tmp_path, monkeypatch):
    result, conn, _ = _run(tmp_path, monkeypatch, jira_key="TOPS")
    try:
        meta = json.loads(conn.execute("SELECT meta FROM snapshot WHERE id = ?",
                                       (result.snapshot_id,)).fetchone()["meta"])
    finally:
        conn.close()
    assert meta["sources_missing"] == ["jira"]
    assert meta["arms"] == {"test": "o/tests", "product": "o/product"}


def test_a_snapshot_that_does_not_record_its_arms_is_refused(tmp_path):
    """A v1 store has no arm roles and no blind spots; a rebuild would have to invent both."""
    path = tmp_path / "v1-rebuild.db"
    v1_store.build(path)
    conn = db.connect(path)
    try:
        with pytest.raises(rebuild.SnapshotNotSelfContained, match="test arm"):
            rebuild.rebuild(conn, v1_store.SNAPSHOT)
    finally:
        conn.close()


def test_an_older_store_gains_the_snapshot_meta_column_without_inventing_a_value(tmp_path):
    path = tmp_path / "v1-meta.db"
    v1_store.build(path)
    conn = db.connect(path)
    try:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(snapshot)")]
        meta = conn.execute("SELECT meta FROM snapshot").fetchone()["meta"]
    finally:
        conn.close()
    assert "meta" in columns
    assert meta == "{}", "an older snapshot recorded nothing, and must not read as 'nothing missing'"


# --------------------------------------------------------------------------- AC2

def test_a_claims_coordinates_find_the_feature_file_it_was_analysed_from(tmp_path, monkeypatch):
    result, conn, _ = _run(tmp_path, monkeypatch)
    try:
        recorded = _artefacts(conn, result.snapshot_id)
        rows = _claims(conn, result.run_id)
        repo = queries._repo_for_coordinates(conn, "fixture", fixtures.COMMIT,
                                             "features/fact_sheet.feature")
    finally:
        conn.close()

    assert repo == "o/tests", "the read model cannot name the repository a claim points at"
    for row in rows:
        matches = [a for a in recorded
                   if (m := GITHUB.match(a["uri"]))
                   and m["sha"] == row["assertion_commit"] and m["path"] == row["assertion_path"]]
        assert matches, f"no artefact records {row['assertion_path']}@{row['assertion_commit']}"
        assert matches[0]["kind"] == "feature"
        assert matches[0]["meta"]["role"] == "test"


# --------------------------------------------------------------------------- AC3

def test_every_bound_claim_carries_the_step_bindings_it_rests_on(tmp_path, monkeypatch):
    result, conn, _ = _run(tmp_path, monkeypatch)
    try:
        rows = _claims(conn, result.run_id)
        observations = {}
        for row in rows:
            for observation_id in json.loads(row["support"]):
                observations[observation_id] = _observation(conn, observation_id)
    finally:
        conn.close()

    assert len(rows) == 3
    for row in rows:
        support = json.loads(row["support"])
        assert support, f"a bound claim recorded no support: {row['assertion_text']!r}"
        for observation_id in support:
            observation = observations[observation_id]
            assert observation is not None, f"support id {observation_id} does not resolve"
            assert observation["extractor"] == "stepbinding"
            assert observation["key"].startswith("binding:")
            assert json.loads(observation["value"])["layer"] in {
                "ui", "api", "controller", "engine", "storage"}


def test_a_claim_whose_step_bound_nothing_carries_an_explicit_empty_support(tmp_path, monkeypatch):
    result, conn, _ = _run(tmp_path, monkeypatch, feature=UNBOUND_FEATURE)
    try:
        rows = _claims(conn, result.run_id)
    finally:
        conn.close()

    assert len(rows) == 1
    assert rows[0]["verdict"] == "unplaced"
    assert rows[0]["support"] == "[]", "empty support must be a recorded list, not NULL"


def test_a_binding_observation_points_at_the_line_that_binds_the_step(tmp_path, monkeypatch):
    result, conn, _ = _run(tmp_path, monkeypatch)
    try:
        sample = None
        for row in _claims(conn, result.run_id):
            for observation_id in json.loads(row["support"]):
                candidate = _observation(conn, observation_id)
                if candidate["key"] == "binding:then:the response body carries stable fact anchors":
                    sample = candidate
    finally:
        conn.close()

    assert sample is not None, "the binding the claim rests on was not recorded"
    value = json.loads(sample["value"])
    assert value["verb"] == "Then" and value["layer"] == "api"
    assert value["line"] == 10, "the [Then(...)] attribute is on line 10 of the fixture step file"
    assert sample["uri"].endswith(":steps/FactSheetSteps.cs")


# --------------------------------------------------------------------------- AC4

def test_the_case_page_shows_the_observations_a_claim_rests_on(tmp_path, monkeypatch):
    result, conn, _ = _run(tmp_path, monkeypatch)
    try:
        assert result.case_ids, "the fixture must raise at least one actionable claim"
        body = app.case_page(conn, result.case_ids[0]).decode("utf-8")
    finally:
        conn.close()

    assert "no observations at these coordinates" not in body
    assert "The observations this claim rests on, recorded in this run:" in body
    assert "step definition for" in body
    assert "drives the HTTP API" in body
    # Every rendered evidence item is a link with a statement of what it shows.
    items = re.findall(r"<li>(.*?)</li>", body, re.S)
    assert items
    for item in items:
        assert "<a href=" in item and " \u2014 " in item, item
    assert "FactSheetSteps.cs" in body


# --------------------------------------------------------------------------- AC5

def test_rebuilding_twice_from_one_snapshot_produces_the_same_claims(tmp_path, monkeypatch):
    result, conn, _ = _run(tmp_path, monkeypatch)
    try:
        first = [_identity(c) for c in rebuild.rebuild(conn, result.snapshot_id)[0]]
        second = [_identity(c) for c in rebuild.rebuild(conn, result.snapshot_id)[0]]
    finally:
        conn.close()
    assert first == second == [_identity(c) for c in result.claims]


def test_a_second_run_on_the_same_commits_writes_a_new_snapshot(tmp_path, monkeypatch):
    result, conn, project = _run(tmp_path, monkeypatch, jira_key="TOPS")
    try:
        first_claims = _claims(conn, result.run_id)
        first_artefacts = _artefacts(conn, result.snapshot_id)
    finally:
        conn.close()

    # Without this shim the second run shares the first run's id - same second - and the snapshot
    # id is what is under test, so the clock is moved on rather than the assertions relaxed.
    monkeypatch.setattr(pipeline, "dt", _DtShim())
    second = pipeline.run_level_fitness(project, token="unused")
    # ``db.connect`` is itself patched by the fixture, so the store is opened directly; the rebuild
    # only needs a connection that can answer SQL.
    import sqlite3

    conn = sqlite3.connect(tmp_path / "pipeline.db")
    conn.row_factory = sqlite3.Row
    try:
        artefacts_now = _artefacts(conn, result.snapshot_id)
        stored_first = _claims(conn, result.run_id)
        rebuilt = [_identity(c) for c in rebuild.rebuild(conn, result.snapshot_id)[0]]
        second_claims = _claims(conn, second.run_id)
    finally:
        conn.close()

    assert second.snapshot_id != result.snapshot_id, "a re-run must not reuse a snapshot"
    assert second.snapshot_id.endswith("-r2")
    assert artefacts_now == first_artefacts, "the first snapshot's artefacts were mutated"
    assert stored_first == first_claims
    assert rebuilt == [_identity(c) for c in result.claims]
    assert len(second_claims) == len(first_claims)


class _Later:
    """A datetime whose now() is a second later, so two runs in one test do not share a run id."""

    @staticmethod
    def now(tz=None):
        import datetime as real

        return real.datetime.now(tz) + real.timedelta(seconds=1)

    def __getattr__(self, item):
        import datetime as real

        return getattr(real.datetime, item)


class _DtShim:
    """Stands in for the ``datetime`` module *inside pipeline only*, one second in the future."""

    def __init__(self):
        import datetime as real

        self.date = real.date
        self.timezone = real.timezone
        self.timedelta = real.timedelta
        self.datetime = _Later()
