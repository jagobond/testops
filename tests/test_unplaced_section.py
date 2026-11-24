"""TESTOPS-57 / TESTOPS-60: the claims a run could not place have a section of their own.

An ``unplaced`` claim is not a finding, so it never becomes a case. TESTOPS-57 gave those claims a
section, each with the step's words, the two nearest declared patterns and an anchor. TESTOPS-60
makes that section scale: the claims are grouped by why the tool could not place them, the shared
reason is stated once per group, each group folds past a stated threshold into a disclosure with
an honest count, and the anchors are the claim ids rather than ordinals.

The tests build a real store under ``tmp_path`` and render the run page. They do not read the
product's ``data/`` directory and do not contact a server.
"""
from __future__ import annotations

import html as htmllib
import re

import pytest

import support_fixtures as fixtures
from testops.store import db
from testops.web import app

RUN = "run-unplaced"
SNAPSHOT = "snap-unplaced"
COMMIT = "a" * 40
PATH = "features/room.feature"
NEAR = "User will get validation/mandatory error message: {string}"
FAR = "Visitor will get validation/mandatory error message: {string}"
THRESHOLD = app.UNPLACED_PREVIEW


def _text(body: bytes) -> str:
    text = body.decode("utf-8")
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(htmllib.unescape(text).split())


def _store(tmp_path, count: int = 3, *, patterns: bool = True):
    conn = db.connect(tmp_path / "unplaced.db")
    fixtures.seed_run(conn, run_id=RUN, snapshot_id=SNAPSHOT)
    artefact = db.add_artefact(
        conn, SNAPSHOT, f"github:test/repo@{COMMIT}:{PATH}", "feature", "b" * 40)
    if patterns:
        for pattern in (NEAR, FAR):
            db.add_observation(conn, artefact, "stepbinding", "1",
                               f"binding:Then:{pattern}",
                               {"pattern": pattern, "layer": "ui"})
    ids = []
    for number in range(1, count + 1):
        ids.append(_add(conn, number))
    conn.commit()
    return conn, ids


def _add(conn, number: int, *, text: str | None = None,
         established_by: str | None = None) -> int:
    text = text or f"User will get mandatory error message: {number}"
    return db.add_claim(
        conn, RUN, "level_fitness", "0.6.0",
        f"scenario:{PATH}#scenario {number}",
        "The step reads a message the suite never declared.",
        "unplaced", 0.0, [], schema_version=2,
        assertion_text=text,
        assertion_path=PATH, assertion_line=number, assertion_commit=COMMIT,
        interaction_label="unclear what would settle it",
        established_by=established_by if established_by is not None else
        'no binding matches these words; the nearest declared patterns are '
        f'"{NEAR}", "{FAR}"',
    )


def _section(body: bytes) -> str:
    markup = body.decode("utf-8")
    return markup.split("What this run could not place", 1)[1].split("<h2", 1)[0]


def _entries(section: str) -> list[tuple[int, str]]:
    """(claim id, rendered step text) for every entry, shown or folded."""
    out = []
    for match in re.finditer(r'<li id="unplaced-claim-(\d+)">(.*?)</li>', section, re.S):
        text = re.search(r'<p class="claimtext">(.*?)</p>', match.group(2), re.S)
        out.append((int(match.group(1)), htmllib.unescape(text.group(1)) if text else ""))
    return out


def test_every_unplaced_claim_is_listed_with_its_words_and_anchor(tmp_path):
    conn, ids = _store(tmp_path)
    try:
        body, status = app.run_response(conn, RUN)
    finally:
        conn.close()

    assert status == 200
    section = _section(body)
    assert section.count('<li id="unplaced-claim-') == 3
    for claim_id, number in zip(ids, (1, 2, 3)):
        assert f'id="unplaced-claim-{claim_id}"' in section
        assert f"User will get mandatory error message: {number}" in section
    # The two nearest patterns are shown for each claim.
    assert section.count(NEAR) >= 3
    assert section.count(FAR) >= 3


