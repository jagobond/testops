"""TESTOPS-17: a clean bill requires having looked.

Three states, and only one of them is allowed to sound reassuring:

  (1) **not assessed** - no registry was consulted for this claim, so nobody looked. The page says
      so. This is what a claim written with a default must produce, and what a run whose snapshot
      recorded no registry migrates to.
  (2) **assessed, none missing** - the registry was consulted and nothing this claim needed was
      missing. Only this state may render "Every source needed for this claim was available."
  (3) **assessed, some missing** - the registry was consulted and named the sources it could not
      consult.

Every test builds a real store under ``tmp_path`` and reads through the product's own writers, read
model and page. The distinction under test is a fact about stored rows, so a mocked dict would assert
the sentence rather than the state it is supposed to report.
"""
from __future__ import annotations

import html as htmllib
import json
import re
import sqlite3
from typing import Any

import pytest

import v1_store
import v2_store
from support_fixtures import TS
from testops import queries
from testops.store import db, migrate
from testops.web import app

PATH = "features/panel_api.feature"
LINE = 17
COMMIT = "a" * 40
CASE = "case-sources"
RUN = "run-sources"
SNAP = "snap-sources"
STATEMENT = ("This test asserts that the panel is served. Only a browser works that out, and this "
             "test only reads the responses the server sends instead, so nothing checks it.")

# The exact sentences AC2 and AC3 ask for. Written out, not imported from the product: a test that
# compares the page to a constant the page itself owns would pass while the wording drifted.
NOT_ASSESSED_SENTENCE = (
    "Nothing was checked against any source for this claim, so nothing here says its sources were "
    "clean.")
NONE_MISSING_SENTENCE = "Every source needed for this claim was available."
SOME_MISSING_SENTENCE = "Not connected when this claim was checked"


def _seed(tmp_path, *, sources_assessed: bool | None, missing, name: str = "store"):
    """A snapshot, a run, one v2 claim and the case that renders it.

    ``sources_assessed=None`` omits the argument entirely, which is how a caller that never heard of
    the field writes a claim. That is the path AC4 is about.
    """
    conn = db.connect(tmp_path / f"{name}.db")
    db.upsert_snapshot(conn, SNAP, "fixture", TS, {"owner/test": COMMIT}, schema_version=2)
    db.start_run(conn, RUN, "fixture", SNAP, "level_fitness", TS)
    db.finish_run(conn, RUN, "ok", TS)
    fields: dict[str, Any] = dict(
        assertion_text="the panel is served",
        assertion_path=PATH, assertion_line=LINE, assertion_commit=COMMIT,
        interaction_label="needs a browser", interaction_code="I4", span=["api"],
        established_by="asserts an accessibility property the browser computes",
        proposed_action='Move the step "the panel is served" into a test that drives a browser.',
    )
    if sources_assessed is not None:
        fields["sources_assessed"] = sources_assessed
    if missing is not _OMITTED:
        fields["sources_missing"] = missing
    claim_id = db.add_claim(conn, RUN, "level_fitness", "0.8.0",
                            f"scenario:{PATH}#the panel is served", STATEMENT, "gap", 0.5, [],
                            schema_version=2, **fields)
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at,"
                 " summary) VALUES (?,?,?,?,?,?,?)",
                 (CASE, RUN, "fixture", "level_fitness", SNAP, TS, "{}"))
    conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                 " VALUES (?,?,?,?,?)",
                 (CASE, STATEMENT[:160], "high", "a" * 32, db.j([claim_id])))
    conn.commit()
    return conn, claim_id


_OMITTED = object()


def _text(body: bytes) -> str:
    html = body.decode("utf-8")
    html = re.sub(r"<style>.*?</style>", " ", html, flags=re.S)
    html = re.sub(r"<head>.*?</head>", " ", html, flags=re.S)
    html = re.sub(r"<[^>]+>", " ", html)
    return " ".join(htmllib.unescape(html).split())


def _page(conn) -> str:
    body = app.case_page(conn, CASE)
    assert body is not None
    return _text(body)


