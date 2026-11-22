"""TESTOPS-16: three empty-evidence states, and they must never share wording.

(a) the run recorded no observations at all - a count the page states, with no claim about why;
(b) the run recorded observations, but none of them bears on this claim - we looked, nothing here;
(c) a v1 claim, recorded before provenance was captured.

Each test builds a real store in ``tmp_path`` and renders the case page through the product's own
read model. Nothing is mocked: the distinction under test is a fact about stored rows, and a mocked
dict would assert the sentence rather than the fact it is supposed to report.
"""
from __future__ import annotations

import html as htmllib
import re
from typing import Any

from testops import queries
from testops.store import db
from testops.web import app

TS = "2020-01-01T00:00:00+00:00"
CASE = "case-empty"
RUN = "run-empty"
SNAP = "snap-empty"
COMMIT = "c" * 40
PATH = "features/panel_api.feature"
LINE = 17
STATEMENT = ("This test asserts that the panel is served. Only a browser works that out, and this "
             "test only reads the responses the server sends instead, so nothing checks it.")

NOTHING_RECORDED = "This run holds no observations"
NOTHING_BEARS = "Nothing in this run bears on this claim"
V1_WORDS = "recorded before provenance was captured"
# TESTOPS-12 AC-b: a zero count cannot prove why the run recorded nothing, so the page must not say.
NO_WHY = "predates observation recording"


def _seed(tmp_path, *, schema_version=2, observations=(), artefact=True):
    """A snapshot, a run, a case, one claim - and the observations the test chooses to record.

    ``observations`` is a list of ``(uri, key, value)``: the artefact is created for that uri, and
    the observation attached to it. An empty list writes no observation rows at all, which is the
    store whose run holds no observations.
    """
    conn = db.connect(tmp_path / f"empty-{schema_version}-{len(observations)}.db")
    db.upsert_snapshot(conn, SNAP, "fixture", TS, {"owner/test": COMMIT},
                       schema_version=schema_version)
    db.start_run(conn, RUN, "fixture", SNAP, "level_fitness", TS)
    db.finish_run(conn, RUN, "ok", TS)
    fields: dict[str, Any] = {}
    if schema_version == 2:
        fields = dict(
            assertion_text="the panel is served",
            assertion_path=PATH, assertion_line=LINE, assertion_commit=COMMIT,
            interaction_label="needs a browser", interaction_code="I4", span=["api"],
            established_by="asserts an accessibility property the browser computes",
            sources_missing=[], proposed_action='Move the step "the panel is served" into a test.',
        )
    claim_id = db.add_claim(conn, RUN, "level_fitness", "0.8.0",
                            f"scenario:{PATH}#the panel is served", STATEMENT, "gap", 0.5, [],
                            schema_version=schema_version, **fields)
    # The claim's own artefact exists even in the run that recorded no observations: a snapshot is
    # what was collected, and an observation is what was extracted from it.
    if artefact:
        db.add_artefact(conn, SNAP, f"github:owner/test@{COMMIT}:{PATH}", "feature", "0" * 40)
    for uri, key, value in observations:
        artefact_id = db.add_artefact(conn, SNAP, uri, "feature", "0" * 40)
        db.add_observation(conn, artefact_id, "gherkin", "1.0.0", key, value)
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at,"
                 " summary) VALUES (?,?,?,?,?,?,?)",
                 (CASE, RUN, "fixture", "level_fitness", SNAP, TS, "{}"))
    conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                 " VALUES (?,?,?,?,?)", (CASE, STATEMENT[:160], "high", "a" * 32, db.j([claim_id])))
    conn.commit()
    return conn, claim_id


def _text(body: bytes) -> str:
    html = body.decode("utf-8")
    html = re.sub(r"<style>.*?</style>", " ", html, flags=re.S)
    html = re.sub(r"<head>.*?</head>", " ", html, flags=re.S)
    html = re.sub(r"<[^>]+>", " ", html)
    return " ".join(htmllib.unescape(html).split())


def _claim(conn, claim_id):
    claim = queries.claim_read(conn, claim_id)
    assert claim is not None
    return claim


def _page(conn) -> str:
    body = app.case_page(conn, CASE)
    assert body is not None
    return _text(body)


# --------------------------------------------------------------------------- (a) nothing recorded

def test_a_run_that_recorded_no_observations_says_so(tmp_path):
    conn, claim_id = _seed(tmp_path)
    try:
        claim = _claim(conn, claim_id)
        text = _page(conn)
    finally:
        conn.close()

    assert claim["support"] == []
    assert claim["evidence"] == []
    assert claim["observations_recorded"] == 0
    assert NOTHING_RECORDED in text
    assert NOTHING_BEARS not in text
    assert V1_WORDS not in text
    # AC-b: the count is stated; the reason for it is not invented.
    assert NO_WHY not in text
    assert "snapshot holds 1 artefact, none of which produced an observation" in text


def test_a_run_that_collected_nothing_says_that_rather_than_guessing_why(tmp_path):
    """Same zero, different store fact: nothing was collected at all. The page says so, and no more."""
    conn, claim_id = _seed(tmp_path, artefact=False)
    try:
        claim = _claim(conn, claim_id)
        text = _page(conn)
    finally:
        conn.close()

    assert claim["observations_recorded"] == 0
    assert claim["artefacts_recorded"] == 0
    assert NOTHING_RECORDED in text
    assert "snapshot holds no artefacts either, so nothing was collected" in text
    assert NO_WHY not in text


