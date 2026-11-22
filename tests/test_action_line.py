"""TESTOPS-28: the action line is the whole stored action, rendered as sentences.

TESTOPS-27 tried to decide, from the words after a semicolon, whether the tail was a second order
or a restatement. Two review passes found three orders it silently lost - "the duplicate is
deletable", "the second one can go", "the copy would be deleted by whoever owns it" - each one a
different grammatical shape. The decision this module pins is that the renderer no longer decides:
``action_line`` returns the whole stored action, split at its semicolons into sentences, and cuts
nothing (AC1, AC5).

What that buys is a property a word list cannot give: every word the analyser stored reaches the
reader. The reviewer's probes are the corpus of that property below, and the real run's corpus is
in ``test_case_scan.py``.

There is no test of a classification here, because there is no classification to test.
"""
from __future__ import annotations

import re

import level_fixtures as fixtures
import pytest
from testops.web import app

STEP = "the panel is served"

# The reviewer's 15 probes, read off the two review passes
# (factory/reports/2026-11-22/TESTOPS-27-review.md and TESTOPS-27-review-2.md). The first eight
# came from the first pass; the rest are the shapes the second pass attacked, three of which the
# word list dropped. They are the corpus of the property below.
REVIEWER_PROBES = [
    # first pass
    "this should be split into two steps and the second deleted",
    "move it and rename it",
    "one copy to keep",
    "keep it if the page does not need it",
    "you should delete the second one",
    "instead, delete the duplicate",
    "the second copy should be deleted",
    "it is worth keeping one copy",
    # second pass
    "the duplicate is deletable",                                # dropped by the word list
    "the second one can go",                                     # dropped by the word list
    "the copy would be deleted by whoever owns it",              # dropped by the word list
    "removal of the copy is advisable",
    "ought to be removed",
    "would be better gone",
    "it must not be kept",
]

# Shapes the same two passes recorded beyond the mandated list. They cost nothing to keep in the
# corpus and they are the sort of tail an analyser will write next.
EXTRA_PROBES = [
    "there is no need for this copy",
    "both copies are unnecessary",
    "one of the copies should go",
    "getting rid of the duplicate is advisable",
    "it requires deleting",
    "is supposed to be removed",
    "had better be merged",
    "is bound to merge",
]

# Function words carry no instruction, so the property is stated on content words: the nouns,
# verbs and modifiers the analyser chose must all survive. "should", "must", "go" and "deletable"
# are deliberately content here - they are exactly what a word list mislaid.
STOPWORDS = frozenset("""
    a an the this that these those it its they them their there here and or but nor so if then
    than as of to in on at for with by from into over under about is are was were be been being
    am do does did has have had
""".split())

WORD = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)*")


def _words(text: str) -> list[str]:
    return WORD.findall(text.lower())


def _content(text: str) -> list[str]:
    return [word for word in _words(text) if word not in STOPWORDS]


def _subsequence(needle: list[str], haystack: list[str]) -> bool:
    """Whether ``needle`` appears in ``haystack`` in order, with words only added between."""
    it = iter(haystack)
    return all(word in it for word in needle)


def _stored(probe: str,
            head: str = "Raise this with the team: this copy repeats an assertion") -> str:
    return f"{head}; {probe}."


def _claim(probe: str) -> dict:
    return {"proposed_action": _stored(probe), "provenance": {"assertion_text": STEP}}


# ------------------------------------------------------------------- AC1: no word is removed


@pytest.mark.parametrize("probe", REVIEWER_PROBES + EXTRA_PROBES)
def test_every_content_word_of_the_stored_action_reaches_the_page(probe):
    """AC1: the property, over the reviewer's 15 probes and the shapes both passes recorded.

    The stored action is the input; the rendered line is the output. Every content word of the
    input appears in the output, in the order it was written, so no clause - and no order inside a
    clause - can be lost without this failing.
    """
    stored = _stored(probe)
    visible = app.action_line(_claim(probe), STEP)
    missing = [word for word in _content(stored) if word not in _words(visible)]
    assert missing == [], (missing, visible)
    assert _subsequence(_content(stored), _words(visible)), visible
    assert ";" not in visible, visible
    assert visible.endswith("."), visible


@pytest.mark.parametrize("probe", [
    "the duplicate is deletable",
    "the second one can go",
    "the copy would be deleted by whoever owns it",
])
def test_the_three_orders_the_word_list_dropped_are_on_the_page(probe):
    """AC1 on the exact leaks this ticket exists for: named, rendered, whole."""
    visible = app.action_line(_claim(probe), STEP)
    assert visible.endswith(probe[:1].upper() + probe[1:] + "."), visible


# ------------------------------------------------------------------- AC5: two sentences, not a run-on


def test_a_stored_action_with_a_tail_renders_as_two_sentences():
    """AC5: the semicolon becomes a full stop and a capital, so the action never runs on."""
    visible = app.action_line(_claim("keep one"), STEP)
    assert visible == ("Raise this with the team: this copy repeats an assertion. Keep one."), visible
    assert visible.count(". ") == 1 and visible.endswith(".")
    assert "; " not in visible


def test_an_action_with_no_semicolon_is_untouched():
    action = 'Call the HTTP client for the step "the panel is served" instead of the browser.'
    assert app.action_line({"proposed_action": action, "provenance": {}}, None) == action


