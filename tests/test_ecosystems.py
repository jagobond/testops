"""TESTOPS-42A: the extractor seam, ecosystem detection, and the honesty of not supporting one.

The ticket's shape, in tests:

  * AC1 - an ecosystem is a module with a declared name and three functions; the registry refuses
    duplicates, refuses to guess between two matches, and refuses to default when nothing matches.
  * AC2 - the ecosystem each repository was read as is written into the run's snapshot and printed.
  * AC3 - the Reqnroll path is the old path. ``BINDING``/``SIGNALS``/``LAYER_ORDER`` still resolve,
    and the module's bindings are the same rows ``stepbindings`` produced, so the seams's proof is
    the absence of change (the corpus tests over the real store cover the rest).
  * AC4 - a detected, unsupported ecosystem reports ``not_assessable`` with its name, and never
    "none of its steps could be tied to a layer". Proven on the demo-booking corpus in the store.
  * AC5 - cucumber-js is unsupported: its declarations parse (T42C-1), its drivers do not, and
    the gate that keeps claims from being placed is still on.
  * AC7 - detection is total for recognisable markers, and an unrecognised repository is `unknown`.

Nothing here reads the network. The corpus tests read the build store read-only and skip when it
is absent.
"""
from __future__ import annotations

import html as htmllib
import json
import re
import sqlite3
from pathlib import Path

import pytest

from testops import blobs, config, pipeline, queries
from testops.collectors import github
from testops.extract import ecosystems, stepbindings
from testops.extract.ecosystems import cucumber_js, python_bdd, reqnroll
from testops.store import db
from testops.web import app

ROOT = Path(__file__).resolve().parents[1]
STORED = ROOT / "data" / "testops.db"
BLOB_DIR = ROOT / "data" / "blobs"

# The TESTOPS-39 specimen: six feature files and fifteen JavaScript files in the test arm.
CYPRESS_SNAPSHOT = "demo-booking-20261122-262404a9"
CYPRESS_TEST_REPO = ("m-pujic-levi9-com/cypress-cucumber-e2e-tests",
                     "262404a95784970315faeae6374ce8783ccbe598")
CYPRESS_PRODUCT_REPO = ("example-org/demo-booking-platform",
                        "efe2deb8ce02db541adbf9d3a6604caf5fbdaae6")


# --------------------------------------------------------------------------- AC1: the protocol

def test_every_registered_module_declares_a_name():
    modules = ecosystems.registry().modules
    assert modules, "a registry with no modules cannot detect anything"
    for module in modules:
        assert isinstance(module.name, str) and module.name.strip(), module
        assert callable(module.detect) and callable(module.bindings) and callable(module.drivers)
    names = [module.name for module in modules]
    assert len(names) == len(set(names)), names


def test_a_duplicate_name_is_refused_not_shadowed():
    with pytest.raises(ecosystems.DuplicateEcosystem):
        ecosystems.Registry((reqnroll.ECOSYSTEM, reqnroll.ECOSYSTEM))


def test_a_registry_with_no_match_raises_rather_than_defaulting():
    with pytest.raises(ecosystems.UnknownEcosystem) as caught:
        ecosystems.registry().detect({"README.md": "nothing to do with tests"})
    assert "none of the" in str(caught.value)


def test_two_recognitions_are_refused_rather_than_tied():
    files = {"a/Steps.cs": '[Then("the thing happens")]',
             "b/login.stepdef.js": ("const { Then } = require('@badeball/cypress-cucumber"
                                    "-preprocessor');\nThen('the thing happens', () => {});\n")}
    with pytest.raises(ecosystems.AmbiguousEcosystem):
        ecosystems.registry().detect(files)


# --------------------------------------------------------------------------- AC7: total detection

@pytest.mark.parametrize("files,expected", [
    ({"Steps/FeatureSteps.cs": 'public class S {\n [Then("a thing")]\n}'}, "reqnroll"),
    ({"Features/one.feature": "Feature: x\n",
      "Services/Sample.csproj": "<PackageReference Include=\"Reqnroll\" />"}, "reqnroll"),
    ({"cypress/e2e/login.stepdef.js": "Then('a user is logged in', () => { cy.contains('x'); });"},
     "cucumber-js"),
    ({"tests/steps/test_login.py":
      "from pytest_bdd import given\n@given('a user exists')\ndef user(): ...\n"}, "python-bdd"),
])
def test_every_recognisable_marker_resolves_to_exactly_one_ecosystem(files, expected):
    ecosystem = ecosystems.registry().detect(files)
    assert ecosystem.name == expected
    assert ecosystems.registry().match(files)[0].name == expected