def test_the_count_and_the_entries_are_the_same_derived_number(tmp_path):
    conn, _ = _store(tmp_path)
    try:
        first, _ = app.run_response(conn, RUN)
        first_section = _section(first)
        first_count = int(re.search(r"(\d+) steps? in this run", first_section).group(1))
        first_entries = first_section.count('<li id="unplaced-claim-')
        assert first_count == first_entries == 3

        # A fourth claim on the same run changes both numbers together, because both are read
        # from the rows rather than from a stored count.
        _add(conn, 4, established_by="no binding matches these words")
        conn.commit()
        second, _ = app.run_response(conn, RUN)
        second_section = _section(second)
        second_count = int(re.search(r"(\d+) steps? in this run", second_section).group(1))
        second_entries = second_section.count('<li id="unplaced-claim-')
        assert second_count == second_entries == 4
    finally:
        conn.close()


def test_each_entry_wears_the_soft_tone_and_not_the_alarm(tmp_path):
    conn, _ = _store(tmp_path)
    try:
        body, _ = app.run_response(conn, RUN)
    finally:
        conn.close()

    section = _section(body)
    assert section.count('class="badge verdict soft"') == 3
    assert "hot" not in section


def test_the_section_is_honest_and_uses_no_banned_phrases(tmp_path):
    conn, _ = _store(tmp_path)
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
    conn, _ = _store(tmp_path, count=0)
    try:
        body, _ = app.run_response(conn, RUN)
    finally:
        conn.close()

    assert "What this run could not place" not in body.decode("utf-8")


# --------------------------------------------------------------------------
# AC1 - grouped by reason, with a count and a sentence saying what is shared
# --------------------------------------------------------------------------

def test_claims_are_grouped_by_reason_with_counts_and_a_shared_sentence(tmp_path):
    conn, _ = _store(tmp_path, count=0)
    try:
        for number in (1, 2, 3):
            _add(conn, number)
        for number in (4, 5):
            _add(conn, number, established_by="the analyser recorded no comparison")
        conn.commit()
        body, _ = app.run_response(conn, RUN)
    finally:
        conn.close()

    section = _section(body)
    groups = re.findall(r'<h3 class="unplaced-group">(.*?)</h3>', section, re.S)
    assert len(groups) == 2, groups
    assert "No binding matches these words" in groups[0]
    assert "3 steps" in groups[0]
    assert "Other reasons" in groups[1]
    assert "2 steps" in groups[1]

    # Each group's sentence says what its entries have in common, before the first row.
    common = re.findall(r'<p class="unplaced-common">(.*?)</p>', section, re.S)
    assert len(common) == 2
    assert "These 3 steps have this in common" in common[0]
    assert "no step binding declared by this run matches their words" in common[0]
    assert "These 2 steps have this in common" in common[1]

    # The group counts sum to the total sentence.
    total = int(re.search(r"(\d+) steps? in this run", section).group(1))
    assert total == 5
    assert total == len(_entries(section))
    # A reason shared by a whole "other" group is stated once, not on each of its rows.
    assert _text(section.encode()).count("the analyser recorded no comparison") == 1


# --------------------------------------------------------------------------
# AC2 - a stated threshold, first N, and an honest count never truncated silently
# --------------------------------------------------------------------------

@pytest.mark.parametrize("count", [0, 1, THRESHOLD - 1, THRESHOLD, THRESHOLD + 1, 500])
def test_the_threshold_is_stated_and_never_truncates_silently(tmp_path, count):
    conn, _ = _store(tmp_path, count=count)
    try:
        body, _ = app.run_response(conn, RUN)
    finally:
        conn.close()

    page = body.decode("utf-8")
    if count == 0:
        assert "What this run could not place" not in page
        return

    section = _section(body)
    entries = _entries(section)
    total = int(re.search(r"(\d+) steps? in this run", section).group(1))
    assert total == count == len(entries), (total, count, len(entries))

    shown = min(count, THRESHOLD)
    if count <= THRESHOLD:
        assert "<details" not in section, "a group at or under the threshold was folded"
        assert "folded below" not in section
    else:
        hidden = count - THRESHOLD
        assert "<details" in section
        assert f"{shown} of {count} shown in this group; the other {hidden} are folded below" \
            in _text(section.encode())
        assert f"Show the other {hidden} of {count} steps in this group" in section
        # The disclosure holds exactly the rest: nothing is dropped and nothing is duplicated.
        inside = section.split("<details", 1)[1]
        assert inside.count('<li id="unplaced-claim-') == hidden