def test_a_run_with_artefacts_but_no_observation_rows_still_counts_as_nothing_recorded(tmp_path):
    """Artefacts proving the run happened do not turn 'nobody extracted anything' into evidence."""
    conn, claim_id = _seed(tmp_path, observations=[
        (f"github:owner/test@{COMMIT}:other.feature",
         "scenario:only bound by a later extractor", {"line": 3, "steps": 1}),
    ])
    conn.execute("DELETE FROM observation")
    conn.commit()
    try:
        claim = _claim(conn, claim_id)
        text = _page(conn)
    finally:
        conn.close()

    assert claim["observations_recorded"] == 0
    assert NOTHING_RECORDED in text
    assert NOTHING_BEARS not in text
    assert NO_WHY not in text


# --------------------------------------------------------------------------- (b) looked, none here

def test_a_run_that_recorded_observations_none_bearing_says_what_it_recorded(tmp_path):
    conn, claim_id = _seed(tmp_path, observations=[
        (f"github:owner/test@{COMMIT}:features/other.feature",
         "scenario:the report is downloadable", {"line": 3, "steps": 4}),
        (f"github:owner/test@{COMMIT}:features/other.feature",
         "binding:Given:the report exists", {"pattern": "the report exists", "layer": "api",
                                            "line": 12, "suite": "features/other.feature"}),
        (f"github:owner/test@{COMMIT}:features/other.feature",
         "scenario:a second report", {"line": 21, "steps": 2}),
    ])
    try:
        claim = _claim(conn, claim_id)
        text = _page(conn)
    finally:
        conn.close()

    assert claim["support"] == []
    assert claim["evidence"] == []              # nothing at the claim's own coordinates
    assert claim["observations_recorded"] == 3
    assert NOTHING_BEARS in text
    assert "The run recorded 3 observations in total" in text
    assert NOTHING_RECORDED not in text
    assert V1_WORDS not in text


def test_the_count_is_a_singular_sentence_when_the_run_recorded_one(tmp_path):
    conn, claim_id = _seed(tmp_path, observations=[
        (f"github:owner/test@{COMMIT}:features/other.feature",
         "scenario:the report is downloadable", {"line": 3, "steps": 4}),
    ])
    try:
        claim = _claim(conn, claim_id)
        text = _page(conn)
    finally:
        conn.close()

    assert claim["observations_recorded"] == 1
    assert "The run recorded 1 observation in total" in text
    assert "The run recorded 1 observations in total" not in text


# --------------------------------------------------------------------------- (c) v1 claim

def test_a_v1_claim_keeps_provenance_not_captured_wording(tmp_path):
    conn, claim_id = _seed(tmp_path, schema_version=1)
    try:
        claim = _claim(conn, claim_id)
        text = _page(conn)
    finally:
        conn.close()

    assert claim["schema_version"] == 1
    assert claim["evidence"] is None      # not recorded, not "nothing bears"
    assert V1_WORDS in text
    assert NOTHING_BEARS not in text
    assert NOTHING_RECORDED not in text


# --------------------------------------------------------------------------- all three, no overlap

def test_the_three_states_never_share_wording(tmp_path):
    """Each phrase belongs to exactly one state; a reader can tell which kind of nothing it is."""
    stores = {}

    conn, cid = _seed(tmp_path / "a")
    try:
        stores["nothing_recorded"] = (_claim(conn, cid), _page(conn))
    finally:
        conn.close()

    conn, cid = _seed(tmp_path / "b", observations=[
        (f"github:owner/test@{COMMIT}:features/other.feature",
         "scenario:the report is downloadable", {"line": 3, "steps": 4}),
    ])
    try:
        stores["nothing_bears"] = (_claim(conn, cid), _page(conn))
    finally:
        conn.close()

    conn, cid = _seed(tmp_path / "c", schema_version=1)
    try:
        stores["v1"] = (_claim(conn, cid), _page(conn))
    finally:
        conn.close()

    phrases = {"nothing_recorded": NOTHING_RECORDED, "nothing_bears": NOTHING_BEARS,
               "v1": V1_WORDS}
    for state, phrase in phrases.items():
        text = stores[state][1]
        assert phrase in text, f"{state} is not distinguishable: {text}"
        for other, other_phrase in phrases.items():
            if other == state:
                continue
            assert other_phrase not in text, f"{state}'s page also carries {other}'s wording"

    # The count is a fact only the state that has a run with observations can print.
    assert stores["nothing_bears"][0]["observations_recorded"] == 1
    assert stores["nothing_recorded"][0]["observations_recorded"] == 0


# --------------------------------------------------------------------------- AC5

def test_the_verdict_is_unchanged_and_the_schema_is_untouched(tmp_path):
    """This ticket changes wording only: same verdict, same columns."""
    conn, claim_id = _seed(tmp_path, observations=[
        (f"github:owner/test@{COMMIT}:features/other.feature",
         "scenario:the report is downloadable", {"line": 3, "steps": 4}),
    ])
    try:
        claim = _claim(conn, claim_id)
        columns = [r[1] for r in conn.execute("PRAGMA table_info(claim)").fetchall()]
        version = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'"
                               ).fetchone()
    finally:
        conn.close()

    assert claim["verdict"] == "gap"
    assert "observations_recorded" not in columns      # a read-model field, not a column
    assert version is not None
