"""TESTOPS-27: the action line keeps a second instruction and drops only a restatement.

The rule under test is ``app.second_half_is_instruction``, written where it is applied
(``testops/web/app.py``) so it can be argued with on evidence. Every case below is a shape of that
evidence:

  * a tail that gives the reason for the clause before it - dropped, and the test names both
    strings and shows why the tail cannot be acted on alone (AC2, AC8)
  * a tail that gives a second order - kept, and the action reads as two sentences, not a run-on
    (AC1, AC3)
  * the eight orders the reviewer smuggled past a bare-stem rule, two of which were lost to
    morphology: ``should be deleted`` and ``worth keeping`` (AC7)
  * every inflection of every instruction verb, and the irregulars the vocabulary uses (AC7)
  * the same two shapes as the page renders them (AC3)

AC4, the corpus floor, lives with the real run it measures: ``test_case_scan.py``. So does AC9,
the before/after drop count over that run.
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


# --------------------------------------------------------------- AC7: the reviewer's eight probes

PROBES = [
    "this should be split into two steps and the second deleted",
    "move it and rename it",
    "one copy to keep",
    "keep it if the page does not need it",
    "you should delete the second one",
    "instead, delete the duplicate",
    "the second copy should be deleted",     # lost to a bare-stem rule: passive voice
    "it is worth keeping one copy",          # lost to a bare-stem rule: inflected verb
]


@pytest.mark.parametrize("tail", PROBES)
def test_every_probe_the_reviewer_smuggled_reaches_the_reader(tail):
    """AC7: all eight orders the reviewer put after a semicolon are on the page, none dropped.

    Two of these were lost before the morphology fix - the passive "should be deleted" and the
    inflected "keeping". Both are orders, and both are kept now. The assertion is on the rendered
    action, not only on the rule, because a kept tail the page still cuts is the same loss.
    """
    claim = {"proposed_action": f"Raise this with the team: this copy repeats an assertion; "
                                f"{tail}.", "provenance": {"assertion_text": STEP}}
    visible = app.action_line(claim, STEP)
    assert app.second_half_is_instruction(tail) is True, tail
    assert tail[:1].upper() + tail[1:] + "." in visible, (tail, visible)
    assert "; " not in visible, visible
    assert visible.endswith(".") and visible.count(". ") == 1, visible


@pytest.mark.parametrize("form,stem", [
    ("deletes", "delete"), ("deleted", "delete"), ("deleting", "delete"),
    ("removes", "remove"), ("removed", "remove"), ("removing", "remove"),
    ("merges", "merge"), ("merged", "merge"),
    ("renames", "rename"), ("renamed", "rename"), ("renaming", "rename"),
    ("checks", "check"), ("checked", "check"), ("checking", "check"),
    ("changes", "change"), ("changed", "change"), ("changing", "change"),
    ("drops", "drop"), ("dropped", "drop"), ("dropping", "drop"),
    ("stops", "stop"), ("stopped", "stop"), ("stopping", "stop"),
    ("swaps", "swap"), ("swapped", "swap"), ("swapping", "swap"),
    ("splits", "split"), ("split", "split"), ("splitting", "split"),
    ("kept", "keep"), ("keeps", "keep"),
    ("made", "make"), ("ran", "run"), ("bound", "bind"), ("written", "write"),
])
def test_an_instruction_verb_is_recognised_in_every_inflection(form, stem):
    """AC7: -s, -es, -ed, -d, -ing, a doubled consonant and the vocabulary's irregulars."""
    assert app.INSTRUCTION_FORMS.get(form) == stem


@pytest.mark.parametrize("tail", [
    "the second copy should be deleted",
    "the second copy needs deleting",
    "the second copy must be removed",
    "it is worth keeping one copy",
    "the copies get merged",
])
def test_a_passive_or_modal_order_is_an_instruction(tail):
    """AC7: an obligation carries the order, so a passive is not read as a description."""
    assert app.order_cues(tail), tail
    assert app.instruction_hits(tail), tail
    assert app.second_half_is_instruction(tail) is True


def test_a_passive_with_no_obligation_describes_and_asks_nothing():
    """The distinction the rule turns on: "is being used" states a fact, "should be used" orders."""
    descriptive = "the response decides everything the browser is being used for."
    ordering = "the response should be used instead of the browser."
    assert app.descriptive_participles(descriptive) == ["used"]
    assert app.instruction_hits(descriptive) == []
    assert app.second_half_is_instruction(descriptive) is False
    assert app.descriptive_participles(ordering) == []
    assert app.instruction_hits(ordering) == ["use"]
    assert app.second_half_is_instruction(ordering) is True


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
    """AC2 and AC8: the test names the head and the tail and proves each condition of the drop.

    Three real analyser tails, one per verdict that writes one. Each is dropped, and the proof is
    AC8's three conditions, asserted here on the strings rather than trusted from a comment: the
    tail opens with a word whose subject is the head, it holds no instruction verb in any
    inflection, and it holds no modal or passive order. Where the vocabulary does appear - "being
    used", "cannot be checked" - the test names it as a descriptive participle, so the drop is
    shown to be a judgement about that word and not an oversight. If an analyser ever writes a
    second order after a semicolon, the probe test above is what keeps it, and the corpus floor in
    ``test_case_scan.py`` is what says no page lost characters it kept.
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

        # AC8, condition 1: the tail opens with a word whose subject is the head clause.
        assert opener in app.CONTINUATION_OPENERS, (
            f"the {verdict} tail is not proved a restatement: {head!r} / {tail!r} - it opens with "
            f"{opener!r}, which is not a word that points back at the head")
        # AC8, condition 2: no instruction verb in any inflection.
        assert app.instruction_hits(tail) == [], (
            f"the {verdict} tail carries an instruction ({app.instruction_hits(tail)}) that "
            f"dropping would lose: {head!r} / {tail!r}")
        # AC8, condition 3: no modal or passive order. A participle here is descriptive, and the
        # test names it so a future change to the passive rule fails here rather than in silence.
        assert app.order_cues(tail) == [], (
            f"the {verdict} tail carries a modal ({app.order_cues(tail)}): {head!r} / {tail!r}")
        for participle in app.descriptive_participles(tail):
            assert participle in app.INSTRUCTION_FORMS and participle not in app.INSTRUCTION_VERBS
            assert participle in tail.lower()

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
