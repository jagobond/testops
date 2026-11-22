"""TESTOPS-12 AC1: one verification pass carries one label, or the page says why it does not.

The label answers "what settles it", and one run answers in one way. Where a scenario still shows
two labels - a claim naming nothing that could settle it, or a claim only a browser can work out -
the page must say so, or a reader can only conclude the pass was two runs. The explanation is read
from the claim's own stored rows, never from a live analysis.

Every test builds a real store in ``tmp_path`` and renders through the product's read model: the
question is a fact about stored rows, and a mocked dict would assert the sentence rather than the
fact it reports.
"""
from __future__ import annotations

import html as htmllib
import re
from typing import Any

import level_fixtures as fixtures
from testops import queries
from testops.analysers import level_fitness
from testops.store import db
from testops.web import app

TS = "2020-01-01T00:00:00+00:00"
CASE = "case-pass"
RUN = "run-pass"
SNAP = "snap-pass"
COMMIT = "c" * 40
PATH = "features/approval_queue.feature"
SCENARIO = f"scenario:{PATH}#The audit counts what rests on a batch decision"
OTHER_SCENARIO = f"scenario:{PATH}#A proposal is refused"
CODE = re.compile(r"\b(I[1-4]|KP)\b")

RESPONSE = "settled by the response the server sends"
UNCLEAR = "unclear what would settle it"
BROWSER = "needs a browser"


def _claim(conn, line: int, text: str, label: str, code: str,
           subject: str = SCENARIO) -> int:
    fields: dict[str, Any] = dict(
        assertion_text=text, assertion_path=PATH, assertion_line=line,
        assertion_commit=COMMIT, interaction_label=label, interaction_code=code,
        span=["api"], established_by="the words name the response the tool sends",
        sources_missing=[], proposed_action='No change: keep the step where it is.',
    )
    return db.add_claim(conn, RUN, "level_fitness", "0.10.0", subject,
                        "The assertion is in the words below.", "distinct", 0.8, [],
                        schema_version=2, **fields)


def _store(tmp_path, claims):
    """A snapshot, a run, one case - and the claims the test chooses to put in one pass."""
    conn = db.connect(tmp_path / "pass.db")
    db.upsert_snapshot(conn, SNAP, "fixture", TS, {"owner/test": COMMIT}, schema_version=3)
    db.start_run(conn, RUN, "fixture", SNAP, "level_fitness", TS)
    db.finish_run(conn, RUN, "ok", TS)
    ids = [_claim(conn, *claim) for claim in claims]
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at,"
                 " summary) VALUES (?,?,?,?,?,?,?)",
                 (CASE, RUN, "fixture", "level_fitness", SNAP, TS, "{}"))
    conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                 " VALUES (?,?,?,?,?)", (CASE, "the audit counts", "high", "a" * 32, db.j(ids)))
    conn.commit()
    return conn, ids


def _read(conn, claim_id: int) -> dict:
    claim = queries.claim_read(conn, claim_id)
    assert claim is not None
    return claim


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


def test_a_pass_with_two_labels_says_on_the_page_why(tmp_path):
    """A claim nothing settles beside a claim the response settles: the run is still one run."""
    conn, ids = _store(tmp_path, [
        (7, "it reports how many admitted facts rest on a batch decision", RESPONSE, "I1"),
        (9, "that count is correct for the store it was run against", UNCLEAR, "U"),
    ])
    try:
        note = _read(conn, ids[0])["pass_note"]
        text = _page(conn)
    finally:
        conn.close()

    assert note, "a pass with two labels offered no explanation"
    assert '"settled by the response the server sends"' in note
    assert '"unclear what would settle it"' in note
    assert note.count("for 1 assertion") == 2, note
    assert "The run is one" in note
    assert not CODE.search(note), f"the explanation carries a code: {note!r}"
    # TESTOPS-23: the page says the same fact in its own words, not in the analyser's sentence.
    assert ("This scenario holds other assertions that need something different to settle them" in
            text)
    assert ("one is settled by the response the server sends and one says nothing about what "
            "would settle it" in text)
    assert note not in text


def test_a_pass_with_one_label_offers_no_explanation(tmp_path):
    """The common case must stay quiet: two response claims are one answer, twice."""
    conn, ids = _store(tmp_path, [
        (7, "the Tier 1 fact is refused for the missing approver", RESPONSE, "I2"),
        (9, "the Tier 2 fact is admitted", RESPONSE, "I1"),
    ])
    try:
        notes = [_read(conn, claim_id)["pass_note"] for claim_id in ids]
        text = _page(conn)
    finally:
        conn.close()

    assert notes == [None, None]
    assert "answers to one run" not in text
    assert "The run is one" not in text