def test_every_semicolon_is_a_sentence_boundary_and_nothing_is_merged():
    """A three-clause action keeps all three clauses, one sentence each."""
    claim = {"proposed_action": "Split this step; move the browser call into its own step; "
                                "delete the duplicate.",
             "provenance": {}}
    visible = app.action_line(claim, None)
    assert visible == ("Split this step. Move the browser call into its own step. "
                       "Delete the duplicate."), visible


def test_an_action_with_nothing_stored_still_says_something():
    assert app.action_line({"proposed_action": "", "provenance": {}}, None) == (
        "No proposed action was recorded for this claim.")


# ---------------------------------------------------- the step reference is the only shortening


def test_the_step_is_referred_to_rather_than_quoted_twice_and_nothing_else_is_shortened():
    """The one shortening the page may make is the step's own words, quoted above the action."""
    claim = {"proposed_action": 'Rewrite the step "the panel is served" to call the HTTP client; '
                                'keep the rest of the scenario as it is.',
             "provenance": {"assertion_text": STEP}}
    visible = app.action_line(claim, STEP)
    assert visible == ("Rewrite this step to call the HTTP client. Keep the rest of the scenario "
                       "as it is."), visible
    assert "the panel is served" not in visible


# ------------------------------------------------------------------- the real analyser's shapes
#
# These are stored actions, not current analyser output. The store keeps every run it was given, so
# rows written by level_fitness 0.10.1 and duplication 2.0.0 still have to render - whole - on a page
# built after TESTOPS-29 rewrote those strings. That is why the fixtures below are the old strings
# verbatim: the renderer's contract is with what is stored, never with what today's analyser writes.

DUPLICATE = ("Raise this with the team: this copy calls the HTTP client to establish what "
             "ReqOverflow.Specs.Controller/Features/Home.feature:7 settles in-process; keep one.")


def test_the_duplicate_claims_own_action_reaches_the_reader_whole():
    visible = app.action_line({"proposed_action": DUPLICATE, "provenance": {}}, None)
    assert visible == ("Raise this with the team: this copy calls the HTTP client to establish what "
                       "ReqOverflow.Specs.Controller/Features/Home.feature:7 settles in-process. "
                       "Keep one."), visible


def _claims(text=None):
    if text is None:
        return fixtures.analyse_fact_sheet()
    return fixtures.analyse_text(text, fixtures.api_bindings(), path=fixtures.FEATURE_PATH)


def _visible(claim) -> str:
    return app.action_line({"proposed_action": claim.detail["proposed_action"],
                            "provenance": {"assertion_text": claim.detail["assertion_text"]}},
                           claim.detail["assertion_text"])


def _referred(stored: str, step: str) -> str:
    """The stored action with its quoted copy of the step referred to as "this step".

    That reference is the only shortening the page makes, because the block has already quoted the
    step directly above the action. Everything else must survive, which is what the property
    asserts.
    """
    if not step:
        return stored
    for form in (f'the step "{step}"', f'step "{step}"', f'"{step}"'):
        if form in stored:
            return stored.replace(form, "this step", 1)
    return stored


def test_a_real_analyser_tail_is_on_the_page_now():
    """AC3 on the analyser's own strings: what today's analyser writes, the page renders whole.

    The distinct verdict is the one action that still carries the level fact (TESTOPS-29 removed the
    clauses that restated the statement). It now states that fact inside the instruction rather than
    as a second sentence, and the page must give it back word for word: the fact appears nowhere else
    on the page, so a renderer that dropped or reshaped it would take it off the page entirely.
    """
    claim = next(claim for claim in _claims() if claim.verdict == "distinct")
    stored, visible = claim.detail["proposed_action"], _visible(claim)
    assert stored.endswith("at the cheapest level that establishes it."), stored
    expected = _referred(stored, claim.detail["assertion_text"])
    expected = " ".join(part.strip()[:1].upper() + part.strip()[1:]
                        for part in re.split(r";\s*", expected) if part.strip())
    assert visible == expected, (stored, visible)
    missing = [word for word in _content(expected) if word not in _words(visible)]
    assert missing == [], (missing, stored, visible)


def test_a_stored_action_whose_tail_is_a_reason_still_renders_whole():
    """A row the store already holds keeps its reason clause, whatever today's analyser writes.

    This is the shape level_fitness 0.10.1 wrote for an unplaced meta claim. TESTOPS-29 stopped it
    being written; TESTOPS-28's renderer is what must keep it readable for as long as the row is in
    the store.
    """
    stored = ('Rewrite the step "that count is correct" to say what it is compared with, then '
              're-run; a judgement with no comparison in it cannot be checked at any level.')
    visible = app.action_line({"proposed_action": stored, "provenance": {}}, None)
    assert visible.endswith(
        "A judgement with no comparison in it cannot be checked at any level."), visible


def test_the_page_renders_the_wordy_action():
    """AC3 through the block the reader meets, not only through the helper."""
    claim = {"proposed_action": DUPLICATE, "verdict": "review", "assessment": {},
             "provenance": {}}
    block = " ".join(app.argument_block(claim))
    assert "Keep one." in block
    assert "&quot;keep one&quot;" not in block
