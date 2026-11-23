"""TESTOPS-42C-3: placement, the wrong-layer guard, and an honest duplication scope.

The ticket's acceptance criteria, in tests, where they are not already pinned by the corpus run in
``test_ecosystems.py``:

  * AC5 - a ``cy.request`` command inside a UI-named file is ``api``, and per-file layer inference
    cannot come back: one file holding both layers yields both, and the cucumber module never
    calls the .NET reader's per-file path;
  * AC6 - the duplication analyser runs on the corpus and pairs a JS feature with the JS step
    definitions of its own suite, recording the extractor it paired with;
  * AC9 - a regex literal and a concatenation in one file are recorded with ``path:line`` and a
    reason, place nothing, and the readable declaration beside them still becomes a binding;
  * AC10 - the 11 ``Step(this, ...)`` delegations stay unknown, are When-steps, and do not move
    the 17/43 asserting figure.

The corpus tests read the build store read-only and skip when it is absent.
"""
from __future__ import annotations

import inspect
import sqlite3
from collections import Counter
from pathlib import Path

import pytest

from testops.analysers import duplication
from testops.extract import gherkin
from testops.extract.ecosystems import cucumber_js

ROOT = Path(__file__).resolve().parents[1]
STORED = ROOT / "data" / "testops.db"
BLOB_DIR = ROOT / "data" / "blobs"

CYPRESS_SNAPSHOT = "restfulbooker-20261122-262404a9"
CYPRESS_TEST_REPO = ("m-pujic-levi9-com/cypress-cucumber-e2e-tests",
                     "262404a95784970315faeae6374ce8783ccbe598")


def _corpus() -> dict[str, str]:
    conn = sqlite3.connect(f"file:{STORED.as_posix()}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "select distinct uri, blob_sha from artefact"
            " where snapshot_id = ? and uri like ? order by uri",
            (CYPRESS_SNAPSHOT, f"github:{CYPRESS_TEST_REPO[0]}@{CYPRESS_TEST_REPO[1]}:%"),
        ).fetchall()
    finally:
        conn.close()
    prefix = f"github:{CYPRESS_TEST_REPO[0]}@{CYPRESS_TEST_REPO[1]}:"
    return {uri[len(prefix):]: (BLOB_DIR / sha[:2] / sha[2:]).read_bytes()
            .decode("utf-8-sig", errors="replace")
            for uri, sha in rows}


requires_store = pytest.mark.skipif(not STORED.exists(),
                                    reason="the product store is a build artefact")


# --------------------------------------------------------------------------- AC5: wrong layer

def test_a_cy_request_command_in_a_ui_named_file_is_api():
    """The file is called room-management and lives in the UI suite; the command is HTTP."""
    files = {
        "cypress/support/custom-commands/room-management.js": (
            "Cypress.Commands.add('createRoom', (name) => {\n"
            "  cy.get('#roomName').type(name);\n"
            "  cy.get('#save').click();\n"
            "});\n"
            "Cypress.Commands.add('createRoomViaApi', (name) => {\n"
            "  cy.request({ method: 'POST', url: `${apiUrl}/room/`, body: { name } });\n"
            "});\n"),
        "cypress/e2e/features/admin-panel/management/room-management.stepdef.js": (
            "When('the admin creates a room on the page', () => {\n"
            "  cy.createRoom('114');\n"
            "});\n"
            "When('a room is created over HTTP', () => {\n"
            "  cy.createRoomViaApi('114');\n"
            "});\n"),
    }

    rows = {binding.pattern: binding for binding in cucumber_js.ECOSYSTEM.bindings(files)}

    assert "room-management" in rows["a room is created over HTTP"].path
    assert rows["a room is created over HTTP"].layer == "api"
    assert rows["the admin creates a room on the page"].layer == "ui"


def test_per_file_layer_inference_cannot_be_reintroduced():
    """One step-definition file holds both layers, and the reader has no per-file path at all."""
    files = {
        "cypress/support/custom-commands/mixed.js": (
            "Cypress.Commands.add('byApi', () => { cy.request('/x'); });\n"
            "Cypress.Commands.add('byBrowser', () => { cy.get('#x').click(); });\n"),
        "cypress/e2e/ui/mixed.stepdef.js": (
            "When('through the API', () => { cy.byApi(); });\n"
            "When('through the browser', () => { cy.byBrowser(); });\n"),
    }

    rows = {binding.pattern: binding for binding in cucumber_js.ECOSYSTEM.bindings(files)}
    assert rows["through the API"].layer == "api"
    assert rows["through the browser"].layer == "ui"
    assert rows["through the API"].path == rows["through the browser"].path

    # The static half of the guard: the cucumber module never calls the .NET reader's per-file
    # inference, so the defect cannot arrive by an edit that reuses it.
    source = inspect.getsource(cucumber_js)
    assert "stepbindings.parse_file" not in source
    assert "build_driver_map" not in source
    assert "stepbindings.infer_layer_from_body" not in source


