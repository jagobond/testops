"""TESTOPS-40: what a decision covers, and the twin that stops it covering silently.

TESTOPS-37 proved a decision holds and reverses. It left three boundaries of the identity unwritten,
and one of them was wrong:

  * the commit is not part of the identity, so a decision made against one snapshot stays silent
    against another. That is the product meaning - the finding is about the test, not the code - but
    nothing said so, and nothing pinned it (AC1, AC2);
  * a data table under a step is not part of the identity either: the key is the interaction and
    the assertion's words. Defensible for an assertion about a list, and now stated and pinned
    (AC1, AC2);
  * two identical assertions in one scenario were told apart by occurrence alone
    (``interaction|words#n``). Delete the first and the survivor's number shifts, so a decision
    recorded against one silently covered whichever assertion became first. The identity now
    carries the count as well (``#n@total``), so a scenario that gains or loses an identical
    assertion re-keys its occurrences and the decision asks to be judged again (AC3, AC4).

The page states all of it in one sentence (AC1, AC4), and the corpus counts are untouched (AC5).
Every store here is ``tmp_path``; the collector is a fixture. No network, no checkout.
"""
from __future__ import annotations

import html as htmllib
import time

import level_fixtures as fixtures
from testops import cases, pipeline
from testops.analysers import level_fitness
from testops.config import Project, Repo
from testops.store import db as store_db
from testops.web import app
from testops.web import lint as english

# The genuine connect, captured before any test patches the module attribute. A test here edits the
# feature between two runs over one store, so it calls the stub twice and cannot rely on the module
# attribute holding the real function by then.
REAL_CONNECT = store_db.connect

# Runs are identified to the second, so two runs inside one second collide on the run's primary key.
GAP = 1.05

ASSERTION = "the citation is announced with a visible label"

# Two assertions with the same words in one scenario. Both are I4 - an assertion only a browser can
# settle, checked over the HTTP API - so both are `gap` and both raise a case.
TWIN_FEATURE = f"""\
Feature: fact sheet
  Scenario: the citation is announced
    Given the fact sheet endpoint returns a sheet
    Then {ASSERTION}
    And {ASSERTION}
"""

# The same scenario with the first of the two identical assertions deleted. The survivor is now the
# first occurrence, which is exactly the shift that used to happen silently.
TWIN_WITHOUT_FIRST = f"""\
Feature: fact sheet
  Scenario: the citation is announced
    Given the fact sheet endpoint returns a sheet
    Then {ASSERTION}
"""

TWIN_STEPDEF = f"""\
public class FactSheetSteps {{
  [Given("the fact sheet endpoint returns a sheet")]
  public void GivenTheEndpoint() {{
    using var client = new HttpClient();
  }}
  [Then("{ASSERTION}")]
  public void ThenAnnounced() {{}}
}}
"""


def _project(key: str = "fixture", test: str = "tests", product: str = "product") -> Project:
    return Project(key=key, product=Repo("o", product), test=Repo("o", test), jira_key="")


def _repo(monkeypatch, tmp_path, feature: str):
    """Point the real pipeline at one feature, and trace what it writes."""
    path, _connect = fixtures.stub_pipeline(monkeypatch, pipeline, tmp_path, feature=feature,
                                            stepdef=TWIN_STEPDEF)
    statements: list[str] = []

    def opener():
        conn = REAL_CONNECT(path)
        conn.set_trace_callback(statements.append)
        return conn

    monkeypatch.setattr(pipeline.db, "connect", opener)
    return statements, lambda: REAL_CONNECT(path)


def _fingerprints(run) -> list[tuple[str, str]]:
    """(evidence_key, fingerprint) for every actionable claim, in the order the run made them."""
    return [(claim.detail["evidence_key"], pipeline._fingerprint(level_fitness.name, claim))
            for claim in run.claims if claim.verdict in pipeline.RAISES]


def _case_for(conn, fingerprint: str) -> dict | None:
    row = conn.execute("SELECT case_id FROM finding WHERE fingerprint = ?", (fingerprint,)
                       ).fetchone()
    return dict(row) if row else None


def _raised(conn, run_id: str) -> set[str]:
    return {row["fingerprint"] for row in conn.execute(
        "SELECT f.fingerprint FROM finding f JOIN case_ c ON c.id = f.case_id"
        " WHERE c.run_id = ?", (run_id,))}


# ------------------------------------------------------------------ AC1 / AC4: the page's sentence

