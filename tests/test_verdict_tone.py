"""TESTOPS-52 AC1-AC3: every verdict has a declared tone, and the page wears it.

The blind author found ``Cannot assess`` served as ``<strong class="verdict hot">`` - the alarm red
used for ``Checked, but this repeats another test`` - so uncertainty and a settled finding were
told apart by words alone. ``tests/contracts`` P4 caught it from the outside; these tests pin the
mechanism:

  * AC2: ``testops/web/tone.py`` covers every name the store has ever accepted, current and
    retired, and the table has no name the store would refuse. A new verdict cannot appear tinted
    by accident, and cannot appear untinted either.
  * AC1: the tone of a verdict is the declared one - never a default that catches the rest.
  * AC3: on a rendered case page, "Cannot assess" and a settled verdict differ structurally, in
    their class attribute, not only in their wording.
"""
from __future__ import annotations

import html as htmllib
from html.parser import HTMLParser

import pytest

import test_claim_headline as rows
import test_source_registry as registry_fixture
import test_verdict_vocabulary as vocabulary
from testops.store import db, verdicts
from testops.web import app, tone


def _vocabulary(tmp_path) -> tuple[frozenset[str], frozenset[str]]:
    """(current, ever) read from a store this build created - the database's own answer."""
    conn = db.connect(tmp_path / "vocabulary.db")
    try:
        return verdicts.current(conn), verdicts.ever_emitted(conn)
    finally:
        conn.close()


# --------------------------------------------------------------------------- AC2

def test_every_verdict_the_store_accepts_has_a_declared_tone(tmp_path):
    _current, ever = _vocabulary(tmp_path)
    assert ever, "the store accepted no verdict names, so the comparison would be vacuous"
    undeclared = sorted(name for name in ever if name not in tone.VERDICT_TONE)
    assert not undeclared, (
        f"verdicts with no declared tone: {undeclared}. Every verdict a page can render - current "
        "or retired - must be toned in testops/web/tone.py.")


def test_the_declared_tones_are_exactly_the_stores_vocabulary(tmp_path):
    """No stale entries either: a tone for a name the store never accepts is dead code."""
    _current, ever = _vocabulary(tmp_path)
    extra = sorted(set(tone.VERDICT_TONE) - ever)
    assert not extra, f"tone.py declares tones for names the store does not accept: {extra}"


def test_the_analysers_emit_only_current_verdicts_and_all_of_them_are_toned(tmp_path):
    current, _ever = _vocabulary(tmp_path)
    emitted = vocabulary.emitted_verdicts()
    assert emitted, "the analyser scan found no verdict literals"
    assert emitted <= current, f"an analyser emits a retired or unknown verdict: {emitted - current}"
    assert emitted <= set(tone.VERDICT_TONE)


@pytest.mark.parametrize("verdict", sorted(tone.VERDICT_TONE))
def test_each_verdicts_tone_is_one_of_the_declared_tones(verdict):
    assert tone.tone_of(verdict) in tone.TONES


# --------------------------------------------------------------------------- AC1

def test_conclusion_and_certainty_are_toned_apart():
    """The crux of the ticket, stated as the mapping rather than as a rendering."""
    assert tone.tone_of("unplaced") == tone.SOFT
    assert tone.tone_of("gap") == tone.ALARM
    assert tone.tone_of("duplicate") == tone.ALARM
    assert tone.tone_of("review") == tone.ALARM
    assert tone.tone_of("overbuilt") == tone.ALARM      # retired, still an asserted problem
    # Nothing is wrong: these must never wear the alarm colour.
    assert tone.tone_of("distinct") == tone.SETTLED
    assert tone.tone_of("necessary") == tone.SETTLED
    assert tone.tone_of("optimal") == tone.SETTLED


def test_an_undeclared_verdict_is_an_error_not_a_default():
    """AC1: the mapping may not catch whatever is left over and dress it as settled."""
    with pytest.raises(KeyError) as refused:
        tone.tone_of("made_up_verdict")
    assert "made_up_verdict" in str(refused.value)


def test_the_class_suffix_follows_the_tone():
    assert tone.class_suffix(tone.SETTLED) == ""
    assert tone.class_suffix(tone.SOFT).split() == ["soft"]
    assert tone.class_suffix(tone.ALARM).split() == ["hot"]
    with pytest.raises(KeyError):
        tone.class_suffix("made_up_tone")


# --------------------------------------------------------------------------- AC3

class _VerdictHeadlines(HTMLParser):
    """The ``<strong>`` elements that carry the case's verdict, with class and text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[tuple[tuple[str, ...], str]] = []
        self._open: tuple[str, ...] | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "strong":
            return
        tokens = next(((value or "").split() for name, value in attrs if name == "class"), [])
        if "verdict" in tokens:
            self._open, self._text = tuple(tokens), []

    def handle_data(self, data):
        if self._open is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "strong" and self._open is not None:
            self.found.append((self._open, htmllib.unescape("".join(self._text)).strip()))
            self._open, self._text = None, []


def _headline(markup: str) -> tuple[set[str], str]:
    parser = _VerdictHeadlines()
    parser.feed(markup)
    parser.close()
    assert len(parser.found) == 1, f"expected one verdict headline, got {parser.found}"
    classes, visible = parser.found[0]
    return set(classes), visible


def test_cannot_assess_does_not_share_a_class_or_colour_with_a_settled_verdict(tmp_path):
    """AC3, structurally: the class attribute distinguishes them, so no legend is needed."""
    # A claim whose needed source is blocked: the page says "Cannot assess".
    blocked_conn, blocked_case = registry_fixture._store(tmp_path, "blocked",
                                                         registry_fixture.BLOCKED)
    try:
        blocked = app.case_page(blocked_conn, blocked_case).decode("utf-8")
    finally:
        blocked_conn.close()

    # A settled claim: checked, and nothing is wrong with it.
    settled_conn = db.connect(tmp_path / "settled" / "settled.db")
    try:
        rows._seed_case(settled_conn, case_id="case-settled", verdict="distinct")
        settled = app.case_page(settled_conn, "case-settled").decode("utf-8")
    finally:
        settled_conn.close()

    blocked_classes, blocked_text = _headline(blocked)
    settled_classes, settled_text = _headline(settled)

    assert "Cannot assess" in blocked_text, blocked_text
    assert blocked_classes != settled_classes, (
        f"'Cannot assess' (class {sorted(blocked_classes)}) shares a class with a settled verdict "
        f"({sorted(settled_classes)}, {settled_text!r})")
    assert "soft" in blocked_classes, "the inconclusive verdict does not wear the soft treatment"
    assert "hot" not in blocked_classes, "'Cannot assess' still wears the alarm colour"
    assert not ({"hot", "soft"} & settled_classes), (
        f"a settled verdict wears warning tone {sorted(settled_classes)}")
