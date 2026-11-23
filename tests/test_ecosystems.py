"""TESTOPS-42A: the extractor seam, ecosystem detection, and the honesty of not supporting one.

The ticket's shape, in tests:

  * AC1 - an ecosystem is a module with a declared name and three functions; the registry refuses
    duplicates, refuses to guess between two matches, and refuses to default when nothing matches.
  * AC2 - the ecosystem each repository was read as is written into the run's snapshot and printed.
  * AC3 - the Reqnroll path is the old path. ``BINDING``/``SIGNALS``/``LAYER_ORDER`` still resolve,
    and the module's bindings are the same rows ``stepbindings`` produced, so the seams's proof is
    the absence of change (the corpus tests over the real store cover the rest).
  * AC4 - a detected, unsupported ecosystem reports ``not_assessable`` with its name, and never
    "none of its steps could be tied to a layer". Proven on the restfulbooker corpus in the store.
  * AC5 - cucumber-js raises instead of returning an empty binding list.
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
CYPRESS_SNAPSHOT = "restfulbooker-20261122-262404a9"
CYPRESS_TEST_REPO = ("m-pujic-levi9-com/cypress-cucumber-e2e-tests",
                     "262404a95784970315faeae6374ce8783ccbe598")
CYPRESS_PRODUCT_REPO = ("mwinteringham/restful-booker-platform",
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

def test_an_unsupported_ecosystem_refuses_rather_than_returning_an_empty_list():
    files = {"cypress/e2e/login.stepdef.js": "Then('a user is logged in', () => {});"}
    ecosystem = cucumber_js.ECOSYSTEM.detect(files)
    assert ecosystem is not None and ecosystem.supported is False
    assert ecosystem.reason
    with pytest.raises(ecosystems.UnsupportedEcosystem):
        cucumber_js.ECOSYSTEM.bindings(files)
    with pytest.raises(ecosystems.UnsupportedEcosystem):
        cucumber_js.ECOSYSTEM.drivers(files)


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


def test_an_unsupported_ecosystem_makes_the_run_not_assessable_and_says_why(monkeypatch,
                                                                           tmp_path):
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
    assert result.claims == []
    assert run["assessment"]["state"] == "not_assessable"
    assert "cucumber-js" in run["assessment"]["sentence"]
    assert "unsupported" in run["assessment"]["sentence"]
    assert status == 200
    # AC4's prohibition: the two sentences a reader could act on and cannot.
    assert "no layers found" not in text
    assert "could be tied to a layer" not in text
    assert "could not be tied to a layer" not in text
    assert "cucumber-js" in text
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
def test_the_restfulbooker_corpus_is_not_assessable_and_not_lied_about(monkeypatch, tmp_path):
    """AC4, on the corpus TESTOPS-39 used: 44 cucumber-js bindings, none of them read."""
    stored = sqlite3.connect(f"file:{STORED.as_posix()}?mode=ro", uri=True)
    stored.row_factory = sqlite3.Row
    try:
        test_arm = _stored_arm(stored, *CYPRESS_TEST_REPO)
        product_arm = _stored_arm(stored, *CYPRESS_PRODUCT_REPO)
    finally:
        stored.close()
    assert sum(1 for _sha, kind in test_arm.values() if kind == "feature") == 6
    assert test_arm, "the restfulbooker snapshot is not in this store"

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
    assert result.stats["ecosystems"]["test"]["supported"] is False
    # The three facts the report asked for: what was recognised, in what quantity, and that
    # support does not exist.
    assert any("44 cucumber-js step-binding declarations" in line
               for line in result.stats["ecosystems"]["test"]["evidence"])
    assert run["assessment"]["state"] == "not_assessable"
    assert "cucumber-js" in run["assessment"]["sentence"]
    assert "cucumber-js is unsupported" in run["assessment"]["sentence"]
    assert "cannot read" in run["assessment"]["sentence"]
    assert "44 cucumber-js step-binding declarations" in text
    assert "no support for cucumber-js" in text
    assert "could be tied to a layer" not in text
    assert "no layers" not in text


def _read_blob(sha: str) -> str:
    path = BLOB_DIR / sha[:2] / sha[2:]
    return path.read_bytes().decode("utf-8-sig", errors="replace")
