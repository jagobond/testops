"""AC1: a scenario with three asserting steps produces three claims, each carrying that step's
verbatim text and its line.

The old analyser emitted one claim per scenario, classified from `name + every step concatenated`.
That is why two independent assertions could share one decision button: there was one row for both.
"""
from __future__ import annotations

import level_fixtures as fixtures


def test_three_asserting_steps_make_three_claims():
    claims = fixtures.analyse_fact_sheet()
    assert len(claims) == 3, "one claim per asserting step"


def test_each_claim_carries_its_own_step_text_verbatim():
    claims = fixtures.analyse_fact_sheet()
    assert [claim.detail["assertion_text"] for claim in claims] == fixtures.ASSERTING_TEXTS
    # Verbatim means verbatim: a reader can paste it back into the feature file and find the step.
    assert all(claim.detail["assertion_text"] in fixtures.FEATURE_TEXT for claim in claims)


def test_each_claim_carries_its_own_step_line():
    claims = fixtures.analyse_fact_sheet()
    assert [claim.detail["assertion_line"] for claim in claims] == fixtures.ASSERTING_LINES
    # The clickable evidence points at the same line as the provenance block, not at the scenario.
    assert [claim.evidence[0].line for claim in claims] == fixtures.ASSERTING_LINES


def test_each_claim_names_the_file_it_is_asserted_in():
    claims = fixtures.analyse_fact_sheet(commit="a" * 40)
    assert {claim.detail["assertion_path"] for claim in claims} == {fixtures.FEATURE_PATH}
    assert {claim.detail["assertion_commit"] for claim in claims} == {"a" * 40}
    assert {claim.evidence[0].uri for claim in claims} == {
        f"github:fixture/fixture@deadbeef:{fixtures.FEATURE_PATH}"}
