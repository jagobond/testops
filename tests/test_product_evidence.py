"""TESTOPS-72: the product is evidence - is this test repeating work the developer already did?

The analyser has always been handed the product's surfaces and never read one. These tests pin what
changed, in the order the ticket argues it:

  * AC1 - the surfaces are consumed, and every claim records what the product said about it: found
    (with the matched surface, route and word), zero, not_assessable or none. Nothing is silent;
  * AC2 - the flip test: one suite analysed twice, identical except that the product declares the
    route or does not, and the same assertion carries different verdicts. Nothing else differs;
  * AC3 - the precision guards: a generic word never matches, a word that most of the product carries
    never matches, and a claim that does not need a browser is never `repeats_product`;
  * AC4 - a product nobody could read is not a zero, and a browser claim is never judged to repeat
    a product nobody consulted;
  * AC5 - the case page shows the route, the word and the surface's own claim;
  * AC6 - the run page keeps "repeats the product" and "product not consulted" as two counts.

Everything here is in-memory or a throwaway store under ``tmp_path``: no repository checkout, no
network, and no contact with the product store.
"""
from __future__ import annotations

from testops import pipeline
from testops.analysers import level_fitness
from testops.collectors.github import Collected
from testops.config import Project, Repo
from testops.extract import gherkin, stepbindings
from testops.store import db
from testops.surfaces.discover import Discovery, Surface
from testops.web import app

FEATURE_PATH = "features/booking_page.feature"

# A browser suite: the Then is an accessibility claim (I4) and the scenario drives a browser, so the
# verdict is `distinct` until the product is asked.
FEATURE_TEXT = """\
Feature: booking page
  Scenario: a visitor books a room
    Given a visitor opens the booking page
    Then the booking confirmation is announced with an accessible name

  Scenario: the page is served with the room list
    Given a visitor opens the booking page
    Then the page is served with the room list
"""

STEPDEF_TEXT = """\
public sealed class BookingSteps
{
    [Given("a visitor opens the booking page")]
    internal void GivenOpened() => Driver.Page.Open("/booking");

    [Then("the booking confirmation is announced with an accessible name")]
    internal void ThenAnnounced() => Driver.Page.FindElement(By.Id("confirmation")).IsVisible();

    [Then("the page is served with the room list")]
    internal void ThenRoomList() => Driver.Page.FindElement(By.Id("rooms")).IsVisible();
}
"""

ASSERTION = "the booking confirmation is announced with an accessible name"
SERVED = "the page is served with the room list"

ROUTE = "POST /booking"
ROUTE_CLAIM = "create booking"
COMMIT = "b" * 40

# Captured before any test patches ``pipeline.db.connect``: the pipeline and the tests share one
# module object, so reading it inside a patched test would capture the patch itself.
REAL_CONNECT = db.connect


def _bindings() -> list[stepbindings.Binding]:
    """Every step bound to the browser driver, in the feature's own suite."""
    suite = stepbindings.suite_of(FEATURE_PATH)
    return [stepbindings.Binding(pattern=text, verb=verb, cls="BookingSteps",
                                 path="steps/BookingSteps.cs", layer="ui", suite=suite)
            for text, verb in [("a visitor opens the booking page", "Given"),
                               (ASSERTION, "Then"), (SERVED, "Then")]]


def _surface(route: str, claim: str) -> Surface:
    return Surface(id=f"api:{route}@booking/src/BookingController.java:method",
                   layer="api", target=route, claims=[claim],
                   source="booking/src/BookingController.java")


BOOKING = _surface(ROUTE, ROUTE_CLAIM)
ROOM = _surface("GET /room/{id}", "get room")
REPORT = _surface("GET /report", "get room report")

# The product as it is: three routes, one of which is about bookings.
WITH_ROUTE = (BOOKING, ROOM, REPORT)
# The same product without the booking route. This is the only difference in the flip test.
WITHOUT_ROUTE = (ROOM, REPORT)


