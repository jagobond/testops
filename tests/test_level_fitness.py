"""AC6: level_fitness classifies a browser claim asserted over HTTP as a gap, and a claim settled
by the response body as distinct.

Fixtures are in-memory objects and a synthetic ``github:`` URI. No repository checkout, no network:
``test_analysis_runs_with_sockets_disabled`` disables sockets for the whole analysis.
"""
from __future__ import annotations

import socket

from testops.analysers import level_fitness
from testops.analysers.base import Claim
from testops.extract import gherkin, stepbindings

FEATURE_PATH = "features/panel_api.feature"
FEATURE_TEXT = """\
Feature: panel api
  Scenario: the save button has an accessible name
    Given the panel endpoint accepts a save
    Then the response status is 200

  Scenario: the panel response body carries stable fact anchors
    Given the panel endpoint accepts a save
    Then the response status is 200
"""

GAP_SUBJECT = f"scenario:{FEATURE_PATH}#the save button has an accessible name"
DISTINCT_SUBJECT = f"scenario:{FEATURE_PATH}#the panel response body carries stable fact anchors"


def _bindings() -> list[stepbindings.Binding]:
    """HTTP-layer step bindings in the feature's own suite (panel_api -> panelapi)."""
    return [
        stepbindings.Binding(pattern="the panel endpoint accepts a save", verb="Given",
                             cls="PanelApiSteps", path="steps/PanelApiSteps.cs",
                             layer="api", suite="panelapi"),
        stepbindings.Binding(pattern="the response status is 200", verb="Then",
                             cls="PanelApiSteps", path="steps/PanelApiSteps.cs",
                             layer="api", suite="panelapi"),
    ]


def _analyse() -> dict[str, Claim]:
    feature = gherkin.parse(FEATURE_PATH, FEATURE_TEXT)
    assert feature is not None and len(feature.scenarios) == 2

    claims = level_fitness.analyse(
        features=[feature],
        bindings=_bindings(),
        surfaces=[],
        uri_for_path=lambda path: f"github:fixture/fixture@deadbeef:{path}",
        budget={"calls": 0, "tokens_in": 0, "tokens_out": 0},
    )
    return {claim.subject_ref: claim for claim in claims}


def test_browser_claim_asserted_over_http_is_a_gap():
    claim = _analyse()[GAP_SUBJECT]
    assert claim.verdict == "gap"
    assert claim.detail["uses_browser"] is False
    assert claim.detail["needs_browser"] is True
    assert "needs a browser" in claim.statement
    assert [evidence.uri for evidence in claim.evidence] == [
        f"github:fixture/fixture@deadbeef:{FEATURE_PATH}"]


def test_claim_settled_by_the_response_body_is_distinct():
    claim = _analyse()[DISTINCT_SUBJECT]
    assert claim.verdict == "distinct"
    assert claim.detail["claim"] == "KP"
    assert claim.detail["uses_browser"] is False
    assert claim.detail["needs_browser"] is False


def test_analysis_runs_with_sockets_disabled(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("level_fitness attempted a network connection")

    monkeypatch.setattr(socket, "socket", refuse)
    claims = _analyse()
    assert claims[GAP_SUBJECT].verdict == "gap"
    assert claims[DISTINCT_SUBJECT].verdict == "distinct"