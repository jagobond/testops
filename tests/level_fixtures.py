"""Fixtures for the per-assertion claim tests (TESTOPS-4).

Everything here is in-memory: a parsed feature, synthetic step bindings and a fake ``github:`` URI.
No repository checkout, no network, no store - except where a test drives the pipeline, which is
done in ``test_case_per_claim.py`` through the same fixtures.
"""
from __future__ import annotations

from testops.analysers import level_fitness
from testops.extract import gherkin, stepbindings

FEATURE_PATH = "features/fact_sheet.feature"

# One scenario, three asserting steps: a Then, an And after it and a But after that. The Given and
# the When are context and must make no claim (AC2). Lines are 1-based and load-bearing (AC1).
FEATURE_TEXT = """\
Feature: fact sheet
  Scenario: the fact sheet is usable with a screen reader
    Given the fact sheet endpoint returns a sheet
    When a reader opens the fact sheet
    Then each fact's citation sits inside an element an assistive technology can name
    And the page is served with stable fact anchors
    But the response status is not an error
"""

ASSERTING_TEXTS = [
    "each fact's citation sits inside an element an assistive technology can name",
    "the page is served with stable fact anchors",
    "the response status is not an error",
]
ASSERTING_LINES = [5, 6, 7]

# Context steps only: nothing is asserted, so this feature must yield no claims at all.
CONTEXT_ONLY_TEXT = """\
Feature: fact sheet context
  Scenario: a reader opens the fact sheet
    Given a fact sheet exists
    And the reader is signed in
    When the reader opens the fact sheet
    And the sheet is loaded
"""

# A browser suite: the same response-status assertion, but this time a browser runs.
BROWSER_FEATURE_PATH = "features/fact_sheet_ui.feature"
BROWSER_FEATURE_TEXT = """\
Feature: fact sheet in a browser
  Scenario: a browser test checks the response status
    Given a reader opens the fact sheet in a browser
    Then the response status is 200
"""

API_SUITE = "factsheet"
BROWSER_SUITE = "factsheetui"


def _bind(pattern: str, verb: str, layer: str, suite: str) -> stepbindings.Binding:
    return stepbindings.Binding(pattern=pattern, verb=verb, cls="FactSheetSteps",
                                path=f"steps/{suite.capitalize()}Steps.cs", layer=layer, suite=suite)


def api_bindings() -> list[stepbindings.Binding]:
    """Every step of the fact-sheet feature bound to the HTTP client the suite actually uses."""
    return [_bind(pattern, verb, "api", API_SUITE) for pattern, verb in [
        ("the fact sheet endpoint returns a sheet", "Given"),
        ("a reader opens the fact sheet", "When"),
        *[(text, "Then") for text in ASSERTING_TEXTS],
    ]]


def browser_bindings() -> list[stepbindings.Binding]:
    return [_bind(pattern, verb, "ui", BROWSER_SUITE) for pattern, verb in [
        ("a reader opens the fact sheet in a browser", "Given"),
        ("the response status is 200", "Then"),
    ]]


def parse(path: str, text: str):
    feature = gherkin.parse(path, text)
    assert feature is not None, f"fixture did not parse as a feature: {path}"
    return feature


def analyse_text(text: str, bindings, path: str = FEATURE_PATH, **kwargs):
    """Run the real analyser over one in-memory feature."""
    return level_fitness.analyse(
        features=[parse(path, text)],
        bindings=bindings,
        surfaces=[],
        uri_for_path=lambda p: f"github:fixture/fixture@deadbeef:{p}",
        budget={"calls": 0, "tokens_in": 0, "tokens_out": 0},
        **kwargs,
    )


def analyse_fact_sheet(**kwargs):
    return analyse_text(FEATURE_TEXT, api_bindings(), **kwargs)


def by_text(claims) -> dict[str, object]:
    return {claim.detail["assertion_text"]: claim for claim in claims}


# --------------------------------------------------------------------------------------------
# A fake repository, for the two tests that drive the whole pipeline (AC6, AC7). It exists so
# those tests exercise the real run_level_fitness, store writes and case creation without a
# checkout or a network call.
# --------------------------------------------------------------------------------------------

COMMIT = "a" * 40

PIPELINE_FEATURE = """\
Feature: fact sheet
  Scenario: the fact sheet is usable with a screen reader
    Given the fact sheet endpoint returns a sheet
    Then each fact's citation sits inside an element an assistive technology can name
    And the citation is announced with a visible label

  Scenario: the fact sheet is served with anchors
    Given the fact sheet endpoint returns a sheet
    Then the response body carries stable fact anchors
"""

PIPELINE_STEPDEF = """\
public class FactSheetSteps {
  [Given("the fact sheet endpoint returns a sheet")]
  public void GivenTheEndpoint() {
    using var client = new HttpClient();
  }
  [Then("each fact's citation sits inside an element an assistive technology can name")]
  public void ThenNamed() {}
  [Then("the citation is announced with a visible label")]
  public void ThenLabel() {}
  [Then("the response body carries stable fact anchors")]
  public void ThenAnchors() {}
}
"""


def stub_pipeline(monkeypatch, pipeline, tmp_path, feature: str = PIPELINE_FEATURE,
                  stepdef: str = PIPELINE_STEPDEF):
    """Point the real pipeline at an in-memory repository and a throwaway store.

    Returns ``(store_path, connect)``: the path, and the real ``db.connect`` (which the pipeline's
    own patched version would otherwise shadow), so the caller can read back what the run wrote.
    A second call against the same ``tmp_path`` changes the repository the next run reads, which is
    how a test edits a feature between two runs over one store (TESTOPS-40).
    """
    from testops.collectors.github import Collected
    from testops.store import db

    path = tmp_path / "pipeline.db"
    real_connect = db.connect
    texts = {"sha-feature": feature, "sha-steps": stepdef}
    files = {"features/fact_sheet.feature": ("sha-feature", "feature"),
             "steps/FactSheetSteps.cs": ("sha-steps", "stepdef")}

    monkeypatch.setattr(pipeline, "load_env", lambda: {})
    monkeypatch.setattr(pipeline.db, "connect", lambda: real_connect(path))
    monkeypatch.setattr(pipeline.blobs, "text", lambda sha: texts[sha])
    monkeypatch.setattr(pipeline.github, "collect",
                        lambda repo, token, role="product": Collected(commit=COMMIT, files=files))
    monkeypatch.setattr(pipeline.surface_discovery, "discover",
                        lambda product_texts: pipeline.surface_discovery.Discovery((), "zero"))
    return path, real_connect

