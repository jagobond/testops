"""AC5: every claim has a proposed action, the action differs by verdict, and it names the step.

"Review this test" is not an action. The reviewer of a case has to be able to read one sentence and
know which step to move or rewrite.
"""
from __future__ import annotations

import level_fixtures as fixtures


def _review_claim():
    claims = fixtures.analyse_text(fixtures.BROWSER_FEATURE_TEXT, fixtures.browser_bindings(),
                                   path=fixtures.BROWSER_FEATURE_PATH)
    assert len(claims) == 1
    return claims[0]


def test_every_claim_has_a_non_empty_action():
    claims = (fixtures.analyse_fact_sheet()
              + fixtures.analyse_text(fixtures.BROWSER_FEATURE_TEXT, fixtures.browser_bindings(),
                                      path=fixtures.BROWSER_FEATURE_PATH))
    assert claims
    for claim in claims:
        action = claim.detail["proposed_action"]
        assert isinstance(action, str) and action.strip(), f"{claim.verdict} claim has no action"


def test_the_action_names_the_step_to_change():
    for claim in fixtures.analyse_fact_sheet():
        action = claim.detail["proposed_action"]
        step = claim.detail["assertion_text"]
        # The statement lowercases the first letter; the action quotes the step's own words.
        assert step.lstrip()[:1].lower() + step.lstrip()[1:] in action, action


def test_a_gap_and_a_review_propose_different_actions():
    gap = next(claim for claim in fixtures.analyse_fact_sheet() if claim.verdict == "gap")
    review = _review_claim()
    assert review.verdict == "review"

    assert gap.detail["proposed_action"] != review.detail["proposed_action"]
    assert gap.detail["proposed_action"].startswith("Move the step")
    assert review.detail["proposed_action"].startswith("Rewrite the step")
    assert "browser" in gap.detail["proposed_action"]
    assert "HTTP client" in review.detail["proposed_action"]


def test_a_distinct_claim_proposes_no_change_but_still_names_the_step():
    distinct = next(claim for claim in fixtures.analyse_fact_sheet() if claim.verdict == "distinct")
    action = distinct.detail["proposed_action"]
    assert action.startswith("No change")
    assert "is the cheapest one" in action
    assert distinct.detail["assertion_text"].lstrip()[:1].lower() + \
        distinct.detail["assertion_text"].lstrip()[1:] in action


def test_an_unplaced_claim_proposes_something_to_do_about_being_unplaced():
    text = """\
Feature: unclear
  Scenario: something happens
    Given a fact sheet exists
    Then the thing is handled
"""
    claims = fixtures.analyse_text(text, fixtures.api_bindings())
    assert len(claims) == 1
    claim = claims[0]
    assert claim.verdict == "unplaced"
    assert claim.detail["interaction_code"] == "U"
    assert claim.detail["proposed_action"].startswith("Rewrite the step")
    assert "the thing is handled" in claim.detail["proposed_action"]