# --------------------------------------------------------------------------- AC6: duplication

def _features(files: dict[str, str]) -> list[gherkin.Feature]:
    out = [gherkin.parse(path, text) for path, text in sorted(files.items())
           if path.endswith(".feature")]
    return [feature for feature in out if feature]


@requires_store
def test_the_duplication_analyser_runs_on_the_js_corpus_without_crashing():
    files = _corpus()
    bindings = cucumber_js.ECOSYSTEM.bindings(files)

    claims = duplication.analyse(features=_features(files), bindings=bindings,
                                 uri_for_path=lambda path: f"uri:{path}",
                                 suite_of=cucumber_js.suite_of_path, extractor="cucumber-js")

    # The corpus has no two scenarios with the same normalised steps and data, so there is nothing
    # to report - and the answer is a measured zero, not a crash and not a refusal.
    assert claims == []


def test_duplication_pairs_a_js_feature_with_its_own_suite_s_js_steps():
    """Two identical scenarios in two suites: each copy's layer comes from its own declarations."""
    files = {
        "cypress/e2e/booking/booking.stepdef.js": (
            "Then('the room is available', () => { cy.request('/room/1'); });\n"),
        "cypress/e2e/contact/contact.stepdef.js": (
            "Then('the room is available', () => { cy.get('#available').should('be.visible'); });\n"),
        "cypress/e2e/booking/book.feature": (
            "Feature: booking\n  Scenario: the room exists\n    Then the room is available\n"),
        "cypress/e2e/contact/contact.feature": (
            "Feature: contact\n  Scenario: the room exists\n    Then the room is available\n"),
    }
    bindings = cucumber_js.ECOSYSTEM.bindings(files)

    claims = duplication.analyse(features=_features(files), bindings=bindings,
                                 uri_for_path=lambda path: f"uri:{path}",
                                 suite_of=cucumber_js.suite_of_path, extractor="cucumber-js")

    assert len(claims) == 1
    detail = claims[0].detail
    assert detail["extractor"] == "cucumber-js"
    assert detail["suite"] in {"booking", "contact"}
    # The two copies are judged at different layers because each suite's own declaration was read.
    assert detail["layer"] == "ui"
    assert detail["cheapest"] == "api"
    assert "over HTTP" in claims[0].statement


# --------------------------------------------------------------------------- AC9: unreadable

def test_two_unreadable_declarations_are_recorded_and_the_rest_is_placed():
    files = {"cypress/e2e/front/booking/booking.stepdef.js": (
        "Given(/^a (\\d+) user is logged in$/, () => {});\n"
        "When('Visitor will get validation/' +\n"
        "     'mandatory error message: {string}', (message) => { cy.get('.alert'); });\n"
        "Then('a readable step', () => { cy.get('.alert').should('be.visible'); });\n")}

    records = cucumber_js.ECOSYSTEM.unreadable(files)
    assert [record["kind"] for record in records] == ["regex-literal", "concatenation"]
    assert [(record["line"], record["reason"] != "") for record in records] == [(1, True), (2, True)]

    bindings = cucumber_js.ECOSYSTEM.bindings(files)
    assert [binding.pattern for binding in bindings] == ["a readable step"]

    ecosystem = cucumber_js.ECOSYSTEM.detect(files)
    assert any("2 declarations cannot be read" in line for line in ecosystem.evidence)


# --------------------------------------------------------------------------- AC10: the unknowns

@requires_store
def test_the_eleven_step_delegations_stay_unknown_and_do_not_move_the_asserting_count():
    bindings = cucumber_js.ECOSYSTEM.bindings(_corpus())
    unknown = [binding for binding in bindings if binding.layer == "unknown"]

    assert len(unknown) == 11
    # They are When-steps: context, never an assertion, so they cannot raise the 17/43 figure.
    assert Counter(binding.verb for binding in unknown) == {"When": 11}
    assert all("re-invokes another step" in binding.layer_reason for binding in unknown)
    # The delegation names its target and the layer_reason names the delegation; nothing is
    # invented to raise the count. The 17/43 run is pinned in test_ecosystems.py.
    assert all("Step(this" in binding.layer_reason for binding in unknown)
    assert Counter(binding.verb for binding in bindings) == {"When": 26, "Then": 13, "Given": 5}