# --------------------------------------------------------------------------- AC1: three states

def test_not_assessed_is_a_stored_state_of_its_own(tmp_path):
    conn, claim_id = _seed(tmp_path, sources_assessed=False, missing=_OMITTED)
    try:
        row = conn.execute("SELECT sources_missing, sources_assessed FROM claim WHERE id = ?",
                           (claim_id,)).fetchone()
        claim = queries.claim_read(conn, claim_id)
    finally:
        conn.close()

    assert row["sources_assessed"] == 0
    assert row["sources_missing"] is None
    assert claim["sources_assessed"] is False
    assert claim["sources_missing"] is None
    assert claim["sources_state"] == queries.SOURCES_NOT_ASSESSED


def test_assessed_with_nothing_missing_is_a_different_stored_value(tmp_path):
    conn, claim_id = _seed(tmp_path, sources_assessed=True, missing=[])
    try:
        row = conn.execute("SELECT sources_missing, sources_assessed FROM claim WHERE id = ?",
                           (claim_id,)).fetchone()
        claim = queries.claim_read(conn, claim_id)
    finally:
        conn.close()

    assert row["sources_assessed"] == 1
    assert row["sources_missing"] == "[]"
    assert claim["sources_missing"] == []
    assert claim["sources_state"] == queries.SOURCES_NONE_MISSING


def test_assessed_with_names_missing_keeps_the_names(tmp_path):
    conn, claim_id = _seed(tmp_path, sources_assessed=True, missing=["jira", "ado"])
    try:
        claim = queries.claim_read(conn, claim_id)
    finally:
        conn.close()

    assert claim["sources_assessed"] is True
    assert claim["sources_missing"] == ["jira", "ado"]
    assert claim["sources_state"] == queries.SOURCES_SOME_MISSING


# --------------------------------------------------------------------------- AC4: the default

def test_the_writer_default_is_not_assessed(tmp_path):
    """A claim written with no source arguments at all records "not assessed"."""
    conn, claim_id = _seed(tmp_path, sources_assessed=None, missing=_OMITTED)
    try:
        claim = queries.claim_read(conn, claim_id)
        text = _page(conn)
    finally:
        conn.close()

    assert claim["sources_state"] == queries.SOURCES_NOT_ASSESSED
    assert NOT_ASSESSED_SENTENCE in text
    assert NONE_MISSING_SENTENCE not in text


def test_a_list_with_no_assessment_record_is_not_stored_as_a_fact(tmp_path):
    """The exact defect: ``sources_missing=[]`` from a caller that never asked the registry."""
    conn, claim_id = _seed(tmp_path, sources_assessed=None, missing=[])
    try:
        row = conn.execute("SELECT sources_missing, sources_assessed FROM claim WHERE id = ?",
                           (claim_id,)).fetchone()
        text = _page(conn)
    finally:
        conn.close()

    assert row["sources_assessed"] == 0, "a list alone must not be read as an assessment"
    assert row["sources_missing"] is None
    assert NONE_MISSING_SENTENCE not in text
    assert NOT_ASSESSED_SENTENCE in text


def test_the_database_refuses_assessed_with_nothing_recorded(tmp_path):
    """The pairing is a CHECK, so a writer that skips ``db.add_claim`` is refused too."""
    conn, _ = _seed(tmp_path, sources_assessed=None, missing=_OMITTED)
    try:
        with pytest.raises(sqlite3.IntegrityError) as refused:
            conn.execute(
                "INSERT INTO claim (run_id, analyser, analyser_version, subject_ref, statement,"
                " verdict, confidence, support, schema_version, assertion_text, assertion_path,"
                " assertion_line, assertion_commit, sources_missing, sources_assessed)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (RUN, "level_fitness", "0.8.0", "scenario:a#b", "hand written", "gap", 0.1, "[]",
                 2, "Given something", PATH, LINE, COMMIT, None, 1))
        assert "claim_sources_assessed_pairing" in str(refused.value)
    finally:
        conn.close()


