"""TESTOPS-47: each analyser states the cover of its own decision, and states identity.

TESTOPS-40 put one sentence on every case page. It was right for the level analyser and wrong twice:
a duplication decision's identity is ``duplicate|scenario-name|signature``, and saying so in the
level analyser's words told that reader a contract they were not entering; and the level sentence
promised that adding or removing an identical assertion "asks you again", which a net-zero twin edit
(delete one, add another) contradicts - the count is unchanged, so the decision holds, and the page
had promised otherwise.

Here the sentence lives on the analyser that raises the claim, beside its verdict and action
(AC1). The level sentence states the identity - scenario, interaction, words, and the count of
identical assertions - rather than an event (AC2). The duplication sentence states its own identity
and what disturbs it (AC3). The level sentence also names the one cover the store cannot prevent:
removing a twin can let an earlier decision cover again (AC4 - stated on the page, not solved in the
key; see the build report for why). A test walks the registry so a new analyser cannot inherit
another's wording by default (AC5).

Every store is ``tmp_path``; the pages in the last tests are rendered from a copy of the checked-in
fixture store, never the fixture itself. No network, no checkout.
"""
from __future__ import annotations

import html as htmllib
import shutil
import time
from pathlib import Path

import level_fixtures as fixtures
from testops import cases, pipeline
from testops.analysers import REGISTERED, cover, duplication, level_fitness
from testops.config import Project, Repo
from testops.store import db as store_db
from testops.web import app
from testops.web import lint as english

REAL_CONNECT = store_db.connect

# Runs are identified to the second, so two runs inside one second collide on the run's primary key.
GAP = 1.05

ASSERTION = "the citation is announced with a visible label"

LONE_FEATURE = f"""\
Feature: fact sheet
  Scenario: the citation is announced
    Given the fact sheet endpoint returns a sheet
    Then {ASSERTION}
"""

TWIN_FEATURE = f"""\
Feature: fact sheet
  Scenario: the citation is announced
    Given the fact sheet endpoint returns a sheet
    Then {ASSERTION}
    And {ASSERTION}
"""

# The net-zero edit from the review: one identical assertion is deleted and another identical one is
# added, so the count is unchanged. The comment is the edit's only trace in the file, which also
# pins that a moved line is not part of the identity.
TWIN_SWAPPED = f"""\
Feature: fact sheet
  # one twin out, one twin in: the count is still two
  Scenario: the citation is announced
    Given the fact sheet endpoint returns a sheet
    Then {ASSERTION}
    And {ASSERTION}
"""

STEPDEF = f"""\
public class FactSheetSteps {{
  [Given("the fact sheet endpoint returns a sheet")]
  public void GivenTheEndpoint() {{
    using var client = new HttpClient();
  }}
  [Then("{ASSERTION}")]
  public void ThenAnnounced() {{}}
}}
"""

FIXTURES = Path(__file__).parent / "fixtures" / "projects_services"


def _project(key: str = "fixture", test: str = "tests", product: str = "product") -> Project:
    return Project(key=key, product=Repo("o", product), test=Repo("o", test), jira_key="")


def _repo(monkeypatch, tmp_path, feature: str):
    path, _connect = fixtures.stub_pipeline(monkeypatch, pipeline, tmp_path, feature=feature,
                                            stepdef=STEPDEF)
    statements: list[str] = []

    def opener():
        conn = REAL_CONNECT(path)
        conn.set_trace_callback(statements.append)
        return conn

    monkeypatch.setattr(pipeline.db, "connect", opener)
    return statements, lambda: REAL_CONNECT(path)


def _fingerprints(run) -> list[tuple[str, str]]:
    return [(claim.detail["evidence_key"], pipeline._fingerprint(level_fitness.name, claim))
            for claim in run.claims if claim.verdict in pipeline.RAISES]


def _case_for(conn, fingerprint: str) -> dict | None:
    row = conn.execute("SELECT case_id FROM finding WHERE fingerprint = ?", (fingerprint,)
                       ).fetchone()
    return dict(row) if row else None


# --------------------------------------------------------------------------- AC5: no default

def test_every_registered_analyser_declares_its_own_cover_sentence():
    """A new analyser must declare a sentence; it cannot inherit one (AC5).

    This is the ticket's point. The bug was a default, so the registry is walked rather than the
    two names being listed here: an analyser added later without a ``COVER`` fails this test, and
    the page's lookup has no fallback to hide it either.
    """
    assert REGISTERED, "no analysers are registered"
    for name, analyser in REGISTERED.items():
        assert getattr(analyser, "COVER", ""), f"{name} declares no cover sentence"
        assert cover(name) == analyser.COVER
        assert analyser.COVER == analyser.COVER.strip()
        assert analyser.COVER.count(".") == 1, f"{name}'s cover sentence is not one sentence"
        assert analyser.COVER.endswith(".")
        assert len(analyser.COVER.split()) <= english.MAX_SENTENCE_WORDS

    wordings = [analyser.COVER for analyser in REGISTERED.values()]
    assert len(set(wordings)) == len(wordings), "two analysers share one cover sentence"


def test_the_page_lookup_has_no_fallback_for_an_analyser_that_declares_nothing(monkeypatch):
    """The page asks the declaring analyser, with no default to inherit (AC5)."""
    class Bare:
        name = "bare"

    monkeypatch.setitem(REGISTERED, "bare", Bare)
    try:
        cover("bare")
    except AttributeError:
        pass
    else:                                        # pragma: no cover - a failure, not a branch
        raise AssertionError("an analyser without COVER inherited a sentence")


# ------------------------------------------------- AC2: the level sentence is an identity claim

