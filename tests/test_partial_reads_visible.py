"""TESTOPS-43: a sentence that hides its own partial reads.

TESTOPS-41 stopped a skipped file being counted as consulted. Three smaller lies stayed in the
*sentence* rather than the record, and this file pins the fix for each:

  * AC1 - the aggregate cannot say which capability supplied what. "code and test code returned 2
    items" is true of 2-and-0 and of 1-and-1, and a reader cannot tell them apart. A capability
    that returned nothing is now named with its zero.
  * AC2 - a capability that read some files and lost others still said only "consulted". It now
    says how many files it read and how many kinds it could not read, in one parenthetical.
  * AC3 - a skip that broke no capability rendered nowhere: `_skip_reason` names one kind, and the
    "Files this run could not read" list appeared only when an unread capability needed
    explaining. A run that skips 500 `.sql` files and reads its code fine now says so, always,
    with each kind's count, its reason, and the names behind a disclosure.

AC4 pins the two sentences that must not change - Demo Product and DemoService have no capability that
lost a file, so neither gains a word. AC5 is structural: the wording lives in `sources.py`, and
no page module builds its own. AC6 is a lint: the sentence uses the page's vocabulary and repeats
nothing the page states beside it.

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

from testops import blobs, config, pipeline, queries, sources
from testops.collectors import github
from testops.store import db
from testops.web import app

ROOT = Path(__file__).resolve().parents[1]
STORED = ROOT / "data" / "testops.db"

DEMO_RUN = "demo-product-levels-20261122T204947"
DEMO_SERVICE_RUN = "demo-service-dup-20261122T205100"
DEMO_SENTENCE = "Assessed: code and test code were consulted and returned 95 items."
DEMO_SERVICE_SENTENCE = "Assessed: test code was consulted and returned 158 items."


# --------------------------------------------------------------------------- a registry in memory

def _registry(*readings: sources.Reading) -> sources.Registry:
    kind = sources.SourceKind(sources.GITHUB, "GitHub", (sources.CODE, sources.TEST_CODE),
                              sources.SourceState(sources.AVAILABLE, readings=readings))
    return sources.Registry([kind])


def _sentence(*readings: sources.Reading, capabilities=None) -> str:
    asked = capabilities or {reading.capability for reading in readings}
    return _registry(*readings).assess(asked).sentence()


# --------------------------------------------------------------------------- AC1: which supplied what

def test_a_capability_that_returned_nothing_is_named_with_its_zero():
    """The review's scenario: 2 items from test code, nothing from code."""
    sentence = _sentence(sources.Reading(sources.CODE, observed=0),
                         sources.Reading(sources.TEST_CODE, observed=2))

    assert sentence == "Assessed: code returned 0 items; test code returned 2 items."


def test_two_one_and_one_is_not_told_as_two_and_zero():
    zero_and_two = _sentence(sources.Reading(sources.CODE, observed=0),
                             sources.Reading(sources.TEST_CODE, observed=2))
    one_and_one = _sentence(sources.Reading(sources.CODE, observed=1),
                            sources.Reading(sources.TEST_CODE, observed=1))

    # Same total, different facts, so they cannot share a sentence.
    assert zero_and_two != one_and_one
    assert "0 items" in zero_and_two
    assert one_and_one == "Assessed: code and test code were consulted and returned 2 items."


def test_both_capabilities_returning_items_keeps_one_aggregate_sentence():
    """The zero is the fact a total hides. Without it, the total states the same thing."""
    assert _sentence(sources.Reading(sources.CODE, observed=1),
                     sources.Reading(sources.TEST_CODE, observed=1)) == \
        "Assessed: code and test code were consulted and returned 2 items."


# --------------------------------------------------------------------------- AC2: partial is said

def test_a_partially_read_capability_says_what_it_read_and_what_it_could_not():
    sentence = _sentence(
        sources.Reading(sources.CODE, observed=12,
                        lost=({"reason": github.SIZE_CAP, "kind": ".cs", "count": 3},
                              {"reason": github.SIZE_CAP, "kind": ".feature", "count": 1})),
        sources.Reading(sources.TEST_CODE, observed=48))

    assert sentence == ("Assessed: code and test code were consulted and returned 60 items "
                        "(3 .cs files and 1 other kind unreadable).")


def test_a_single_lost_kind_is_named_with_its_count():
    sentence = _sentence(sources.Reading(sources.CODE, observed=1,
                                         lost=({"reason": github.SIZE_CAP, "kind": ".py",
                                                "count": 1},)),
                         sources.Reading(sources.TEST_CODE, observed=1))

    assert sentence.endswith("(1 .py file unreadable).")