def test_the_case_page_states_what_a_decision_covers_and_the_page_passes_the_lint(
        tmp_path, monkeypatch):
    """One sentence, on the page a reader decides from, and the page's own prose lint accepts it.

    The sentence is read off the rendered page, not imported from the module: it is the reader's
    words that have to be there. It names every part of the identity - one assertion, one scenario,
    the same interaction and words - the two things it deliberately ignores (commit, test data),
    and both edits that ask again, including the identical-assertion case AC3 fixes (AC4).
    """
    _statements, connect = _repo(monkeypatch, tmp_path, TWIN_FEATURE)
    run = pipeline.run_level_fitness(_project(), token="unused")
    assert len(run.case_ids) == 2, run.stats

    conn = connect()
    try:
        cases.set_state(conn, run.case_ids[0], "resolved", "harry", "judged once")
        page = app.case_page(conn, run.case_ids[0]).decode("utf-8")
        problems = english.lint(page, ASSERTION)
    finally:
        conn.close()

    assert level_fitness.COVER in htmllib.unescape(page)
    for part in ("one assertion in one scenario", "same interaction", "words",
                 "count of identical assertions", "any commit", "any test data",
                 "earlier decision cover again"):
        assert part in htmllib.unescape(page), f"the cover sentence does not say {part!r}"
    assert problems == [], f"the case page fails the prose lint: {problems}"


def test_the_cover_sentence_is_one_sentence():
    """AC1 says one sentence. The page is no place for a paragraph of contract."""
    assert level_fitness.COVER.count(".") == 1
    assert level_fitness.COVER.endswith(".")
    assert len(level_fitness.COVER.split()) <= english.MAX_SENTENCE_WORDS


# ------------------------------------------------------- AC2: the commit and the data are ignored

def test_a_decision_is_keyed_on_the_test_not_the_commit():
    """The same assertion at two different commits is one decision - pinned, not assumed.

    Adding the commit to the fingerprint would re-ask after every deploy, which the ticket forbids
    and the Product Owner would not tolerate. This test fails the moment the commit becomes part of
    the identity.
    """
    one = fixtures.analyse_text(fixtures.FEATURE_TEXT, fixtures.api_bindings(), commit="a" * 40)
    other = fixtures.analyse_text(fixtures.FEATURE_TEXT, fixtures.api_bindings(), commit="9" * 40)

    def by_text(claims):
        return {claim.detail["assertion_text"]: pipeline._fingerprint(level_fitness.name, claim)
                for claim in claims}

    assert set(by_text(one)) == set(by_text(other))
    assert by_text(one) == by_text(other)


def test_a_decision_is_keyed_on_the_words_not_the_test_data():
    """A data table under a step changes the test's inputs, not the assertion's identity (AC2).

    The table is added under the Given and under the assertion itself, so the change is real test
    data in both places a user would edit. The fingerprint must not move; if the data joined the
    key, saving a new row would resurrect every decision about the scenario.
    """
    with_data = fixtures.FEATURE_TEXT.replace(
        "    Given the fact sheet endpoint returns a sheet\n",
        "    Given the fact sheet endpoint returns a sheet\n"
        "      | sheet | source |\n"
        "      | facts | release |\n").replace(
        f"    Then {fixtures.ASSERTING_TEXTS[0]}\n",
        f"    Then {fixtures.ASSERTING_TEXTS[0]}\n"
        "      | label | announced |\n"
        "      | wrap  | yes       |\n")

    plain = fixtures.analyse_fact_sheet(commit=fixtures.COMMIT)
    changed = fixtures.analyse_text(with_data, fixtures.api_bindings(), commit=fixtures.COMMIT)

    assert len(plain) == len(changed) == len(fixtures.ASSERTING_TEXTS)

    def by_text(claims):
        return {claim.detail["assertion_text"]: pipeline._fingerprint(level_fitness.name, claim)
                for claim in claims}

    assert by_text(plain) == by_text(changed), \
        "test data moved the fingerprint; a changed row would resurrect the decision"


# ------------------------------------------------------------- AC3: the twin stops being silent

def test_two_identical_assertions_carry_their_occurrence_and_the_count():
    """The identity says which of the identical assertions it is, and how many there are."""
    claims = fixtures.analyse_text(TWIN_FEATURE, fixtures.api_bindings())
    keys = [claim.detail["evidence_key"] for claim in claims]
    assert keys == [f"I4|{ASSERTION}#1@2", f"I4|{ASSERTION}#2@2"]

    alone = fixtures.analyse_text(TWIN_WITHOUT_FIRST, fixtures.api_bindings())
    assert [claim.detail["evidence_key"] for claim in alone] == [f"I4|{ASSERTION}"]