def test_the_level_sentence_states_the_count_and_promises_no_event():
    """The contract is the tuple, not a re-ask per edit (AC2)."""
    sentence = level_fitness.COVER
    for part in ("one assertion in one scenario", "same interaction", "words",
                 "count of identical assertions", "any commit", "any test data"):
        assert part in sentence, f"the level cover sentence does not state {part!r}"
    assert "asks you again" not in sentence, \
        "the level sentence promises an event; a net-zero twin edit leaves the count unchanged"


def test_the_net_zero_twin_edit_leaves_the_pages_claim_true(tmp_path, monkeypatch):
    """Delete one identical assertion, add another: the identity is unchanged, so the claim holds.

    The page says the cover is the tuple (scenario, interaction, words, count of identical
    assertions). This edit preserves that tuple exactly - same keys, same fingerprints - so the
    decision continuing to hold is what the page states, not a contradiction of it.
    """
    _statements, connect = _repo(monkeypatch, tmp_path, TWIN_FEATURE)
    project = _project()
    first = pipeline.run_level_fitness(project, token="unused")
    assert [_key for _key, _fp in _fingerprints(first)] == [f"I4|{ASSERTION}#1@2",
                                                            f"I4|{ASSERTION}#2@2"]
    (_first_key, first_fp), (_second_key, second_fp) = _fingerprints(first)

    conn = connect()
    try:
        for fingerprint in (first_fp, second_fp):
            case = _case_for(conn, fingerprint)
            assert case is not None
            cases.set_state(conn, case["case_id"], "resolved", "harry", "judged both twins")
    finally:
        conn.close()

    _repo(monkeypatch, tmp_path, TWIN_SWAPPED)      # one twin out, one twin in: net zero
    time.sleep(GAP)
    second = pipeline.run_level_fitness(project, token="unused")

    assert [(key, fp) for key, fp in _fingerprints(second)] == \
        [(key, fp) for key, fp in _fingerprints(first)], \
        "the net-zero edit moved the identity; the page's count claim would be false"
    conn = connect()
    try:
        # The tuple still names the decided assertions, so both decisions hold - and the page says
        # the cover is that tuple, so the page is true. No case is raised.
        assert cases.suppressed(conn, first_fp) is not None
        assert not second.case_ids
    finally:
        conn.close()


# ---------------------------------------------- AC3: the duplication sentence is its own contract

def _fixture_page(tmp_path, case_id: str) -> str:
    """One case page, rendered from a copy of the checked-in store (never the fixture itself)."""
    target = tmp_path / "store.db"
    shutil.copyfile(FIXTURES / "before_v3.db", target)
    store_db.connect(target).close()
    conn = REAL_CONNECT(target)
    try:
        return app.case_page(conn, case_id).decode("utf-8")
    finally:
        conn.close()


def test_a_duplication_case_shows_the_duplication_sentence_and_not_the_level_one(tmp_path):
    """AC1 and AC3: the declaring analyser's sentence, and it states scenario and signature."""
    page = htmllib.unescape(_fixture_page(tmp_path, "case-page-03"))
    assert duplication.COVER in page, "the duplication case does not show its own contract"
    assert level_fitness.COVER not in page, "the duplication case shows another analyser's contract"
    assert "duplicated scenario" in page
    assert "steps and data tables" in page
    assert "renaming or moving the scenario" in page
    assert "changing the steps in either copy" in page
    problems = english.lint(page)
    assert problems == [], f"the duplication case page fails the prose lint: {problems}"


def test_a_level_case_shows_the_level_sentence_and_not_the_duplication_one(tmp_path):
    """AC1: a level-fitness case shows the level-fitness contract, in both directions."""
    page = htmllib.unescape(_fixture_page(tmp_path, "case-page-01"))
    assert level_fitness.COVER in page
    assert duplication.COVER not in page


# ------------------------------------- AC4: the twin-removal cover is stated, and it is true

def test_the_level_sentence_states_the_cover_a_removed_twin_can_restore():
    """AC4: the reader is told a decision recorded before the twin can cover again."""
    assert "removing an identical assertion" in level_fitness.COVER
    assert "earlier decision cover again" in level_fitness.COVER


def test_a_decision_recorded_before_a_twin_covers_again_after_the_twin_is_removed(tmp_path,
                                                                                 monkeypatch):
    """The hazard the sentence states, exercised end to end so the wording stays true.

    Decide the lone assertion, add a twin (asked again, correctly), delete the twin: the survivor's
    key is the lone key again and the original decision covers it with no new case. The page says
    this, which is why it is honest rather than a defect.
    """
    _statements, connect = _repo(monkeypatch, tmp_path, LONE_FEATURE)
    project = _project()
    first = pipeline.run_level_fitness(project, token="unused")
    assert len(first.case_ids) == 1
    [(lone_key, lone_fp)] = _fingerprints(first)
    assert lone_key == f"I4|{ASSERTION}"

    conn = connect()
    try:
        case = _case_for(conn, lone_fp)
        assert case is not None
        cases.set_state(conn, case["case_id"], "resolved", "harry", "judged the lone assertion")
    finally:
        conn.close()

    _repo(monkeypatch, tmp_path, TWIN_FEATURE)      # the twin is added: asked again
    time.sleep(GAP)
    with_twin = pipeline.run_level_fitness(project, token="unused")
    assert len(with_twin.case_ids) == 2, "adding a twin did not ask again"

    _repo(monkeypatch, tmp_path, LONE_FEATURE)      # the twin is removed: the lone key returns
    time.sleep(GAP)
    without_twin = pipeline.run_level_fitness(project, token="unused")

    conn = connect()
    try:
        assert cases.suppressed(conn, lone_fp) is not None, \
            "the page says the earlier decision can cover again; it did not"
        assert not without_twin.case_ids
    finally:
        conn.close()
