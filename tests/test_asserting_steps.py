"""AC2: `Given` and `When` steps make no claim; a `But`/`And` following a `Then` does."""
from __future__ import annotations

import level_fixtures as fixtures

CONTEXT_THEN_ONE_ASSERTION = """\
Feature: signing in
  Scenario: the panel loads for a signed-in reader
    Given a fact sheet exists
    And the reader is signed in
    When the reader opens the fact sheet
    And the sheet is loaded
    Then the response status is 200
"""


def test_given_and_when_make_no_claim():
    claims = fixtures.analyse_text(fixtures.CONTEXT_ONLY_TEXT, fixtures.api_bindings())
    assert claims == [], [claim.detail["assertion_text"] for claim in claims]


def test_and_before_a_then_is_still_context():
    claims = fixtures.analyse_text(CONTEXT_THEN_ONE_ASSERTION, fixtures.api_bindings())
    assert [claim.detail["assertion_text"] for claim in claims] == ["the response status is 200"]


def test_and_after_a_then_makes_a_claim():
    claims = fixtures.analyse_fact_sheet()
    texts = [claim.detail["assertion_text"] for claim in claims]
    assert "the page is served with stable fact anchors" in texts   # an And


def test_but_after_a_then_makes_a_claim():
    claims = fixtures.analyse_fact_sheet()
    texts = [claim.detail["assertion_text"] for claim in claims]
    assert "the response status is not an error" in texts           # a But


def test_the_phase_is_read_from_the_keyword_not_the_position():
    """A `Then` after a `When` re-opens asserting; an `And` after that inherits it."""
    text = """\
Feature: phase
  Scenario: two assertions in one scenario
    When the reader opens the fact sheet
    Then the response status is 200
    And the page is served with stable fact anchors
"""
    claims = fixtures.analyse_text(text, fixtures.api_bindings())
    assert [claim.detail["assertion_text"] for claim in claims] == [
        "the response status is 200",
        "the page is served with stable fact anchors",
    ]
    assert [claim.detail["assertion_line"] for claim in claims] == [4, 5]
