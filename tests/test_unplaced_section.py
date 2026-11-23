"""TESTOPS-57: the claims a run could not place have a section of their own.

An ``unplaced`` claim is not a finding, so it never becomes a case. Before this ticket the run
page reduced those claims to a count and a sentence. The section added here lists them, each with
the step's words, the two nearest declared patterns, and a stable anchor a reader can cite.

The tests build a real store under ``tmp_path`` and render the run page. They do not read the
product's ``data/`` directory and do not contact a server.
"""
from __future__ import annotations

import html as htmllib
import re

import support_fixtures as fixtures
from testops.store import db
from testops.web import app

RUN = "run-unplaced"
SNAPSHOT = "snap-unplaced"
COMMIT = "a" * 40
PATH = "features/room.feature"
NEAR = "User will get validation/mandatory error message: {string}"
FAR = "Visitor will get validation/mandatory error message: {string}"


def _text(body: bytes) -> str:
    text = body.decode("utf-8")
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(htmllib.unescape(text).split())


def _store(tmp_path, count: int = 3):
    conn = db.connect(tmp_path / "unplaced.db")
    fixtures.seed_run(conn, run_id=RUN, snapshot_id=SNAPSHOT)
    artefact = db.add_artefact(
        conn, SNAPSHOT, f"github:test/repo@{COMMIT}:{PATH}", "feature", "b" * 40)
    for pattern in (NEAR, FAR):
        db.add_observation(conn, artefact, "stepbinding", "1",
                           f"binding:Then:{pattern}", {"pattern": pattern, "layer": "ui"})
    for number in range(1, count + 1):
        db.add_claim(
            conn, RUN, "level_fitness", "0.6.0",
            f"scenario:{PATH}#scenario {number}",
            "The step reads a message the suite never declared.",
            "unplaced", 0.0, [], schema_version=2,
            assertion_text=f"User will get mandatory error message: {number}",
            assertion_path=PATH, assertion_line=number, assertion_commit=COMMIT,
            interaction_label="unclear what would settle it",
            established_by='no binding matches these words; the nearest declared patterns are '
                           f'"{NEAR}", "{FAR}"',
        )
    conn.commit()
    return conn


def _section(body: bytes) -> str:
    markup = body.decode("utf-8")
    return markup.split("What this run could not place", 1)[1].split("<h2", 1)[0]


def test_every_unplaced_claim_is_listed_with_its_words_and_anchor(tmp_path):
    conn = _store(tmp_path)
    try:
        body, status = app.run_response(conn, RUN)
    finally:
        conn.close()

    assert status == 200
    section = _section(body)
    assert section.count('<li id="unplaced-') == 3
    for number in (1, 2, 3):
        assert f'id="unplaced-{number}"' in section
        assert f"User will get mandatory error message: {number}" in section
    # The two nearest patterns are shown for each claim.
    assert section.count(NEAR) >= 3
    assert section.count(FAR) >= 3


def test_the_count_and_the_entries_are_the_same_derived_number(tmp_path):
    conn = _store(tmp_path)
    try:
        first, _ = app.run_response(conn, RUN)
        first_section = _section(first)
        first_count = int(re.search(r"(\d+) steps? in this run", first_section).group(1))
        first_entries = first_section.count('<li id="unplaced-')
        assert first_count == first_entries == 3

        # A fourth claim on the same run changes both numbers together, because both are read
        # from the rows rather than from a stored count.
        db.add_claim(
            conn, RUN, "level_fitness", "0.6.0", f"scenario:{PATH}#scenario 4",
            "The step reads a message the suite never declared.", "unplaced", 0.0,
            [], schema_version=2, assertion_text="User will get mandatory error message: 4",
            assertion_path=PATH, assertion_line=4, assertion_commit=COMMIT,
            established_by="no binding matches these words")
        conn.commit()
        second, _ = app.run_response(conn, RUN)
        second_section = _section(second)
        second_count = int(re.search(r"(\d+) steps? in this run", second_section).group(1))
        second_entries = second_section.count('<li id="unplaced-')
        assert second_count == second_entries == 4
    finally:
        conn.close()


def test_each_entry_wears_the_soft_tone_and_not_the_alarm(tmp_path):
    conn = _store(tmp_path)
    try:
        body, _ = app.run_response(conn, RUN)
    finally:
        conn.close()

    section = _section(body)
    assert section.count('class="badge verdict soft"') == 3
    assert "hot" not in section


def test_the_section_is_honest_and_uses_no_banned_phrases(tmp_path):
    conn = _store(tmp_path)
    try:
        body, _ = app.run_response(conn, RUN)
    finally:
        conn.close()

    section = _section(body)
    text = _text(section.encode("utf-8")).lower()
    assert "not assessed" in text
    assert "no binding matches these words" in text
    assert "nearest declared patterns" in text
    # Where the nearest patterns are known, the section says why they did not match.
    assert "none of them matches these words" in text
    assert "unsupported ecosystem" not in text
    assert "could not be tied to a layer" not in text
    # No invented resolution: the section does not tell the reader what to change.
    assert "should" not in text
    assert "rewrite" not in text


def test_a_run_with_no_unplaced_claims_has_no_section(tmp_path):
    conn = _store(tmp_path, count=0)
    try:
        body, _ = app.run_response(conn, RUN)
    finally:
        conn.close()

    assert "What this run could not place" not in body.decode("utf-8")