def test_deleting_the_first_twin_asks_again_about_the_second(tmp_path, monkeypatch):
    """The ticket's own case: decide the second, delete the first, and the reader is asked again.

    Before and after the fix this edit raises a fresh case, because the survivor's key shifts from
    ``#2`` to ``#1``. What this test pins is that the shift is reported: the survivor's fingerprint
    is no longer the one the decision named, nothing suppresses it, and the run raises a case the
    Product Owner has to judge. Silence here - a decision that keeps covering a different
    occurrence - is the failure AC3 names.
    """
    _statements, connect = _repo(monkeypatch, tmp_path, TWIN_FEATURE)
    project = _project()
    first = pipeline.run_level_fitness(project, token="unused")
    assert len(first.case_ids) == 2

    (_first_key, _first_fp), (_second_key, second_fp) = _fingerprints(first)
    conn = connect()
    try:
        case = _case_for(conn, second_fp)
        assert case is not None
        cases.set_state(conn, case["case_id"], "resolved", "harry", "judged the second one")
    finally:
        conn.close()

    _repo(monkeypatch, tmp_path, TWIN_WITHOUT_FIRST)   # the first identical assertion is deleted
    time.sleep(GAP)
    second = pipeline.run_level_fitness(project, token="unused")

    [(key, fp)] = _fingerprints(second)
    assert key == f"I4|{ASSERTION}", "the survivor is now the first occurrence"
    assert fp != second_fp, "the survivor kept the decided fingerprint, so the shift was not seen"
    conn = connect()
    try:
        assert cases.suppressed(conn, fp) is None
        raised = _raised(conn, second.run_id)
        assert _case_for(conn, fp) is not None, "the reader was not asked about the survivor"
        assert second_fp not in raised
    finally:
        conn.close()
    assert len(second.case_ids) == 1


def test_deleting_the_first_twin_never_moves_the_decision_onto_the_survivor(tmp_path, monkeypatch):
    """The silent direction, and the reason the count joined the key.

    Decide the **first** of two identical assertions, then delete it. Before TESTOPS-40 the survivor
    became occurrence ``#1`` - the decided key - so the decision silently covered an assertion that
    was never judged, and the run stayed quiet. The count in the key makes the survivor ``#1@1``
    while the decision names ``#1@2``, so the finding comes back as a case to judge. This test fails
    on the old identity exactly here.
    """
    _statements, connect = _repo(monkeypatch, tmp_path, TWIN_FEATURE)
    project = _project()
    first = pipeline.run_level_fitness(project, token="unused")
    assert len(first.case_ids) == 2

    (first_key, first_fp), _rest = _fingerprints(first)
    assert first_key == f"I4|{ASSERTION}#1@2"      # the first occurrence, decided
    conn = connect()
    try:
        case = _case_for(conn, first_fp)
        assert case is not None
        cases.set_state(conn, case["case_id"], "resolved", "harry", "judged the first one")
        assert cases.suppressed(conn, first_fp) is not None
    finally:
        conn.close()

    _repo(monkeypatch, tmp_path, TWIN_WITHOUT_FIRST)   # exactly the assertion that was decided
    time.sleep(GAP)
    second = pipeline.run_level_fitness(project, token="unused")

    [(key, fp)] = _fingerprints(second)
    assert key == f"I4|{ASSERTION}", "the survivor is now the first occurrence"
    assert fp != first_fp, "the survivor inherited the decided key; the count is not in it"

    conn = connect()
    try:
        assert cases.suppressed(conn, fp) is None, \
            "the decision still covers the survivor; the reader would never be asked again"
        assert _case_for(conn, fp) is not None, "the survivor raised no case: the shift was silent"
    finally:
        conn.close()
    assert len(second.case_ids) == 1, "the decided case did not come back to be judged"


# ---------------------------------------------------------------------------------- AC5: the counts

def test_reformatting_a_scenario_with_twins_keeps_their_occurrence_keys():
    """A guard against the tempting wrong fix: the occurrence key must carry no line.

    A line-based key would resurrect decisions on every reformat, which the ticket forbids, and it
    would also make the twin's key move whenever a comment above it grew. Adding a comment above
    both identical assertions moves every line and must leave the keys, and the fingerprints, alone.
    """
    shifted = TWIN_FEATURE.replace(
        f"    Then {ASSERTION}\n",
        f"    # a comment above both twins shifts every line below it\n    Then {ASSERTION}\n")

    def keys(text):
        return [(claim.detail["evidence_key"], claim.detail["assertion_line"],
                 pipeline._fingerprint(level_fitness.name, claim))
                for claim in fixtures.analyse_text(text, fixtures.api_bindings())]

    before, after = keys(TWIN_FEATURE), keys(shifted)
    assert [key for key, _line, _fp in before] == [key for key, _line, _fp in after]
    assert [fp for _key, _line, fp in before] == [fp for _key, _line, fp in after]
    assert [line for _key, line, _fp in before] != [line for _key, line, _fp in after], \
        "the fixture did not move the assertions"
