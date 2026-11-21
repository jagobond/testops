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
    Then the save button has an accessible name

  Scenario: the panel response body carries stable fact anchors
    Given the panel endpoint accepts a save
    Then the response body carries stable fact anchors
"""

GAP_SUBJECT = f"scenario:{FEATURE_PATH}#the save button has an accessible name"
DISTINCT_SUBJECT = f"scenario:{FEATURE_PATH}#the panel response body carries stable fact anchors"


def _bindings() -> list[stepbindings.Binding]:
    """HTTP-layer step bindings in the feature's own suite (panel_api -> panelapi)."""
    return [
        stepbindings.Binding(pattern="the panel endpoint accepts a save", verb="Given",
                             cls="PanelApiSteps", path="steps/PanelApiSteps.cs",
                             layer="api", suite="panelapi"),
        stepbindings.Binding(pattern="the save button has an accessible name", verb="Then",
                             cls="PanelApiSteps", path="steps/PanelApiSteps.cs",
                             layer="api", suite="panelapi"),
        stepbindings.Binding(pattern="the response body carries stable fact anchors", verb="Then",
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
    assert "Only a browser works that out" in claim.statement
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


# --- TESTOPS-11: restraint, and one pass with one label ------------------------------------------

META_CLAIM = "that count is correct for the store it was run against"


def _scenario_claim(path: str, name: str, *steps: str, layer: str = "api") -> dict:
    """Analyse one real-shaped scenario whose every asserting step binds at ``layer``."""
    text = f"Feature: constructed\n  Scenario: {name}\n"
    text += "".join(f"    Then {step}\n" for step in steps)
    feature = gherkin.parse(path, text)
    assert feature is not None
    suite = stepbindings.suite_of(path)
    bindings = [stepbindings.Binding(pattern=step, verb="Then", cls="Steps",
                                     path="Steps/Steps.cs", layer=layer, suite=suite)
                for step in steps]
    claims = level_fitness.analyse(
        features=[feature], bindings=bindings, surfaces=[],
        uri_for_path=lambda p: f"github:fixture/fixture@deadbeef:{p}",
        budget={"calls": 0, "tokens_in": 0, "tokens_out": 0},
    )
    return {claim.detail["assertion_text"]: claim for claim in claims}


def test_a_meta_claim_is_not_placed_by_its_nouns_even_when_its_step_is_bound():
    """AC1/AC2: the ticket's own example. "Store" is in the vocabulary; the claim is still a
    judgement with no comparison in it, so the instrument fallback must not rescue it."""
    claim = _scenario_claim("features/approval_queue.feature",
                            "The audit counts what rests on a batch decision", META_CLAIM,
                            layer="api")[META_CLAIM]
    assert claim.verdict == "unplaced"
    assert claim.detail["interaction_code"] == "U"
    assert "compared with" in claim.detail["established_by"]
    assert "compared with" in claim.statement
    assert "asserts that that" not in claim.statement
    assert not level_fitness._CODE_TOKEN.search(claim.statement)


def test_a_meta_claim_that_says_what_it_compares_is_placed():
    """AC1's other half: restraint is not a blanket. Naming the comparison makes it checkable."""
    text = "that count is correct because it matches the admitted fact count"
    claim = _scenario_claim("features/approval_queue.feature",
                            "The audit counts what rests on a batch decision", text,
                            layer="api")[text]
    assert claim.verdict == "distinct"
    assert claim.detail["interaction_code"] == "I1"


def test_one_verification_pass_carries_one_label():
    """AC5: an engine suite has no server, so no claim in it may be called a server response.

    The two claims keep the codes their own words earned; it is the label a reader trusts, and it
    must be the same for both.
    """
    claims = _scenario_claim("features/canon_verification.feature",
                             "The verification pass reports a failing result",
                             "the pass fails",
                             "the clean store exits with the success status",
                             layer="engine")
    first, second = claims["the pass fails"], claims["the clean store exits with the success status"]
    assert first.detail["interaction_label"] == second.detail["interaction_label"]
    assert first.detail["interaction_label"] == "settled by the engine's own answer about the stored data"
    for claim in claims.values():
        assert "server" not in claim.detail["interaction_label"], claim.detail["interaction_label"]
        assert "server" not in claim.statement, claim.statement
        assert level_fitness._reads("engine") in claim.statement, claim.statement


def test_a_review_statement_names_the_instrument_that_settles_it():
    """AC6: a page claim read through a browser is settled by the page, not by the response."""
    text = "every rendered fact sits in an element carrying a data-fact-id"
    claim = _scenario_claim("features/review_panel.feature",
                            "Every rendered fact is anchored", text, layer="ui")[text]
    assert claim.verdict == "review"
    assert claim.detail["interaction_label"] == "settled by the page the server sends"
    assert "The page the server sends settles that" in claim.statement
    assert "The response the server sends settles that" not in claim.statement