def _analyse(surfaces, state: str = "found", reason: str = ""):
    feature = gherkin.parse(FEATURE_PATH, FEATURE_TEXT)
    assert feature is not None and len(feature.scenarios) == 2
    claims = level_fitness.analyse(
        features=[feature], bindings=_bindings(), surfaces=list(surfaces),
        uri_for_path=lambda path: f"github:fixture/fixture@deadbeef:{path}",
        budget={"calls": 0, "tokens_in": 0, "tokens_out": 0},
        product_state=state, product_reason=reason)
    return {claim.detail["assertion_text"]: claim for claim in claims}


# --------------------------------------------------------------------------------- AC1: consumed

def test_the_product_record_is_on_every_claim_and_never_silent():
    """AC1: every claim says what the product said, including the claims it is not evidence for."""
    claims = _analyse(WITH_ROUTE)
    assert len(claims) == 2
    for claim in claims.values():
        product = claim.detail["product"]
        assert product["state"] in {"found", "zero", "not_assessable", "none"}, product
        assert product["reason"], (claim.detail["assertion_text"], product)


def test_a_matched_claim_carries_the_surface_the_route_and_the_word():
    """AC1: the evidence a reader needs to check the verdict travels with it."""
    claim = _analyse(WITH_ROUTE)[ASSERTION]
    product = claim.detail["product"]
    assert product["state"] == "found"
    assert product["surface"] == BOOKING.id
    assert product["route"] == ROUTE
    assert product["word"] == "booking"
    assert product["claim"] == ROUTE_CLAIM
    assert product["surfaces"] == 3 and product["shared_with"] == 1
    assert product["needs_browser"] is True


def test_a_claim_the_product_is_not_evidence_about_says_so():
    """AC1: a claim settled without a browser records `none`, not a zero it never looked for."""
    claim = _analyse(WITH_ROUTE)[SERVED]
    assert claim.detail["interaction_code"] == "KP"
    assert claim.detail["product"]["state"] == "none"
    assert "does not need a browser" in claim.detail["product"]["reason"]


def test_a_product_read_with_no_match_records_zero_and_not_silence():
    claim = _analyse(WITHOUT_ROUTE)[ASSERTION]
    product = claim.detail["product"]
    assert product["state"] == "zero"
    assert "none of them shares a meaningful word" in product["reason"]
    assert product["surface"] is None and product["route"] is None and product["word"] is None


# ------------------------------------------------------------------------------- AC2: the flip

def test_the_flip_test_one_suite_two_products_and_one_assertion_that_changes_verdict():
    """AC2, the proof: the same assertion, the same suite, two products - and only the verdict moves.

    The two runs are the same feature text and the same bindings. The only difference is that the
    product declares ``POST /booking`` or does not, so the difference in verdict is traceable to the
    product alone.
    """
    with_route = _analyse(WITH_ROUTE)[ASSERTION]
    without_route = _analyse(WITHOUT_ROUTE)[ASSERTION]

    assert with_route.verdict == "repeats_product"
    assert without_route.verdict == "distinct"

    # Nothing else differs: same assertion, same interaction, same instrument, same span, same
    # coordinates, and the same suppression identity - so a decision recorded against the assertion
    # still covers it after the product changes.
    for field in ("assertion_text", "assertion_path", "assertion_line", "interaction_code",
                  "interaction_label", "instrument", "span", "evidence_key"):
        assert with_route.detail[field] == without_route.detail[field], field
    assert with_route.subject_ref == without_route.subject_ref

    # And the difference is the product's: found in one, zero in the other.
    assert with_route.detail["product"]["state"] == "found"
    assert without_route.detail["product"]["state"] == "zero"