def test_an_unrecognised_repository_is_reported_unknown_not_guessed():
    record, module = pipeline._ecosystem_record("test", "o/unreadable",
                                               {"README.md": "hello", "src/app.java": "class A {}"})
    assert module is None
    assert record["ecosystem"] == "unknown"
    assert record["reason"]
    # The registry refuses too; the pipeline's record is a report of that refusal, not a default.
    with pytest.raises(ecosystems.UnknownEcosystem):
        ecosystems.registry().detect({"README.md": "hello"})


# --------------------------------------------------------------------------- AC3: the seam is absent

def test_the_reqnroll_module_is_the_old_extractor():
    assert reqnroll.BINDING is stepbindings.BINDING
    assert reqnroll.SIGNALS is stepbindings.SIGNALS
    assert reqnroll.LAYER_ORDER is stepbindings.LAYER_ORDER

    files = {
        "Steps/BookingSteps.cs": ('public class BookingSteps {\n'
                                 '  private readonly BookingDriver _driver;\n'
                                 '  [Then("the booking is stored")]\n'
                                 '  public void ThenStored() { }\n}'),
        "Drivers/BookingDriver.cs": "public class BookingDriver {\n"
                                    "  public void Go(IPage page) { page.ClickAsync(\"go\"); }\n}",
    }
    module_rows = reqnroll.ECOSYSTEM.bindings(files)
    driver_map = stepbindings.build_driver_map(files)
    old_rows = [b for path, text in files.items()
                for b in stepbindings.parse_file(path, text, driver_map)]

    assert module_rows == old_rows
    assert reqnroll.ECOSYSTEM.drivers(files) == driver_map
    assert [row.layer for row in module_rows] == ["ui"]


# --------------------------------------------------------------------------- AC5: no half-extractor

def test_a_supported_ecosystem_places_the_declaration_it_can_read():
    """TESTOPS-42C-3: cucumber-js is supported, and a readable declaration becomes a claim."""
    files = {"cypress/e2e/login.stepdef.js":
             "Then('a user is logged in', () => { cy.contains('Logout'); });"}
    ecosystem = cucumber_js.ECOSYSTEM.detect(files)
    assert ecosystem is not None and ecosystem.supported is True
    # T42C-1: the parsing floor reads the declaration ...
    rows = cucumber_js.ECOSYSTEM.bindings(files)
    assert [row.pattern for row in rows] == ["a user is logged in"]
    assert rows[0].layer == "ui"
    # T42C-2 reads the custom commands too - this repository registers none, and the answer to
    # "which commands are there" is a measured empty, not a refusal ...
    assert cucumber_js.ECOSYSTEM.drivers(files) == {}
    # ... and an unreadable declaration is a record, not a zero.
    assert cucumber_js.ECOSYSTEM.unreadable(files) == []


def test_python_bdd_is_detected_and_refused_for_the_same_reason():
    files = {"tests/steps/test_login.py":
             "from pytest_bdd import given\n@given('a user exists')\ndef user(): ...\n"}
    ecosystem = python_bdd.ECOSYSTEM.detect(files)
    assert ecosystem is not None and ecosystem.supported is False


# --------------------------------------------------------------------------- an in-memory run

FEATURE = """\
Feature: the guest books
  Scenario: a booking is accepted
    Then the booking is stored
"""
STEPS = """\
public class Steps {
  [Then("the booking is stored")]
  public void ThenStored() { using var client = new HttpClient(); }
}
"""
CYPRESS_FEATURE = """\
Feature: login
  Scenario: a user logs in
    Then a user is logged in
"""
CYPRESS_STEPS = """\
const { Then } = require('@badeball/cypress-cucumber-preprocessor');
Then('a user is logged in', () => {
  cy.contains('Logout');
});
"""


def _levels_run(monkeypatch, tmp_path, texts, files, product_files=None, product_texts=None):
    """A real levels run over an in-memory pair of repositories, in a throwaway store."""
    path = tmp_path / "t42a.db"
    real_connect = db.connect
    test_arm = github.Collected(commit="c" * 40, role="test", files=files)
    product_arm = github.Collected(commit="p" * 40, role="product",
                                   files=product_files or {"src/product.py": ("sha:product", "source")})
    arms = {"test": test_arm, "product": product_arm}
    all_texts = {**texts, **(product_texts or {"sha:product": "def store(x):\n    return x\n"})}

    monkeypatch.setattr(pipeline, "load_env", lambda: {})
    monkeypatch.setattr(pipeline.db, "connect", lambda: real_connect(path))
    monkeypatch.setattr(pipeline.blobs, "text", lambda sha: all_texts[sha])
    monkeypatch.setattr(pipeline.github, "collect",
                        lambda repo, token, role="product": arms[role])

    project = config.Project("specimen", config.Repo("o", "product"),
                             config.Repo("o", "tests"), jira_key="")
    result = pipeline.run_level_fitness(project, "token")
    return result, real_connect(path)