def test_the_explanation_is_scoped_to_the_claim_s_own_scenario(tmp_path):
    """A second scenario with a different label is a different pass, and must not be blamed here."""
    conn, ids = _store(tmp_path, [
        (7, "it reports how many admitted facts rest on a batch decision", RESPONSE, "I1"),
        (3, "the proposal is refused", BROWSER, "I4", OTHER_SCENARIO),
    ])
    try:
        notes = [_read(conn, claim_id)["pass_note"] for claim_id in ids]
    finally:
        conn.close()

    assert notes == [None, None]


def test_a_v1_claim_with_no_label_does_not_manufacture_an_explanation(tmp_path):
    """A label nobody recorded is not a second answer; NULL is absence, not a phrase."""
    rows = [("settled by the data as stored", "I1"), (None, None), ("settled by the data as stored", "I1")]
    assert queries.pass_note_from_rows(rows) is None


def test_the_label_and_the_explanation_never_contradict_the_statement():
    """The explanation names what the assertions ask, which is what the statement's opener says."""
    note = queries.pass_note_from_rows([(RESPONSE, "I1"), (UNCLEAR, "U")])
    assert note is not None
    assert "one is about a guarantee on the data as stored" in note
    assert "one names nothing that could settle it" in note


# --- TESTOPS-18: the label names the answer; it is never the sentence -----------------------------

def _every_label() -> set[str]:
    """Every label the analyser can produce, as a value - not as a template."""
    labels = set(level_fitness.INTERACTION_LABEL.values())
    for instrument in ("api", "controller", "engine", "storage", "ui", "unknown"):
        for interaction in ("I1", "I2", "KP", "I3", "I4", "U"):
            labels.add(level_fitness._label(interaction, instrument))
    return labels


def test_no_statement_contains_a_label_value():
    """AC1: a label is a phrase for what settles a claim, and a statement never quotes it back.

    The leak this catches is not hypothetical: the pass note used a label as the object of "one is
    about", producing "one is about settled by the response the server sends". If a label can leak
    into the explanation, it can leak into a statement, so the corpus is checked against every
    label the analyser can write.
    """
    claims = fixtures.analyse_fact_sheet()
    assert claims
    labels = _every_label()
    seen = {claim.detail["interaction_label"] for claim in claims}
    assert seen <= labels
    for claim in claims:
        for label in labels:
            assert label not in claim.statement, (label, claim.statement)


def test_every_statement_shape_leaves_the_labels_out():
    """The same guarantee for the shapes the fact-sheet fixture does not reach (all verdicts)."""
    labels = _every_label()
    clause = "the record is present"
    for instrument in ("api", "controller", "engine", "storage", "ui", "unknown"):
        for interaction in ("I1", "I2", "KP", "I3", "I4", "U"):
            for verdict in ("distinct", "unplaced", "gap", "review"):
                statement = level_fitness._statement(
                    interaction, clause, verdict, instrument,
                    level_fitness.WHY_META if verdict == "unplaced" else "")
                for label in labels:
                    assert label not in statement, (label, verdict, statement)


def test_a_pass_note_with_two_labels_reads_as_one_sentence():
    """AC2: two answers, explained without a placeholder and without a doubled preposition."""
    note = queries.pass_note_from_rows([(RESPONSE, "I1"), (BROWSER, "I4")])
    assert note is not None
    assert ("one is about a guarantee on the data as stored and one is about what only a browser "
            "works out") in note
    assert "about settled by" not in note
    assert "about needs a browser" not in note
    assert "  " not in note
    assert "; one is about" not in note
    assert note.endswith("not in which instrument read them.")


def test_a_pass_note_with_three_labels_reads_as_a_list():
    """AC2: the three-label case joins its clauses like a reader would write them."""
    note = queries.pass_note_from_rows([(RESPONSE, "I1"), (UNCLEAR, "U"), (BROWSER, "I4")])
    assert note is not None
    assert ("one is about a guarantee on the data as stored, one names nothing that could settle "
            "it, and one is about what only a browser works out") in note
    assert "about settled by" not in note
    assert "about unclear" not in note
    assert note.count("one is about") + note.count("one names") == 3
    # The quoted labels are a list too: one ", and" before the last item, not one between all three.
    assert note.count(", and \"") == 1, note
    assert "\" for 1 assertion, and" in note, note


def test_a_label_with_no_code_is_never_used_to_build_the_sentence():
    """AC1: a row that records a label but no code cannot explain itself from the label.

    Older rows carry the label without an interaction code; the fallback that interpolated the
    label is exactly the defect the reviewer saw. The note still says why one run has two answers,
    and it says nothing it cannot stand behind.
    """
    note = queries.pass_note_from_rows([(RESPONSE, None), (BROWSER, "")])
    assert note is not None
    assert "The run is one:" in note
    tail = note.split("The run is one:", 1)[1]
    for label in (RESPONSE, BROWSER):
        assert label not in tail, tail
    assert f'"{RESPONSE}" for 1 assertion' in note
    assert f'"{BROWSER}" for 1 assertion' in note