def _pipeline_run(path, surfaces, monkeypatch, *, feature_text=FEATURE_TEXT,
                  product_file="booking/src/BookingController.java",
                  product_text="public class BookingController {}", state="found", reason=""):
    """One real levels run over an in-memory repository and a throwaway store.

    Everything the run reads is the same for both arms of the flip test except the surface reader's
    answer: same feature, same step definitions, same commit, same collector.
    """
    files = {"features/booking_page.feature": ("sha-feature", "feature"),
             "steps/BookingSteps.cs": ("sha-steps", "stepdef"),
             product_file: ("sha-product", "source")}
    texts = {"sha-feature": feature_text, "sha-steps": STEPDEF_TEXT, "sha-product": product_text}
    monkeypatch.setattr(pipeline, "load_env", lambda: {})
    monkeypatch.setattr(pipeline.db, "connect", lambda: REAL_CONNECT(path))
    monkeypatch.setattr(pipeline.blobs, "text", lambda sha: texts[sha])
    monkeypatch.setattr(pipeline.github, "collect",
                        lambda repo, token, role="product": Collected(commit=COMMIT, files=files))
    monkeypatch.setattr(pipeline.surface_discovery, "discover",
                        lambda product_texts: Discovery(tuple(surfaces), state, reason=reason))
    project = Project(key="flip", product=Repo("o", "product"), test=Repo("o", "tests"),
                      jira_key="")
    result = pipeline.run_level_fitness(project, token="unused")
    conn = REAL_CONNECT(path)
    try:
        rows = conn.execute("SELECT * FROM claim ORDER BY id").fetchall()
    finally:
        conn.close()
    return result, {row["assertion_text"]: dict(row) for row in rows}, REAL_CONNECT


def test_the_flip_test_through_the_real_pipeline(tmp_path, monkeypatch):
    """AC2 end to end: two runs over the same suite, differing only in what the product declares.

    The store, the collector and the commit are the same in both runs; the surface reader's answer
    is the only thing that changes, and the two stored claims differ in their verdict and nothing
    else that identifies the assertion.
    """
    with_route, claims_with, _ = _pipeline_run(tmp_path / "with.db", WITH_ROUTE, monkeypatch)
    without_route, claims_without, _ = _pipeline_run(tmp_path / "without.db", WITHOUT_ROUTE,
                                                     monkeypatch)

    assert with_route.stats["repeats_product"] == 1
    assert without_route.stats["repeats_product"] == 0

    first, second = claims_with[ASSERTION], claims_without[ASSERTION]
    assert first["verdict"] == "repeats_product"
    assert second["verdict"] == "distinct"
    for field in ("assertion_path", "assertion_line", "interaction_code", "interaction_label",
                  "analyser", "analyser_version"):
        assert first[field] == second[field], field


# ------------------------------------------------------------------------- AC3: precision guards

def test_a_generic_word_alone_is_never_evidence():
    """AC3: the ticket's own list. "data", "result", "page", "correct" are not a match."""
    generic = Surface(id="api:/data", layer="api", target="GET /data",
                      claims=["list the result page so the data is correct"], source="p.py")
    claim = _analyse((generic, ROOM))[ASSERTION]
    assert claim.detail["product"]["state"] == "zero"
    assert claim.verdict == "distinct"


def test_a_word_most_of_the_product_carries_is_the_products_subject_not_evidence():
    """AC3: a word in more than half the surfaces is what the whole repository is about."""
    everywhere = tuple(_surface(f"GET /booking/{index}", f"get booking {index}")
                       for index in range(3))
    claim = _analyse(everywhere)[ASSERTION]
    assert claim.detail["product"]["state"] == "zero"
    assert claim.verdict == "distinct"

    # The same word in one surface of three is evidence.
    assert _analyse((BOOKING, ROOM, REPORT))[ASSERTION].detail["product"]["state"] == "found"


def test_a_claim_that_does_not_need_a_browser_is_never_a_repeat_however_well_it_matches():
    """AC3: the product cannot make an API-level claim into a repeat of the product."""
    text = "the canon store contains one fact per admitted proposal"
    feature = gherkin.parse("features/canon.feature",
                            f"Feature: canon\n  Scenario: the canon\n    Then {text}\n")
    assert feature is not None
    suite = stepbindings.suite_of("features/canon.feature")
    bindings = [stepbindings.Binding(pattern=text, verb="Then", cls="CanonSteps",
                                     path="steps/CanonSteps.cs", layer="api", suite=suite)]
    surfaces = [Surface(id="api:/canon", layer="api", target="GET /canon",
                        claims=["return the canon, one fact per admitted proposal"], source="c.py"),
                Surface(id="api:/other", layer="api", target="GET /other", claims=["list books"],
                        source="o.py")]
    claims = level_fitness.analyse(
        features=[feature], bindings=bindings, surfaces=surfaces,
        uri_for_path=lambda path: f"github:fixture/fixture@deadbeef:{path}",
        budget={"calls": 0, "tokens_in": 0, "tokens_out": 0},
        product_state="found")
    claim = claims[0]
    assert claim.detail["interaction_code"] == "I1"
    assert claim.detail["product"]["state"] == "none"
    assert claim.verdict == "distinct"