def test_a_complete_reading_gains_no_parenthetical():
    """No capability lost a file it would have read, so there is nothing to add."""
    sentence = _sentence(sources.Reading(sources.CODE, observed=45),
                         sources.Reading(sources.TEST_CODE, observed=50))

    assert "(" not in sentence
    assert sentence == DEMO_SENTENCE


# --------------------------------------------------------------------------- AC4: the pins

def test_demo_product_and_demo_service_sentences_are_unchanged():
    """Both recorded no lost file, so the wording is exactly what it was before this ticket."""
    assert _sentence(sources.Reading(sources.CODE, observed=45),
                     sources.Reading(sources.TEST_CODE, observed=50)) == DEMO_SENTENCE
    assert _sentence(sources.Reading(sources.TEST_CODE, observed=158)) == DEMO_SERVICE_SENTENCE


def test_a_record_written_before_readings_still_reads_as_it_did():
    stored = {"github": {"id": "github", "title": "GitHub", "capabilities": ["code", "test_code"],
                         "state": "available", "reason": "", "blocked_by": "", "observed": 95,
                         "route": "github-api", "note": "", "order": 0}}
    registry = sources.Registry.from_record(stored)

    assert registry.assess({sources.CODE, sources.TEST_CODE}).sentence() == DEMO_SENTENCE


@pytest.mark.skipif(not STORED.exists(), reason="the product store is a build artefact")
@pytest.mark.parametrize("run_id,sentence", [(DEMO_RUN, DEMO_SENTENCE),
                                             (DEMO_SERVICE_RUN, DEMO_SERVICE_SENTENCE)])
