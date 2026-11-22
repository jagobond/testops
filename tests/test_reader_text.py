"""AC4: no reader-facing text contains the debugging shorthand `I1`..`I4` or `KP`.

The statement is what a reader makes a decision from; the interaction label is the phrase the case
page shows; the proposed action is what the reviewer acts on. None of the three may carry a code -
and a step whose own text contains one must not leak it into them either.
"""
from __future__ import annotations

import re

import level_fixtures as fixtures

CODE = re.compile(r"\b(I[1-4]|KP)\b")

# The step text deliberately contains the shorthand a developer might have pasted in.
CODE_IN_THE_STEP = """\
Feature: codes in a step
  Scenario: the panel reports its own code
    Given the fact sheet endpoint returns a sheet
    Then the I4 claim is accessible in the browser
    And the KP marker is in the response body
"""


def _reader_fields(claims):
    for claim in claims:
        yield claim.statement, "statement"
        yield claim.detail["interaction_label"], "interaction_label"
        yield claim.detail["proposed_action"], "proposed_action"


def test_no_reader_facing_text_carries_a_code():
    claims = fixtures.analyse_fact_sheet()
    for text, field in _reader_fields(claims):
        assert text, f"{field} is empty"
        assert not CODE.search(text), f"{field} contains shorthand: {text!r}"


def test_a_code_in_the_step_text_is_not_copied_into_the_statement():
    claims = fixtures.analyse_text(CODE_IN_THE_STEP, fixtures.api_bindings())
    assert len(claims) == 2
    for text, field in _reader_fields(claims):
        assert not CODE.search(text), f"{field} leaked a code from the step: {text!r}"

    gap = next(claim for claim in claims if claim.verdict == "gap")
    assert "The assertion is about what only a browser works out" in gap.statement
    assert "the claim is accessible in the browser" in gap.statement
    # The verbatim step still holds the code - it is evidence, not prose.
    assert gap.detail["assertion_text"] == "the I4 claim is accessible in the browser"
    assert gap.detail["interaction_code"] == "I4"


def test_the_code_lives_in_interaction_code():
    claims = fixtures.analyse_fact_sheet()
    assert [claim.detail["interaction_code"] for claim in claims] == ["I4", "KP", "I2"]
    assert all(claim.detail["claim"] == claim.detail["interaction_code"] for claim in claims)