def test_the_database_refuses_a_list_with_no_assessment(tmp_path):
    conn, _ = _seed(tmp_path, sources_assessed=None, missing=_OMITTED)
    try:
        with pytest.raises(sqlite3.IntegrityError) as refused:
            conn.execute(
                "INSERT INTO claim (run_id, analyser, analyser_version, subject_ref, statement,"
                " verdict, confidence, support, schema_version, assertion_text, assertion_path,"
                " assertion_line, assertion_commit, sources_missing, sources_assessed)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (RUN, "level_fitness", "0.8.0", "scenario:a#c", "hand written", "gap", 0.1, "[]",
                 2, "Given something", PATH, LINE, COMMIT, "[]", 0))
        assert "claim_sources_assessed_pairing" in str(refused.value)
    finally:
        conn.close()


# --------------------------------------------------------------------------- AC2, AC3, AC5

def test_all_three_states_render_their_own_sentence_from_stored_rows(tmp_path):
    """The three sentences, read back from three stores, asserted exactly and cross-checked."""
    pages: dict[str, str] = {}
    states: dict[str, str] = {}
    for name, assessed, missing in (
            ("not_assessed", False, _OMITTED),
            ("none_missing", True, []),
            ("some_missing", True, ["jira", "ado"])):
        conn, claim_id = _seed(tmp_path / name, sources_assessed=assessed, missing=missing,
                               name=name)
        try:
            states[name] = queries.claim_read(conn, claim_id)["sources_state"]
            pages[name] = _page(conn)
        finally:
            conn.close()

    assert states == {"not_assessed": queries.SOURCES_NOT_ASSESSED,
                      "none_missing": queries.SOURCES_NONE_MISSING,
                      "some_missing": queries.SOURCES_SOME_MISSING}

    assert NOT_ASSESSED_SENTENCE in pages["not_assessed"]
    assert NONE_MISSING_SENTENCE in pages["none_missing"]
    assert SOME_MISSING_SENTENCE in pages["some_missing"]

    # Each phrase belongs to exactly one state: a reader can tell which kind of silence it is.
    phrases = {"not_assessed": NOT_ASSESSED_SENTENCE, "none_missing": NONE_MISSING_SENTENCE,
               "some_missing": SOME_MISSING_SENTENCE}
    for state, phrase in phrases.items():
        for other, other_phrase in phrases.items():
            if other != state:
                assert other_phrase not in pages[state], f"{state}'s page carries {other}'s wording"

    # The assessed-and-clean state names the sources it could not consult, by name.
    assert "Jira" in pages["some_missing"] and "Azure DevOps" in pages["some_missing"]


def test_a_not_assessed_claim_renders_a_sentence_not_a_blank_not_an_exception(tmp_path):
    conn, _ = _seed(tmp_path, sources_assessed=False, missing=_OMITTED)
    try:
        body = app.case_page(conn, CASE)
    finally:
        conn.close()

    assert body is not None
    section = body.decode("utf-8").split("4. What could not be checked")[1]
    section = section.split("5. Decision")[0]
    assert "Nothing was checked against any source for this claim" in section
    assert "source needed" not in section.lower()


# --------------------------------------------------------------------------- AC6: migration