def test_the_stored_runs_still_render_the_sentence_they_rendered(run_id, sentence):
    conn = sqlite3.connect(f"file:{STORED.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        run = queries.run_read(conn, run_id)
    finally:
        conn.close()

    assert run is not None, f"the pinned run {run_id} is not in the store"
    assert run["assessment"]["sentence"] == sentence


# --------------------------------------------------------------------------- an in-memory levels run

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
PRODUCT = "def store(booking):\n    return booking\n"

TEXTS = {"sha:feature": FEATURE, "sha:steps": STEPS, "sha:product": PRODUCT}


def _levels_run(monkeypatch, tmp_path, *, product_files, product_skipped):
    """A real levels run over an in-memory pair of repositories, in a throwaway store."""
    path = tmp_path / "t43.db"
    real_connect = db.connect
    test_arm = github.Collected(commit="c" * 40, role="test",
                                files={"features/one.feature": ("sha:feature", "feature"),
                                       "steps/Steps.cs": ("sha:steps", "stepdef")})
    product_arm = github.Collected(commit="p" * 40, role="product", files=product_files,
                                   skipped=product_skipped)
    arms = {"test": test_arm, "product": product_arm}

    monkeypatch.setattr(pipeline, "load_env", lambda: {})
    monkeypatch.setattr(pipeline.db, "connect", lambda: real_connect(path))
    monkeypatch.setattr(pipeline.blobs, "text", lambda sha: TEXTS[sha])
    monkeypatch.setattr(pipeline.github, "collect",
                        lambda repo, token, role="product": arms[role])
    monkeypatch.setattr(blobs, "BLOB_DIR", tmp_path / "blobs")

    project = config.Project("specimen", config.Repo("o", "product"),
                             config.Repo("o", "tests"), jira_key="")
    result = pipeline.run_level_fitness(project, "token")
    return result, real_connect(path)


def _text(body: bytes) -> str:
    text = body.decode("utf-8")
    text = re.sub(r"<style>.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(htmllib.unescape(text).split())


# --------------------------------------------------------------------------- AC3: skips always show

def test_a_run_that_skips_five_hundred_sql_files_says_so_though_its_code_read_fine(
        monkeypatch, tmp_path):
    """The review's concern: a skip that breaks no capability used to render nowhere."""
    skipped = (github.Skipped(github.UNSUPPORTED, ".sql",
                              tuple(f"db/migrations/{number:03d}.sql" for number in range(500))),)
    result, conn = _levels_run(monkeypatch, tmp_path,
                               product_files={"src/product.py": ("sha:product", "source")},
                               product_skipped=skipped)
    try:
        run = queries.run_read(conn, result.run_id)
        body, status = app.run_response(conn, result.run_id)
        meta = json.loads(conn.execute("SELECT meta FROM snapshot WHERE id = ?",
                                      (result.snapshot_id,)).fetchone()["meta"])
    finally:
        conn.close()

    page = body.decode("utf-8")
    text = _text(body)
    # The code read fine, so the sentence is the plain aggregate (AC2's other rule).
    assert run["assessment"]["state"] == sources.FOUND
    assert run["assessment"]["sentence"] == ("Assessed: code and test code were consulted and "
                                             "returned 3 files.")
    # AC5: the page prints that sentence, not one of its own.
    assert run["assessment"]["sentence"] in text
    # AC3: the skips are on the page anyway, with kind, count and reason, and the names reachable.
    assert status == 200
    assert "Files this run could not read" in text
    assert "500 files in 1 kind" in text
    assert "<strong>500 .sql</strong> in the product repository" in page
    assert "unsupported kind" in text
    assert "500 .sql files" not in run["assessment"]["sentence"], \
        "a kind no reader here reads is not a loss inside a complete reading's sentence"
    assert "<details><summary>Name them</summary>" in page
    assert "db/migrations/000.sql" in page
    # And the record still holds every skip, so page and store agree.
    assert meta["reads"]["product"]["skipped"][0]["count"] == 500


def test_a_run_that_skipped_nothing_gains_no_section(monkeypatch, tmp_path):
    result, conn = _levels_run(monkeypatch, tmp_path,
                               product_files={"src/product.py": ("sha:product", "source")},
                               product_skipped=())
    try:
        body, _status = app.run_response(conn, result.run_id)
    finally:
        conn.close()

    assert "Files this run could not read" not in _text(body)


def test_a_lost_file_makes_the_sentence_partial_and_the_page_still_lists_it(monkeypatch, tmp_path):
    """AC2 proven through the pipeline, not just the registry: a size-capped file is a loss."""
    skipped = (github.Skipped(github.SIZE_CAP, ".py", ("src/huge.py",)),)
    result, conn = _levels_run(monkeypatch, tmp_path,
                               product_files={"src/product.py": ("sha:product", "source")},
                               product_skipped=skipped)
    try:
        run = queries.run_read(conn, result.run_id)
        body, _status = app.run_response(conn, result.run_id)
    finally:
        conn.close()

    assert run["assessment"]["sentence"] == ("Assessed: code and test code were consulted and "
                                             "returned 3 files (1 .py file unreadable).")
    page = body.decode("utf-8")
    assert "1 .py" in page and "size cap" in page
    assert "src/huge.py" in page


# --------------------------------------------------------------------------- AC5: wording lives once

def test_no_page_module_builds_the_assessment_sentence():
    """AC5: the sentence is constructed in `sources.py`; no template composes its own.

    TESTOPS-49: the walk of the page modules is checked before it is trusted. An empty walk would
    check zero modules and pass, which is a pass about nothing - so it is named and refused.
    """
    web = ROOT / "testops" / "web"
    modules = sorted(web.glob("*.py"))
    assert modules, (
        f"the page-module walk of {web} found no .py files at all; this test would otherwise "
        "check zero modules and pass vacuously"
    )
    for module in modules:
        source = module.read_text(encoding="utf-8")
        assert "consulted and returned" not in source, \
            f"{module.name} builds the assessment sentence; that wording belongs in sources.py"
        assert "other kind" not in source, \
            f"{module.name} writes its own partial-read clause"
    assert "consulted and returned" in (ROOT / "testops" / "sources.py").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- AC6: prose lint

INTERNAL_WORDS = ("capability", "capabilities", "registry", "reading", "readings", "arm", "arms",
                  "observed", "snapshot", "artefact", "collector", "not_assessable")


@pytest.mark.parametrize("sentence", [
    DEMO_SENTENCE,
    "Assessed: code returned 0 items; test code returned 2 items.",
    "Assessed: code and test code were consulted and returned 60 items "
    "(3 .cs files and 1 other kind unreadable).",
])
def test_the_sentence_uses_the_page_s_vocabulary(sentence):
    """AC6: nothing here is a word the reader has to learn."""
    lowered = sentence.lower()
    for word in INTERNAL_WORDS:
        assert word not in lowered, f"{word!r} is this build's word, not the reader's"


def test_the_run_page_states_the_sentence_once(monkeypatch, tmp_path):
    """AC6: no repetition with the surrounding page - the sentence appears exactly once."""
    skipped = (github.Skipped(github.SIZE_CAP, ".py", ("src/huge.py",)),)
    result, conn = _levels_run(monkeypatch, tmp_path,
                               product_files={"src/product.py": ("sha:product", "source")},
                               product_skipped=skipped)
    try:
        run = queries.run_read(conn, result.run_id)
        body, _status = app.run_response(conn, result.run_id)
    finally:
        conn.close()

    sentence = run["assessment"]["sentence"]
    assert _text(body).count(sentence) == 1
