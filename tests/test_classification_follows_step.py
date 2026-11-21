"""AC3: classification follows the asserting step's words, not the scenario title.

Both directions are tested with a title that says the opposite of its step, so an analyser that
still reads the title cannot pass either one by coincidence.
"""
from __future__ import annotations

import level_fixtures as fixtures
from testops.analysers import level_fitness as lf

# Title claims markup (fact anchors); the step asserts an accessibility property.
TITLE_SAYS_ANCHORS = """\
Feature: anchors
  Scenario: the page is served with stable fact anchors
    Given the fact sheet endpoint returns a sheet
    Then each citation sits inside an element an assistive technology can name
"""

# Title claims accessibility; the step asserts markup.
TITLE_SAYS_ACCESSIBLE = """\
Feature: accessible
  Scenario: every citation has an accessible name
    Given the fact sheet endpoint returns a sheet
    Then the response body carries stable fact anchors
"""

ANCHOR_TITLE = "the page is served with stable fact anchors"
ACCESSIBLE_TITLE = "every citation has an accessible name"


def test_a_title_about_anchors_does_not_hide_an_accessibility_step():
    claims = fixtures.analyse_text(TITLE_SAYS_ANCHORS, fixtures.api_bindings())
    assert len(claims) == 1
    claim = claims[0]

    # The title, read on its own, would have said markup - so this really is the step winning.
    assert lf.classify_step(ANCHOR_TITLE)[0] == "KP"
    assert claim.detail["interaction_code"] == "I4"
    assert claim.verdict == "gap", "a browser property asserted over the API is not established"


def test_a_title_about_accessibility_does_not_invent_a_browser_claim():
    claims = fixtures.analyse_text(TITLE_SAYS_ACCESSIBLE, fixtures.api_bindings())
    assert len(claims) == 1
    claim = claims[0]

    assert lf.classify_step(ACCESSIBLE_TITLE)[0] == "I4"
    assert claim.detail["interaction_code"] == "KP"
    assert claim.verdict == "distinct", "the response body settles this; no browser is missing"


def test_the_title_is_passed_as_context_and_never_changes_the_answer():
    """Same step, two contradictory titles, one answer - twice."""
    step = "the response body carries stable fact anchors"
    assert lf.classify_step(step, context="the page is served with stable fact anchors")[0] == "KP"
    assert lf.classify_step(step, context="every citation has an accessible name")[0] == "KP"
    assert lf.classify_claims(step, context="every citation has an accessible name") == \
        lf.classify_claims(step)