def test_a_v2_store_migrates_to_an_honest_state_per_claim(tmp_path):
    path = tmp_path / "v2.db"
    v2_store.build(path)

    conn = db.connect(path)  # the migration runs here
    try:
        rows = {row["id"]: row for row in conn.execute(
            "SELECT id, statement, verdict, sources_missing, sources_assessed FROM claim")}
        registry_claim = queries.claim_read(conn, v2_store.REGISTRY_CLAIM)
        bare_claim = queries.claim_read(conn, v2_store.NO_REGISTRY_CLAIM)
        version = migrate.stored_version(conn)
        bare_meta = json.loads(conn.execute(
            "SELECT meta FROM snapshot WHERE id = 'snap-no-registry'").fetchone()[0])
    finally:
        conn.close()

    assert version == migrate.CURRENT_VERSION == 3

    # The run that recorded the registry was assessed, and its stored list is what it said.
    assert rows[v2_store.REGISTRY_CLAIM]["sources_assessed"] == 1
    assert rows[v2_store.REGISTRY_CLAIM]["sources_missing"] == v2_store.MISSING
    assert registry_claim["sources_state"] == queries.SOURCES_SOME_MISSING

    # The run whose snapshot has no registry meta is not assessed - even though its row carries the
    # same list. A list without a registry behind it was a default, and the migration says so.
    assert rows[v2_store.NO_REGISTRY_CLAIM]["sources_assessed"] == 0
    assert rows[v2_store.NO_REGISTRY_CLAIM]["sources_missing"] is None
    assert bare_claim["sources_state"] == queries.SOURCES_NOT_ASSESSED
    assert bare_claim["sources_missing"] is None

    # Nothing about what was claimed moved.
    for row in rows.values():
        assert row["statement"] == v2_store.STATEMENT
        assert row["verdict"] == "gap"

    # And nothing was deleted: the snapshot still records what the run said about its sources, so a
    # reader can see why the claim is now not assessed.
    assert bare_meta["sources_missing"] == ["jira", "ado"]


def test_the_migration_leaves_no_claim_that_reads_as_a_clean_bill(tmp_path):
    """No migrated claim is assessed-and-clean unless its own snapshot recorded the registry."""
    path = tmp_path / "v2-bills.db"
    v2_store.build(path)
    conn = db.connect(path)
    try:
        clean = conn.execute("SELECT COUNT(*) FROM claim WHERE sources_assessed = 1"
                             " AND sources_missing = '[]'").fetchone()[0]
        assessed = conn.execute("SELECT COUNT(*) FROM claim WHERE sources_assessed = 1").fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM claim").fetchone()[0]
    finally:
        conn.close()

    assert total == 2
    assert assessed == 1
    assert clean == 0, "a claim with no registry behind it was migrated into a clean bill"


def test_a_v1_store_migrates_to_not_assessed(tmp_path):
    path = tmp_path / "v1.db"
    v1_store.build(path)
    conn = db.connect(path)
    try:
        row = conn.execute("SELECT sources_assessed, sources_missing FROM claim WHERE id = ?",
                           (v1_store.CLAIM_ID,)).fetchone()
        claim = queries.claim_read(conn, v1_store.CLAIM_ID)
    finally:
        conn.close()

    assert row["sources_assessed"] == 0
    assert row["sources_missing"] is None
    assert claim["sources_state"] == queries.SOURCES_NOT_ASSESSED


def test_the_migrated_claim_table_is_shaped_like_a_new_one(tmp_path):
    migrated_path = tmp_path / "migrated.db"
    v2_store.build(migrated_path)
    fresh_path = tmp_path / "fresh.db"

    db.connect(migrated_path).close()
    db.connect(fresh_path).close()

    def definition(path):
        conn = sqlite3.connect(path)
        try:
            columns = [tuple(row[1:]) for row in conn.execute("PRAGMA table_info(claim)")]
            sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'claim'").fetchone()[0]
        finally:
            conn.close()
        return columns, sql

    migrated_columns, migrated_sql = definition(migrated_path)
    fresh_columns, fresh_sql = definition(fresh_path)

    assert migrated_columns == fresh_columns
    assert migrated_sql.replace('"claim"', "claim") == fresh_sql
    assert "claim_sources_assessed_pairing" in migrated_sql


# --------------------------------------------------------------------------- the analyser seam

def test_an_analysed_claim_with_no_registry_is_not_assessed(tmp_path):
    """The defect's own path: the analyser's default used to write ``sources_missing = []``."""
    import level_fixtures as fixtures
    from testops.analysers import level_fitness

    claims = fixtures.analyse_fact_sheet()
    assert claims
    for claim in claims:
        assert claim.detail["sources_assessed"] is False
        assert claim.detail["sources_missing"] is None
        assert claim.verdict in {"distinct", "gap", "review", "unplaced"}