def test_the_match_is_deterministic_and_prefers_the_route_that_names_the_thing():
    """A tie between surfaces is broken by the route, then rarity, then id - never by order."""
    other = _surface("GET /booking", "get booking")
    first = _analyse((BOOKING, other, ROOM, REPORT))[ASSERTION]
    second = _analyse((REPORT, ROOM, other, BOOKING))[ASSERTION]
    assert first.detail["product"]["surface"] == second.detail["product"]["surface"]
    assert first.detail["product"]["word"] == second.detail["product"]["word"]


# ------------------------------------------------- TESTOPS-72 amendment: the verb is a rule

CREATION = "New room will be created"
# Four surfaces so that "room" is in half of them and the common-share guard does not decide this.
GET_ROOM = _surface("GET /room/{id}", "get room")
POST_ROOM = _surface("POST /room", "create room")
BRANDING = _surface("GET /branding", "get branding")
REPORTS = _surface("GET /report", "get room report")
AUTH = _surface("GET /auth", "get token")
CORPUS = (GET_ROOM, POST_ROOM, BRANDING, AUTH)


def _verb_claim(assertion: str, surfaces):
    """One browser claim for ``assertion``, through the analyser, with the product present."""
    path = "features/rooms.feature"
    feature = gherkin.parse(
        path, f"Feature: rooms\n  Scenario: a new room\n"
              f"    Given a visitor opens the room admin page\n    Then {assertion}\n")
    assert feature is not None
    suite = stepbindings.suite_of(path)
    bindings = [stepbindings.Binding(pattern=text, verb=verb, cls="RoomSteps",
                                     path="steps/RoomSteps.cs", layer="ui", suite=suite)
                for text, verb in [("a visitor opens the room admin page", "Given"),
                                   (assertion, "Then")]]
    claims = level_fitness.analyse(
        features=[feature], bindings=bindings, surfaces=list(surfaces),
        uri_for_path=lambda value: f"github:fixture/fixture@deadbeef:{value}",
        budget={"calls": 0, "tokens_in": 0, "tokens_out": 0}, product_state="found")
    return claims[-1]


def test_a_creation_assertion_prefers_the_post_surface_over_a_get_that_shares_the_noun():
    """The review's case: "New room will be created" must not match ``GET /room/{id}``.

    Both surfaces carry the noun "room"; one answers a POST and one a GET. The verb decides before
    the route, the word or the id ever do, and the claim records the assertion's verb and the
    surface's method so a reader can check the rule that fired.
    """
    claim = _verb_claim(CREATION, CORPUS)
    product = claim.detail["product"]
    assert claim.verdict == "repeats_product"
    assert product["route"] == "POST /room"
    assert product["word"] == "room"
    assert product["assertion_verb"] == "create"
    assert product["surface_verb"] == "POST"
    assert product["verb_agrees"] is True
    assert product["near_miss"] is False


def test_where_only_the_get_exists_the_verb_differs_and_no_repeat_is_emitted():
    """The honest refusal: a shared noun is not evidence when the method settles a different act.

    ``GET /room/{id}`` is the only surface about rooms, and the assertion is about creation. No
    ``repeats_product`` is emitted; the claim is ``distinct`` and records the near miss - route,
    assertion verb and surface method - so the evidence is arguable rather than silent.
    """
    claim = _verb_claim(CREATION, (GET_ROOM, BRANDING, REPORTS, AUTH))
    product = claim.detail["product"]
    assert claim.verdict == "distinct"
    assert product["state"] == "zero"
    assert product["near_miss"] is True
    assert product["route"] == "GET /room/{id}"
    assert product["assertion_verb"] == "create"
    assert product["surface_verb"] == "GET"
    assert product["verb_agrees"] is False
    assert "create" in product["reason"] and "GET" in product["reason"]



