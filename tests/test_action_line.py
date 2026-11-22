"""TESTOPS-27: the action line keeps a second instruction and drops only a restatement.

The rule under test is ``app.second_half_is_instruction``, written where it is applied
(``testops/web/app.py``) so it can be argued with on evidence. Every case below is a shape of that
evidence:

  * a tail that gives the reason for the clause before it - dropped, and the test names both
    strings and shows why the tail cannot be acted on alone (AC2)
  * a tail that gives a second order - kept, and the action reads as two sentences, not a run-on
    (AC1, AC3)
  * the same two shapes as the page renders them (AC3)

AC4, the corpus floor, lives with the real run it measures: ``test_case_scan.py``.
"""
from __future__ import annotations

import re

import level_fixtures as fixtures
import pytest
from testops.web import app

STEP = "the panel is served"


# --------------------------------------------------------------------------- the rule itself

INSTRUCTION_TAILS = [
    "keep one",                                            # the duplicate claims' own tail
    "call the HTTP client first, then delete the browser step",
    "delete it if the page does not need it",
    "then re-run",                                         # "then" does not make it a reason
    "move the step into a test that drives a browser",
]
RESTATEMENT_TAILS = [
    "this level is the cheapest one that establishes it",   # the distinct claims' own tail
    "at this level nothing establishes what it asserts",    # the gap claims' own tail
    "a judgement with no comparison in it cannot be checked at any level",
    "the response decides everything the browser is being used for",
]


@pytest.mark.parametrize("tail", INSTRUCTION_TAILS)
def test_a_tail_that_opens_with_an_instruction_is_kept(tail):
    """AC1: a second order stays, so a reader is never given half an instruction."""
    assert app.second_half_is_instruction(tail) is True


@pytest.mark.parametrize("tail", RESTATEMENT_TAILS)
def test_a_tail_whose_only_subject_is_the_clause_before_it_is_a_restatement(tail):
    """AC1: a reason continues the head's sentence; it names no one to act and no new order."""
    assert app.second_half_is_instruction(tail) is False


def test_the_rule_fails_open_on_a_word_it_does_not_know():
    """A tail the rule cannot read is kept: a lost instruction is invisible, a stray reason is not."""
    tail = "whoever wrote that step was right"
    assert "whoever" not in app.CONTINUATION_OPENERS
    assert app.second_half_is_instruction(tail) is True


# --------------------------------------------------------------------------- AC2: the dropped tail

def _claims(text=None, bindings=None, path=None):
    if text is None:
        return fixtures.analyse_fact_sheet()
    return fixtures.analyse_text(text, bindings, path=path or fixtures.FEATURE_PATH)


def _stored(claim) -> str:
    return claim.detail["proposed_action"]


def _visible(claim) -> str:
    return app.action_line({"proposed_action": _stored(claim),
                            "provenance": {"assertion_text": claim.detail["assertion_text"]}},
                           claim.detail["assertion_text"])


def _proved_head(claim, head: str) -> str:
    """The head the page must show: the stored head, with the step referred to as "this step"."""
    step = claim.detail["assertion_text"]
    return head.replace(f'the step "{step}"', "this step").rstrip(".") + "."


def _split(stored: str) -> tuple[str, str]:
    head, _, tail = stored.partition("; ")
    assert tail, f"this action has no tail to prove anything about: {stored!r}"
    return head.strip(), tail.strip()