# --------------------------------------------------------------------------
# AC3 - the repeated reason clause is stated once per group
# --------------------------------------------------------------------------

def test_the_reason_clause_is_stated_once_per_group_not_once_per_entry(tmp_path):
    conn, _ = _store(tmp_path, count=5)
    try:
        body, _ = app.run_response(conn, RUN)
    finally:
        conn.close()

    section = _section(body)
    text = _text(section.encode())
    assert text.count("Why they were not assessed: no binding matches these words.") == 1
    # The heading carries the phrase too, but no entry repeats the reason clause on its own.
    assert text.count("Why it was not assessed") == 0
    assert text.lower().count("no binding matches these words") == 2  # heading + group sentence
    # Entries keep what is specific to them: the step and its nearest patterns.
    assert text.count("Nearest declared patterns:") == 5


# --------------------------------------------------------------------------
# AC4 - anchors are structural and survive pruning; ordinals are gone
# --------------------------------------------------------------------------

def test_anchors_survive_deleting_the_first_claim_of_a_group(tmp_path):
    conn, ids = _store(tmp_path, count=5)
    try:
        first, _ = app.run_response(conn, RUN)
        before = dict(_entries(_section(first)))
        assert len(before) == 5

        # Prune the FIRST claim of the group: with positional anchors every later ordinal would
        # shift by one, which is exactly the failure this ticket exists to remove.
        removed = ids[0]
        conn.execute("DELETE FROM claim WHERE id = ?", (removed,))
        conn.commit()

        second, _ = app.run_response(conn, RUN)
        section = _section(second)
        after = dict(_entries(section))
    finally:
        conn.close()

    assert removed not in after
    assert len(after) == 4
    for claim_id, words in after.items():
        assert before[claim_id] == words, (
            f"anchor #unplaced-claim-{claim_id} now resolves to different words")

    # The structural anchor is the only anchor: no ordinal id is rendered, because an ordinal
    # would silently re-point at a different claim after this delete.
    for claim_id, words in after.items():
        assert f'id="unplaced-claim-{claim_id}"' in section
    assert not re.search(r'id="unplaced-\d+"', section), (
        "an ordinal anchor survived; it would shift with position after a prune")
    assert "anchor-legacy" not in section


# --------------------------------------------------------------------------
# AC5 - a snapshot with no declared patterns is pinned
# --------------------------------------------------------------------------

def test_a_run_with_no_declared_patterns_claims_no_nearest_patterns(tmp_path):
    conn, _ = _store(tmp_path, count=3, patterns=False)
    try:
        body, _ = app.run_response(conn, RUN)
    finally:
        conn.close()

    section = _section(body)
    text = _text(section.encode()).lower()
    assert "declared no binding patterns" in text
    assert "no nearest patterns are claimed for these steps" in text
    assert "nearest declared patterns" not in text
    assert "Nearest declared patterns:" not in section
    assert len(_entries(section)) == 3


# --------------------------------------------------------------------------
# AC6 - counts agree per group and in total
# --------------------------------------------------------------------------

def test_every_group_count_agrees_with_its_entries_and_the_total(tmp_path):
    conn, _ = _store(tmp_path, count=0)
    try:
        for number in range(1, 8):
            _add(conn, number)
        for number in range(8, 10):
            _add(conn, number, established_by="a different recorded reason")
        conn.commit()
        body, _ = app.run_response(conn, RUN)
    finally:
        conn.close()

    section = _section(body)
    total = int(re.search(r"(\d+) steps? in this run", section).group(1))
    rendered_total = len(_entries(section))
    assert total == rendered_total == 9

    group_counts = [int(number) for number in
                    re.findall(r'<span class="meta unplaced-group-count">(\d+) steps?</span>',
                               section)]
    assert group_counts == [7, 2]
    assert sum(group_counts) == total