# --------------------------------------------------------------- AC4: a product nobody could read

def test_an_unreadable_product_is_not_a_zero_and_never_a_repeat():
    """AC4: the product could not be consulted, so the claim says that and keeps its own verdict."""
    reason = ("the surface reader parses Python (.py) and Java (.java) only, and the product "
              "repository holds no file it can read: 142 .kt")
    claim = _analyse((), state="not_assessable", reason=reason)[ASSERTION]
    assert claim.verdict == "distinct"
    assert claim.detail["product"]["state"] == "not_assessable"
    assert "could not be consulted" in claim.detail["product"]["reason"]
    assert "142 .kt" in claim.detail["product"]["reason"]
    assert claim.detail["product"]["surface"] is None


def test_a_run_with_no_product_record_says_nothing_rather_than_zero():
    """AC4's other half: a caller that recorded no product reading is not a clean product."""
    claim = _analyse((), state="")[ASSERTION]
    assert claim.detail["product"]["state"] == "none"
    assert "recorded no product reading" in claim.detail["product"]["reason"]
    assert claim.verdict == "distinct"


# ------------------------------------------------------------------------------ the page (AC5, AC6)

def test_the_case_page_shows_the_route_the_word_and_the_surfaces_own_claim(tmp_path, monkeypatch):
    """AC5: a `repeats_product` verdict with no visible evidence is a failure of the ticket."""
    result, _claims, connect = _pipeline_run(tmp_path / "case.db", WITH_ROUTE, monkeypatch)
    assert result.stats["repeats_product"] == 1, result.stats
    conn = connect(tmp_path / "case.db")
    try:
        page, status = app.case_response(conn, result.case_ids[0])
    finally:
        conn.close()

    assert status == 200
    text = page.decode("utf-8")
    assert ROUTE in text, "the page does not name the route the product declares"
    assert "What the product says" in text
    assert ROUTE_CLAIM in text, "the page does not quote the surface's own claim"
    assert "booking" in text
    assert "Checked, but the product already exposes this" in text
    # The action names the API-level check and still says what a browser is for.
    assert f"call {ROUTE}" in text
    assert "A browser is still needed for what only a person sees" in text


def test_the_run_page_counts_repeats_and_unconsulted_separately(tmp_path, monkeypatch):
    """AC6: two counts, never folded into one another."""
    result, _claims, connect = _pipeline_run(tmp_path / "run.db", WITH_ROUTE, monkeypatch)
    conn = connect(tmp_path / "run.db")
    try:
        page, status = app.run_response(conn, result.run_id)
    finally:
        conn.close()

    assert status == 200
    text = page.decode("utf-8")
    section = text.split("What the product says", 1)[1].split("<h2", 1)[0]
    assert "1 claim repeat work the product already exposes" in section
    assert "could not be consulted" not in section
    assert result.stats["product_not_consulted"] == 0


def test_the_run_page_says_so_when_the_product_could_not_be_consulted(tmp_path, monkeypatch):
    """AC6's other half: a blind product is counted where it belongs, not as a repeat."""
    result, _claims, connect = _pipeline_run(
        tmp_path / "blind.db", (), monkeypatch, product_file="product/src/App.kt",
        product_text="class App {}", state="not_assessable",
        reason="the surface reader parses Python (.py) and Java (.java) only, and the product "
               "repository holds no file it can read: 1 .kt")
    conn = connect(tmp_path / "blind.db")
    try:
        page, status = app.run_response(conn, result.run_id)
    finally:
        conn.close()

    assert result.stats["repeats_product"] == 0
    assert result.stats["product_not_consulted"] == 1
    text = page.decode("utf-8")
    section = text.split("What the product says", 1)[1].split("<h2", 1)[0]
    assert "could not be consulted" in section
    assert "not counted among the repeats" in section
    assert "No claim in this run repeats work the product already exposes." in text