def test_a_dropped_tail_is_proved_a_restatement_by_showing_it_cannot_stand_alone():
    """AC2: the test names the head and the tail and shows why the tail is not an instruction.

    Three real analyser tails, one per verdict that writes one. Each is dropped, and the proof is
    the overlap: the tail opens with a word that points back at the head - "this level", "at this
    level", "the response" - and it carries no instruction verb anywhere, so the only order in the
    string is the head's. If an analyser ever writes a second order after a semicolon, the first
    test in this file is what keeps it, and the corpus floor in ``test_case_scan.py`` is what says
    no page lost characters it kept.
    """
    verdicts = {}
    for claim in _claims():
        verdicts.setdefault(claim.verdict, claim)

    assert set(verdicts) >= {"distinct", "gap"}, sorted(verdicts)
    checked = 0
    for verdict in ("distinct", "gap"):
        claim = verdicts[verdict]
        stored, visible = _stored(claim), _visible(claim)
        head, tail = _split(stored)

        match = re.match(r"[A-Za-z]+", tail)
        assert match is not None, f"the {verdict} tail opens with no word at all: {tail!r}"
        opener = match.group(0).lower()
        wants = [word for word in re.findall(r"[A-Za-z][A-Za-z'-]*", tail.lower())
                 if word in app.INSTRUCTION_VERBS]

        assert opener in app.CONTINUATION_OPENERS, (
            f"the {verdict} tail is not proved a restatement: {head!r} / {tail!r} - it opens with "
            f"{opener!r}, which is not a word that points back at the head")
        assert not wants, (
            f"the {verdict} tail carries an instruction ({wants}) that dropping would lose: "
            f"{head!r} / {tail!r}")
        assert tail not in visible, (
            f"the {verdict} tail was proved a restatement and is still on the page: {visible!r}")
        assert visible == _proved_head(claim, head), (
            f"the {verdict} page kept something other than the proved head: {visible!r} from "
            f"{stored!r}")
        checked += 1
    assert checked == 2


def test_an_unplaced_claim_that_judges_without_a_comparison_drops_its_reason_too():
    """The third analyser tail in the store, from the run the ticket's corpus came from."""
    text = ("Feature: counts\n"
            "  Scenario: the count is reported\n"
            "    Then that count is correct for the store it was run against\n")
    claims = fixtures.analyse_text(text, fixtures.api_bindings())
    assert len(claims) == 1 and claims[0].verdict == "unplaced", claims[0].verdict
    stored = _stored(claims[0])
    head, tail = _split(stored)
    assert tail == "a judgement with no comparison in it cannot be checked at any level."
    assert app.second_half_is_instruction(tail) is False
    assert _visible(claims[0]) == _proved_head(claims[0], head)


# --------------------------------------------------------------------------- AC1, AC3: kept tails

DUPLICATE = ("Raise this with the team: this copy calls the HTTP client to establish what "
             "ReqOverflow.Specs.Controller/Features/Home.feature:7 settles in-process; keep one.")


def test_a_second_order_after_the_semicolon_reaches_the_reader():
    """AC1 on the shape the store already holds: the duplicate claims' own action."""
    claim = {"proposed_action": DUPLICATE, "provenance": {}}
    visible = app.action_line(claim, None)
    assert visible.endswith(". Keep one."), visible
    # The first half is unchanged by the rule: the reader reads the same instruction, plus one.
    assert visible.startswith("Raise this with the team: this copy calls the HTTP client")


def test_a_kept_tail_renders_as_two_sentences_and_never_as_a_run_on():
    """AC3, kept shape: two clauses reach the page as two sentences with one full stop each."""
    claim = {"proposed_action": 'Rewrite the step "the panel is served" to call the HTTP '
                                'client; call the HTTP client first, before the browser.',
             "provenance": {"assertion_text": STEP}}
    visible = app.action_line(claim, STEP)
    assert visible == ("Rewrite this step to call the HTTP client. Call the HTTP client first, "
                       "before the browser."), visible
    assert "; " not in visible
    assert visible.count(". ") == 1 and visible.endswith(".")


def test_a_dropped_tail_renders_as_one_sentence_and_never_as_a_run_on():
    """AC3, dropped shape: the page says one thing, in one sentence, with no dangling semicolon."""
    claim = {"proposed_action": 'No change: keep the step "the page is served with stable fact '
                                'anchors" where it is; this level is the cheapest one that '
                                'establishes it.',
             "provenance": {"assertion_text": "the page is served with stable fact anchors"}}
    visible = app.action_line(claim, "the page is served with stable fact anchors")
    assert visible == "No change: keep this step where it is.", visible
    assert "; " not in visible and visible.endswith(".")


def test_the_page_renders_the_kept_second_order():
    """AC3 through the block the reader meets, not only through the helper."""
    claim = {"proposed_action": DUPLICATE, "verdict": "review", "assessment": {},
             "provenance": {}}
    block = " ".join(app.argument_block(claim))
    assert "Keep one." in block
    assert "&quot;keep one&quot;" not in block


def test_an_action_with_no_semicolon_is_untouched():
    action = 'Call the HTTP client for the step "the panel is served" instead of the browser.'
    assert app.action_line({"proposed_action": action, "provenance": {}}, None) == action