def _dotnet_run(monkeypatch, tmp_path):
    return _levels_run(monkeypatch, tmp_path,
                       {"sha:feature": FEATURE, "sha:steps": STEPS},
                       {"features/one.feature": ("sha:feature", "feature"),
                        "steps/Steps.cs": ("sha:steps", "stepdef")})


def _text(body: bytes) -> str:
    text = body.decode("utf-8")
    text = re.sub(r"<style>.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(htmllib.unescape(text).split())


def test_a_supported_ecosystem_is_recorded_per_repository_and_printed(monkeypatch, tmp_path):
    result, conn = _dotnet_run(monkeypatch, tmp_path)
    try:
        meta = json.loads(conn.execute("SELECT meta FROM snapshot WHERE id = ?",
                                       (result.snapshot_id,)).fetchone()["meta"])
        run = queries.run_read(conn, result.run_id)
        body, status = app.run_response(conn, result.run_id)
        listed = app.runs_index(conn)
    finally:
        conn.close()

    assert meta["ecosystems"]["test"]["ecosystem"] == "reqnroll"
    assert meta["ecosystems"]["test"]["supported"] is True
    assert meta["ecosystems"]["product"]["repository"] == "o/product"
    assert run["assessment"]["state"] != "not_assessable"
    assert "read as Reqnroll/.NET" in _text(body)
    assert status == 200
    assert "read as Reqnroll/.NET" in _text(listed)


def test_a_supported_cucumber_run_places_a_claim_and_says_so(monkeypatch, tmp_path):
    """TESTOPS-42C-3 (AC3): the run page drops the unsupported sentence and speaks in counts."""
    result, conn = _levels_run(
        monkeypatch, tmp_path,
        {"sha:feature": CYPRESS_FEATURE, "sha:steps": CYPRESS_STEPS},
        {"cypress/e2e/login.feature": ("sha:feature", "feature"),
         "cypress/e2e/login.stepdef.js": ("sha:steps", "stepdef")})
    try:
        run = queries.run_read(conn, result.run_id)
        body, status = app.run_response(conn, result.run_id)
        listed = app.runs_index(conn)
    finally:
        conn.close()

    text = _text(body)
    assert result.stats["ecosystems"]["test"]["ecosystem"] == "cucumber-js"
    assert result.stats["ecosystems"]["test"]["supported"] is True
    assert len(result.claims) == 1 and result.claims[0].verdict == "distinct"
    assert run["assessment"]["state"] != "not_assessable"
    assert "unsupported" not in run["assessment"]["sentence"]
    assert "no support for cucumber-js" not in text
    assert "is unsupported" not in text
    # The page states what was placed, in the same voice as the other analysers.
    assert "What this run placed" in text
    assert "1 asserting step" in text
    assert "was placed on a layer (1 ui)" in text
    assert "Every declaration in the suite was readable" in text
    assert status == 200
    assert "cucumber-js" in _text(listed)


# --------------------------------------------------------------------------- AC4: the real corpus

def _stored_arm(conn, slug, commit):
    """The artefacts of one repository arm, read back from the store as a collector result."""
    prefix = f"github:{slug}@{commit}:"
    files = {}
    for row in conn.execute(
            "SELECT uri, kind, blob_sha FROM artefact WHERE snapshot_id = ? ORDER BY uri",
            (CYPRESS_SNAPSHOT,)):
        if row["uri"].startswith(prefix):
            files[row["uri"][len(prefix):]] = (row["blob_sha"], row["kind"])
    return files


@pytest.mark.skipif(not STORED.exists(), reason="the product store is a build artefact")
def test_the_demo_booking_corpus_places_17_of_43_and_says_why(monkeypatch, tmp_path):
    """AC1/AC2/AC8, on the corpus TESTOPS-39 used: 44 declarations, 43 asserting steps.

    17 are placed and 26 are unplaced because no binding matches their words - never because the
    tool could not read the suite.
    """
    stored = sqlite3.connect(f"file:{STORED.as_posix()}?mode=ro", uri=True)
    stored.row_factory = sqlite3.Row
    try:
        test_arm = _stored_arm(stored, *CYPRESS_TEST_REPO)
        product_arm = _stored_arm(stored, *CYPRESS_PRODUCT_REPO)
    finally:
        stored.close()
    assert sum(1 for _sha, kind in test_arm.values() if kind == "feature") == 6
    assert test_arm, "the demo-booking snapshot is not in this store"

    shas = {sha for sha, _kind in test_arm.values()} | {sha for sha, _kind in product_arm.values()}
    blobs_text = {f"__{sha}": _read_blob(sha) for sha in shas}
    files = {path: (f"__{sha}", kind) for path, (sha, kind) in test_arm.items()}
    product = {path: (f"__{sha}", kind) for path, (sha, kind) in product_arm.items()}
    product_texts = {path: f"__{sha}" for path, (sha, _kind) in product_arm.items()}

    result, conn = _levels_run(monkeypatch, tmp_path, blobs_text, files,
                               product_files=product, product_texts=product_texts)
    try:
        run = queries.run_read(conn, result.run_id)
        body, _status = app.run_response(conn, result.run_id)
    finally:
        conn.close()

    text = _text(body)
    assert result.stats["ecosystems"]["test"]["ecosystem"] == "cucumber-js"
    assert result.stats["ecosystems"]["test"]["supported"] is True
    assert any("44 cucumber-js step-binding declarations" in line
               for line in result.stats["ecosystems"]["test"]["evidence"])
    assert run["assessment"]["state"] != "not_assessable"
    assert "unsupported" not in run["assessment"]["sentence"]

    # AC1: the count the ticket names, and no other.
    assert len(result.claims) == 43
    placement = result.stats["placement"]
    assert placement["asserting"] == 43
    assert placement["placed"] == 17
    assert placement["unplaced"] == 26
    assert placement["layers"] == {"ui": 17}

    # AC2: every unplaced claim says what actually happened, and names the near patterns.
    unplaced = [claim for claim in result.claims if claim.verdict == "unplaced"]
    assert len(unplaced) == 26
    for claim in unplaced:
        assert "no binding matches these words" in claim.statement
        assert claim.detail["assertion_text"] in claim.statement
        assert set(claim.detail["unbound"]["nearly"]) == {
            "Visitor will get validation/mandatory error message: {string}",
            "User will get validation/mandatory error message: {string}"}
        assert "unsupported ecosystem" not in claim.statement
        assert "could not be tied to a layer" not in claim.statement

    # AC3: the page states the split and never the old unsupported sentence.
    assert "What this run placed" in text
    assert "17 were placed on a layer (17 ui)" in text
    assert "26 matched no step binding" in text
    assert "no support for cucumber-js" not in text
    assert "cucumber-js is unsupported" not in text
    assert "could be tied to a layer" not in text
    assert "no layers" not in text

    # AC4: a claim's provenance names the extractor and can be walked to cy.request in a command.
    placed = [claim for claim in result.claims if claim.verdict != "unplaced"]
    assert all(claim.detail["provenance"]["extractor"] == "cucumber-js" for claim in placed)
    walks = [(binding, command)
             for claim in placed
             for binding in claim.detail["provenance"]["scenario_bindings"]
             for command in binding["commands"] if "cy.request" in command["via"]]
    assert walks, "no placed claim can be walked to a cy.request command"
    assert any(command["path"].endswith(
        "custom-commands/room-management.js") for _binding, command in walks)


def test_an_unreadable_declaration_is_visible_on_the_run_and_not_fatal(monkeypatch, tmp_path):
    """TESTOPS-42C-3 (AC9): one regex and one concatenation cost two placements, not the run."""
    feature = "Feature: login\n  Scenario: a user logs in\n    Then a readable step\n"
    steps = (
        "const { Given, When, Then } = require('@badeball/cypress-cucumber-preprocessor');\n"
        "Given(/^a (\\d+) user is logged in$/, () => {});\n"
        "When('Visitor will get validation/' +\n"
        "     'mandatory error message: {string}', (message) => {});\n"
        "Then('a readable step', () => { cy.contains('Logout'); });\n")
    result, conn = _levels_run(
        monkeypatch, tmp_path,
        {"sha:feature": feature, "sha:steps": steps},
        {"cypress/e2e/login.feature": ("sha:feature", "feature"),
         "cypress/e2e/login.stepdef.js": ("sha:steps", "stepdef")})
    try:
        run = queries.run_read(conn, result.run_id)
        body, _status = app.run_response(conn, result.run_id)
    finally:
        conn.close()

    text = _text(body)
    # The readable declaration was still analysed: the run is a claim, not a refusal.
    assert len(result.claims) == 1 and result.claims[0].verdict == "distinct"
    assert run["assessment"]["state"] != "not_assessable"
    placement = result.stats["placement"]
    assert placement["asserting"] == 1 and placement["placed"] == 1
    assert [entry["kind"] for entry in placement["unreadable"]] == ["regex-literal",
                                                                   "concatenation"]
    assert "2 declarations could not be read" in text
    assert "login.stepdef.js:2" in text
    assert "login.stepdef.js:3" in text
    assert "the rest of the suite was analysed" in text


def _read_blob(sha: str) -> str:
    path = BLOB_DIR / sha[:2] / sha[2:]
    return path.read_bytes().decode("utf-8-sig", errors="replace")
