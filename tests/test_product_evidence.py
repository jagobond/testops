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
    Then the booking confirmation is shown with an accessible name

  Scenario: the page is served with the room list
    Given a visitor opens the booking page
    Then the page is served with the room list
"""

STEPDEF_TEXT = """\
public sealed class BookingSteps
{
    [Given("a visitor opens the booking page")]
    internal void GivenOpened() => Driver.Page.Open("/booking");

    [Then("the booking confirmation is shown with an accessible name")]
    internal void ThenAnnounced() => Driver.Page.FindElement(By.Id("confirmation")).IsVisible();

    [Then("the page is served with the room list")]
    internal void ThenRoomList() => Driver.Page.FindElement(By.Id("rooms")).IsVisible();
}
"""

ASSERTION = "the booking confirmation is shown with an accessible name"
SERVED = "the page is served with the room list"

ROUTE = "GET /booking"
ROUTE_CLAIM = "show booking"
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
    """AC1, TESTOPS-79 AC7: a KP claim the run drove a browser for is assessed, not exempt.

    ``the page is served with the room list`` is settled by the page the server sends. Before
    TESTOPS-79 it recorded the product as irrelevant and a whole class of browser claims never
    reached the rule; now the product is read for it. Its verdict stays ``review`` - the browser was
    the waste - and the product record says what the product's surfaces had to say (here ``zero``:
    the one shared word is carried by two of three surfaces, so it is the product's subject).
    """
    claim = _analyse(WITH_ROUTE)[SERVED]
    assert claim.detail["interaction_code"] == "KP"
    product = claim.detail["product"]
    assert product["state"] == "zero"
    assert product["needs_browser"] is False
    assert "shares a meaningful word" in product["reason"]
    assert claim.verdict == "review"


def test_a_kp_claim_with_no_browser_says_why_the_product_is_not_evidence():
    """AC7's other half: where no browser ran there is nothing to repeat, and the record says so.

    The same KP claim in an API suite is ``distinct`` - no browser was spent - and the product
    record names that as the reason it was not asked, rather than the old blanket "does not need a
    browser" that also covered browser runs.
    """
    text = "the page is served with the room list"
    feature = gherkin.parse("features/served.feature",
                            f"Feature: served\n  Scenario: served\n    Then {text}\n")
    assert feature is not None
    suite = stepbindings.suite_of("features/served.feature")
    bindings = [stepbindings.Binding(pattern=text, verb="Then", cls="ServedSteps",
                                     path="steps/ServedSteps.cs", layer="api", suite=suite)]
    claims = level_fitness.analyse(
        features=[feature], bindings=bindings, surfaces=list(WITH_ROUTE),
        uri_for_path=lambda path: f"github:fixture/fixture@deadbeef:{path}",
        budget={"calls": 0, "tokens_in": 0, "tokens_out": 0}, product_state="found")
    claim = claims[0]
    assert claim.detail["interaction_code"] == "KP"
    assert claim.detail["product"]["state"] == "none"
    assert "did not drive a browser" in claim.detail["product"]["reason"]
    assert claim.verdict == "distinct"


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
    product declares ``GET /booking`` or does not, so the difference in verdict is traceable to the
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
                  stepdef_text=STEPDEF_TEXT,
                  product_file="booking/src/BookingController.java",
                  product_text="public class BookingController {}", state="found", reason=""):
    """One real levels run over an in-memory repository and a throwaway store.

    Everything the run reads is the same for both arms of the flip test except the surface reader's
    answer: same feature, same step definitions, same commit, same collector.
    """
    files = {"features/booking_page.feature": ("sha-feature", "feature"),
             "steps/BookingSteps.cs": ("sha-steps", "stepdef"),
             product_file: ("sha-product", "source")}
    texts = {"sha-feature": feature_text, "sha-steps": stepdef_text, "sha-product": product_text}
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
    assert result.stats["product_not_consulted"] == 2
    text = page.decode("utf-8")
    section = text.split("What the product says", 1)[1].split("<h2", 1)[0]
    assert "could not be consulted" in section
    assert "not counted among the repeats" in section
    assert "No claim in this run repeats work the product already exposes." in text


# ------------------------------------------------------------ TESTOPS-78: the two remaining holes

# The explicit intent table, pinned exactly (AC2). A form that is not here is not an intent, and a
# form added here is a deliberate change to how an assertion is read - which is why the whole table
# is written out rather than sampled.
EXPECTED_INTENT_FORMS = {
    "create": ("create", frozenset({"POST"})),
    "creates": ("create", frozenset({"POST"})),
    "created": ("create", frozenset({"POST"})),
    "creating": ("create", frozenset({"POST"})),
    "add": ("add", frozenset({"POST"})),
    "adds": ("add", frozenset({"POST"})),
    "added": ("add", frozenset({"POST"})),
    "adding": ("add", frozenset({"POST"})),
    "new": ("new", frozenset({"POST"})),
    "read": ("read", frozenset({"GET"})),
    "reads": ("read", frozenset({"GET"})),
    "reading": ("read", frozenset({"GET"})),
    "get": ("get", frozenset({"GET"})),
    "gets": ("get", frozenset({"GET"})),
    "getting": ("get", frozenset({"GET"})),
    "show": ("show", frozenset({"GET"})),
    "shows": ("show", frozenset({"GET"})),
    "showed": ("show", frozenset({"GET"})),
    "shown": ("show", frozenset({"GET"})),
    "showing": ("show", frozenset({"GET"})),
    "display": ("display", frozenset({"GET"})),
    "displays": ("display", frozenset({"GET"})),
    "displayed": ("display", frozenset({"GET"})),
    "displaying": ("display", frozenset({"GET"})),
    "list": ("list", frozenset({"GET"})),
    "lists": ("list", frozenset({"GET"})),
    "listed": ("list", frozenset({"GET"})),
    "listing": ("list", frozenset({"GET"})),
    "view": ("view", frozenset({"GET"})),
    "views": ("view", frozenset({"GET"})),
    "viewed": ("view", frozenset({"GET"})),
    "viewing": ("view", frozenset({"GET"})),
    "see": ("see", frozenset({"GET"})),
    "sees": ("see", frozenset({"GET"})),
    "saw": ("see", frozenset({"GET"})),
    "seen": ("see", frozenset({"GET"})),
    "seeing": ("see", frozenset({"GET"})),
    "fetch": ("fetch", frozenset({"GET"})),
    "fetches": ("fetch", frozenset({"GET"})),
    "fetched": ("fetch", frozenset({"GET"})),
    "fetching": ("fetch", frozenset({"GET"})),
    "retrieve": ("retrieve", frozenset({"GET"})),
    "retrieves": ("retrieve", frozenset({"GET"})),
    "retrieved": ("retrieve", frozenset({"GET"})),
    "retrieving": ("retrieve", frozenset({"GET"})),
    "update": ("update", frozenset({"PUT", "PATCH"})),
    "updates": ("update", frozenset({"PUT", "PATCH"})),
    "updated": ("update", frozenset({"PUT", "PATCH"})),
    "updating": ("update", frozenset({"PUT", "PATCH"})),
    "edit": ("edit", frozenset({"PUT", "PATCH"})),
    "edits": ("edit", frozenset({"PUT", "PATCH"})),
    "edited": ("edit", frozenset({"PUT", "PATCH"})),
    "editing": ("edit", frozenset({"PUT", "PATCH"})),
    "change": ("change", frozenset({"PUT", "PATCH"})),
    "changes": ("change", frozenset({"PUT", "PATCH"})),
    "changed": ("change", frozenset({"PUT", "PATCH"})),
    "changing": ("change", frozenset({"PUT", "PATCH"})),
    "modify": ("modify", frozenset({"PUT", "PATCH"})),
    "modifies": ("modify", frozenset({"PUT", "PATCH"})),
    "modified": ("modify", frozenset({"PUT", "PATCH"})),
    "modifying": ("modify", frozenset({"PUT", "PATCH"})),
    "delete": ("delete", frozenset({"DELETE"})),
    "deletes": ("delete", frozenset({"DELETE"})),
    "deleted": ("delete", frozenset({"DELETE"})),
    "deleting": ("delete", frozenset({"DELETE"})),
    "remove": ("remove", frozenset({"DELETE"})),
    "removes": ("remove", frozenset({"DELETE"})),
    "removed": ("remove", frozenset({"DELETE"})),
    "removing": ("remove", frozenset({"DELETE"})),
    "destroy": ("destroy", frozenset({"DELETE"})),
    "destroys": ("destroy", frozenset({"DELETE"})),
    "destroyed": ("destroy", frozenset({"DELETE"})),
    "destroying": ("destroy", frozenset({"DELETE"})),
}


def test_the_intent_table_is_an_explicit_list_and_holds_no_generated_form():
    """AC2: the table's contents are pinned, and a form nobody writes does not exist."""
    assert level_fitness._INTENT_FORMS == EXPECTED_INTENT_FORMS
    for absent in ("getted", "readed", "seed", "newed", "seesed", "listedting"):
        assert absent not in level_fitness._INTENT_FORMS, absent


GET_BOOKING = _surface("GET /booking/{id}", "get booking")
DELETE_BOOKING = _surface("DELETE /booking/{id}", "delete booking")
# Six surfaces so the shared noun is not the noun the whole product is about (the common-share
# guard), exactly as the reviewer's probe had.
BOOKING_CORPUS = (GET_BOOKING, DELETE_BOOKING, BRANDING, AUTH, GET_ROOM, REPORTS)

PRESENT = "booking details present"


def test_a_verb_less_assertion_shares_a_noun_and_is_refused_not_counted():
    """AC1, the reviewer's own probe: presence is not an act, and a bare noun is not evidence.

    ``booking details present`` matched ``DELETE /booking/{id}`` on the bare noun over the
    ``GET /booking/{id}`` beside it and was counted as a repeat. It must not be: no recognised act
    means nothing the product does can agree with it, so the claim stays ``distinct`` and the record
    says why in words a reader can act on.
    """
    claim = _verb_claim(PRESENT, BOOKING_CORPUS)
    product = claim.detail["product"]
    assert claim.verdict == "distinct"
    assert product["state"] == "zero"
    assert product["near_miss"] is True
    assert product["near_miss_kind"] == "no_intent"
    assert product["assertion_verb"] == ""
    assert product["verb_agrees"] is False
    # The nearest surface is the DELETE the review saw; the route is recorded, not hidden.
    assert product["route"] == "DELETE /booking/{id}"
    assert product["word"] == "booking"
    assert "no act this rule recognises" in product["reason"]
    assert "not counted as a repeat" in product["reason"]


def test_precision_is_unchanged_on_the_round_2_fixtures():
    """AC5: every repeat the amendment's fixtures pinned still fires, and the verb-less ones refuse.

    ``New room will be created`` against a POST is a repeat; against a GET-only product it is a near
    miss; the two-verb sentence still prefers the mutation. Nothing here is new behaviour - the test
    pins that the new refusal did not buy its honesty by losing a true positive.
    """
    assert _verb_claim(CREATION, CORPUS).verdict == "repeats_product"
    assert _verb_claim("A room is created and then the room is displayed",
                       CORPUS).verdict == "repeats_product"
    assert _verb_claim(CREATION, (GET_ROOM, BRANDING, REPORTS, AUTH)).verdict == "distinct"
    assert _verb_claim(PRESENT, BOOKING_CORPUS).verdict == "distinct"


# ------------------------------------------------------- AC3 and AC4: the refusal is on the page

ROOM_SHOWN = "the room is shown with an accessible name"
CASE_FEATURE_TEXT = f"""\
Feature: room admin
  Scenario: a new room
    Given a visitor opens the room admin page
    Then {ROOM_SHOWN}
    And {PRESENT}
"""

CASE_STEPDEF_TEXT = f"""\
public sealed class RoomSteps
{{
    [Given("a visitor opens the room admin page")]
    internal void GivenPage() => Driver.Page.Open("/rooms");

    [Then("{ROOM_SHOWN}")]
    internal void ThenShown() => Driver.Page.FindElement(By.Id("room")).IsVisible();

    [Then("{PRESENT}")]
    internal void ThenDetails() => Driver.Page.FindElement(By.Id("details")).IsVisible();
}}
"""

# One repeat and one near miss in one scenario: the case page for the repeat is the page a reader is
# already on when the sibling's refusal matters.
CASE_SURFACES = (GET_ROOM, _surface("GET /booking", "show booking"), GET_BOOKING,
                 DELETE_BOOKING, _surface("GET /report", "get report"), AUTH)


def test_the_run_page_counts_the_claims_it_refused_separately(tmp_path, monkeypatch):
    """AC3: one line, its own count, split by why - never folded into repeats or blind spots."""
    result, _claims, connect = _pipeline_run(
        tmp_path / "near.db", CASE_SURFACES, monkeypatch, feature_text=CASE_FEATURE_TEXT,
        stepdef_text=CASE_STEPDEF_TEXT)
    assert result.stats["repeats_product"] == 1, result.stats
    assert result.stats["product_near_miss"] == 1, result.stats
    conn = connect(tmp_path / "near.db")
    try:
        page, status = app.run_response(conn, result.run_id)
    finally:
        conn.close()

    assert status == 200
    text = page.decode("utf-8")
    section = text.split("What the product says", 1)[1].split("<h2", 1)[0]
    assert (("1 claim shares a noun with a product route but was not counted "
             "(verb differs 0 / no intent 1 / display copy 0)") in section)
    assert "could not be consulted" not in section


def test_a_near_miss_is_reachable_from_its_run_page_and_from_its_scenarios_case_page(
        tmp_path, monkeypatch):
    """AC4: recorded and invisible is not acceptable - the sentence is on a page, and linked.

    The near-miss claim is ``distinct``, so it raises no case. Its own sentence must be on the run
    page, and where its scenario raised a finding, the run page must link to that case page and the
    case page must show the same sentence: route, shared word, why it is not a repeat.
    """
    result, _claims, connect = _pipeline_run(
        tmp_path / "shown.db", CASE_SURFACES, monkeypatch, feature_text=CASE_FEATURE_TEXT,
        stepdef_text=CASE_STEPDEF_TEXT)
    assert result.case_ids, result.stats
    case_id = result.case_ids[0]
    conn = connect(tmp_path / "shown.db")
    try:
        run_page, _ = app.run_response(conn, result.run_id)
        case_page, case_status = app.case_response(conn, case_id)
    finally:
        conn.close()

    run_text = run_page.decode("utf-8")
    assert "What the product refused" in run_text
    assert PRESENT in run_text
    assert "DELETE /booking/{id}" in run_text
    assert "no act this rule recognises" in run_text
    assert f'/case/{case_id}#near-miss-claim-' in run_text

    assert case_status == 200
    case_text = case_page.decode("utf-8")
    assert "What the product refused" in case_text
    assert PRESENT in case_text
    assert "DELETE /booking/{id}" in case_text
    assert "no act this rule recognises" in case_text


# ------------------------------------------------- TESTOPS-79: display copy is not the subject

# The first real corpus run's exact sentences. Two are the contact feature's banner assertions;
# the third is the one claim of the original nine that is defensible.
BANNER = "Visitor will get Booking Successful! message"
CONTACT = ("Visitor 'Jhon Doe' will get Thanks for getting in touch message regarding "
           "subject 'Special Accommodation'")
ROOM_CREATION = ("New '<room_type>' type '<accessibility>' room '<room_name>' priced at "
                 "'<room_price>' GBP with '<features>' will be created")

MESSAGE = _surface("GET /{id:[0-9]*}", "get message")
# Six surfaces, so "message" in one of them is specific rather than the product's subject.
DISPLAY_CORPUS = (MESSAGE, GET_ROOM, POST_ROOM, BRANDING, AUTH, REPORTS)


def test_a_word_that_occurs_only_in_display_copy_is_not_a_candidate_shared_word():
    """AC1, the real corpus: `message` is part of a banner, not an entity the product publishes.

    The room-creation assertion beside it is a repeat on the same corpus, so the rule cannot be
    satisfied by refusing everything - the difference is the word, not the product.
    """
    claim = _verb_claim(BANNER, DISPLAY_CORPUS)
    product = claim.detail["product"]
    assert claim.verdict == "distinct"
    assert product["state"] == "zero"
    assert product["near_miss"] is True
    assert product["near_miss_kind"] == "display_copy"
    assert product["route"] == "GET /{id:[0-9]*}"
    assert product["word"] == "message"
    assert product["display_text"] == "Booking Successful! message"

    # The contact feature's sibling, same shape.
    contact = _verb_claim(CONTACT, DISPLAY_CORPUS).detail["product"]
    assert contact["state"] == "zero"
    assert contact["near_miss_kind"] == "display_copy"
    assert contact["word"] == "message"
    assert contact["display_text"] == "Thanks for getting in touch message"

    # AC2: the defensible case survives, on the same surfaces.
    room = _verb_claim(ROOM_CREATION, DISPLAY_CORPUS)
    assert room.verdict == "repeats_product"
    assert room.detail["product"]["route"] == "POST /room"
    assert room.detail["product"]["word"] == "room"
    assert room.detail["product"]["display_copy"] is False


def test_the_refusal_names_the_word_and_the_copy_it_sits_in():
    """AC3: the reason is a sentence a reader can act on, and it quotes the display copy."""
    product = _verb_claim(BANNER, DISPLAY_CORPUS).detail["product"]
    reason = product["reason"]
    assert '"message"' in reason
    assert "display copy" in reason
    assert "Booking Successful! message" in reason
    assert "not counted as a repeat" in reason
    assert "GET /{id:[0-9]*}" in reason

    rendered = app.near_miss_sentence(product)
    assert "\u201cmessage\u201d" in rendered
    assert "display copy" in rendered
    assert "Booking Successful! message" in rendered


def test_a_quoted_placeholder_is_a_slot_not_display_copy():
    """AC2's pin: `'<room_name>'` names a parameter, so the words in it stay candidates.

    A rule that treated every quoted run as copy would refuse this assertion on `room`, which is
    the true positive the ticket exists to protect.
    """
    assert level_fitness._display_copy(ROOM_CREATION) == {}
    # A slot with no unquoted occurrence is still a candidate word.
    slot_only = "New '<room_name>' will be created"
    assert level_fitness._display_copy(slot_only) == {}
    claim = _verb_claim(slot_only, DISPLAY_CORPUS)
    assert claim.verdict == "repeats_product"
    assert claim.detail["product"]["word"] == "room"


def test_quoted_copy_is_not_the_assertions_intent():
    """AC6: `Visitor sees "Booking created"` records `see`, never `create` from the quoted copy."""
    assertion = 'Visitor sees the booking with "Booking created"'
    product = _verb_claim(assertion, BOOKING_CORPUS).detail["product"]
    assert product["assertion_verb"] == "see"
    assert product["surface_verb"] == "GET"
    # The quoted `create` did not outrank the sentence's own verb and hand it a POST route.
    assert product["route"] == "GET /booking/{id}"
    # Read without the rule, the quoted copy *would* supply the intent - which is the fault.
    assert level_fitness._assertion_intent(assertion) == ("create", frozenset({"POST"}))

    # Both directions: with only a POST surface the claim is refused, and the refusal still
    # records the sentence's verb. The quoted string cannot make the POST route agree.
    post_booking = _surface("POST /booking", "create booking")
    post_only = (post_booking, BRANDING, AUTH, GET_ROOM, REPORTS)
    refused = _verb_claim(assertion, post_only).detail["product"]
    assert refused["assertion_verb"] == "see"
    assert refused["route"] == "POST /booking"
    assert refused["state"] == "zero"
    assert refused["verb_agrees"] is False


# -------------------------------------------- TESTOPS-82: quoting is not a signal of copy

# The reviewer's five probes, verbatim. Four are assertions a person would trust - they quote their
# subject to be unambiguous - and the fifth is the one that used to accuse on the incidental word
# `list` after `room` had been withheld.
QUOTED_SHOWN = 'the "booking" record is shown'
QUOTED_CREATED = 'a "booking" is created'
QUOTED_EXISTS = 'the "booking" exists'
QUOTED_SEARCH = 'search for "room" returns results'
QUOTED_LIST = 'verify the "room" type appears in the list'

POST_BOOKING = _surface("POST /booking", "create booking")
# Six surfaces: "booking" in three of them is exactly half, so the common-share guard cannot be what
# refuses the creation probe - only the act can.
QUOTED_BOOKING_CORPUS = (GET_BOOKING, DELETE_BOOKING, POST_BOOKING, BRANDING, AUTH, REPORTS)
HEALTH = _surface("GET /health", "get health")
PING = _surface("GET /ping", "ping")
DOCS = _surface("GET /docs", "read docs")
ROOM_CORPUS = (GET_ROOM, POST_ROOM, BRANDING, AUTH, REPORTS, HEALTH)
# `list` is a route word here, and `room` is carried by three of eight surfaces. Without the
# quoted-subject preference `list` wins on rarity; with it, `room` is the word the record uses.
ROOM_LIST = _surface("GET /list", "list the room")
LIST_CORPUS = (ROOM_LIST, GET_ROOM, BRANDING, AUTH, REPORTS, HEALTH, PING, DOCS)


def test_a_single_quoted_word_is_the_subject_and_not_display_copy():
    """AC1: all five probes, each verdict stated, on corpora where the act can be judged.

    A single quoted word with no second mark stays a candidate shared word. ``the "booking" record
    is shown`` is a repeat on its merits - the verb ``shown`` and a GET route agree - and
    ``a "booking" is created`` is a repeat because ``created`` agrees with POST. The two sentences
    that name no act the rule knows are refused on the act, not on the quoting.
    """
    assert level_fitness._display_copy(QUOTED_SHOWN) == {}
    assert level_fitness._display_copy(QUOTED_CREATED) == {}
    assert level_fitness._display_copy(QUOTED_EXISTS) == {}
    assert level_fitness._display_copy(QUOTED_SEARCH) == {}
    assert level_fitness._display_copy(QUOTED_LIST) == {}

    # 1. the "booking" record is shown -> show agrees with GET /booking/{id}. The word `record`
    #    places the claim as stored data (I1), so the claim is `review`; what the ticket turns on
    #    is that the rule no longer refuses `booking` as copy - the match is a real one.
    shown = _verb_claim(QUOTED_SHOWN, QUOTED_BOOKING_CORPUS)
    assert shown.verdict == "review"
    assert shown.detail["product"]["word"] is None
    match = level_fitness.product_match(QUOTED_SHOWN, QUOTED_BOOKING_CORPUS)
    assert match is not None
    assert match["word"] == "booking"
    assert match["route"] == "GET /booking/{id}"
    assert match["display_copy"] is False
    assert match["verb_agrees"] is True

    # 2. a "booking" is created -> creation agrees with POST /booking
    created = _verb_claim(QUOTED_CREATED, QUOTED_BOOKING_CORPUS)
    assert created.verdict == "repeats_product"
    assert created.detail["product"]["word"] == "booking"
    assert created.detail["product"]["route"] == "POST /booking"

    # 3. the "booking" exists -> no recognised act, so distinct; the noun is still the subject
    exists = _verb_claim(QUOTED_EXISTS, QUOTED_BOOKING_CORPUS)
    assert exists.verdict == "distinct"
    assert exists.detail["product"]["near_miss_kind"] == "no_intent"
    assert exists.detail["product"]["word"] == "booking"
    assert exists.detail["product"]["word_quoted"] is True

    # 4. search for "room" returns results -> no recognised act; `room` is the shared word
    search = _verb_claim(QUOTED_SEARCH, ROOM_CORPUS)
    assert search.verdict == "distinct"
    assert search.detail["product"]["near_miss_kind"] == "no_intent"
    assert search.detail["product"]["word"] == "room"

    # 5. verify the "room" type appears in the list -> on `room`, never on `list`
    listed = _verb_claim(QUOTED_LIST, LIST_CORPUS)
    assert listed.detail["product"]["word"] == "room"
    assert listed.detail["product"]["route"] == "GET /room/{id}"


def test_a_quoted_noun_outranks_an_incidental_word_outside_the_quotes():
    """AC2: the strongest shared noun in the quotes is the one the record uses.

    ``list`` sits in a route and is rarer than ``room``, so it wins the old ranking. It is not what
    the assertion is about: the quoted ``room`` is. The record must name ``room`` - a weaker word
    outside the run may never justify the match.
    """
    product = _verb_claim(QUOTED_LIST, LIST_CORPUS).detail["product"]
    assert product["word"] == "room"
    assert product["word_quoted"] is True
    assert product["route"] == "GET /room/{id}"
    # The refusal is never justified with the incidental word.
    assert '"list"' not in product["reason"]
    assert level_fitness._quoted_subject_words(QUOTED_LIST) == frozenset({"room"})


def test_a_quoted_run_is_copy_only_when_a_second_mark_says_so():
    """AC1: the three second marks, and the single quoted word that carries none of them."""
    # (a) a multi-word quoted run is copy.
    assert level_fitness._display_copy('Visitor sees "Booking created"') == {
        "booking": "Booking created", "created": "Booking created"}
    # (b) a display verb immediately in front of the quotes makes even one word copy.
    for verb in ("shows", "sees", "displays", "reads", "gets", "receives", "says"):
        _, copy = next(iter(level_fitness._display_copy(f'Visitor {verb} "Booking"').items()))
        assert copy == "Booking", verb
    # (c) banner punctuation inside the run is copy, whatever stands in front of it.
    assert level_fitness._display_copy('Visitor checks the "Success!" banner') == {
        "success": "Success!"}
    # No second mark: the quotes alone are not copy.
    assert level_fitness._display_copy(QUOTED_SHOWN) == {}
    assert level_fitness._display_copy('the "booking" exists') == {}


def test_the_refusal_distinguishes_copy_from_a_quoted_subject_refused_for_another_reason():
    """AC4: the two near misses say different things, and neither calls the subject incidental."""
    copy = _verb_claim(BANNER, DISPLAY_CORPUS).detail["product"]
    assert copy["near_miss_kind"] == "display_copy"
    assert "text a person is shown" in copy["reason"]
    assert "rather than the subject of the check" in copy["reason"]

    subject = _verb_claim(QUOTED_EXISTS, QUOTED_BOOKING_CORPUS).detail["product"]
    assert subject["near_miss_kind"] == "no_intent"
    assert "quoting is not why it is refused" in subject["reason"]
    assert "rather than the subject of the check" not in subject["reason"]
    assert "text a person is shown" not in subject["reason"]
    assert "rather than the subject of the check" not in app.near_miss_sentence(subject)


# ------------------------- TESTOPS-82 amendment: the review's attacks, refused in both directions

GET_MESSAGE = _surface("GET /message/{id}", "get message")
POST_MESSAGE = _surface("POST /message", "create message")
MESSAGE_CORPUS = (GET_MESSAGE, POST_MESSAGE, GET_BOOKING, POST_BOOKING, BRANDING, AUTH)
# `message` is a product word here, so a quoted word in front of it is that noun's copy.
QUOTED_MESSAGE_PANEL = 'the "booking" is shown in the "message" panel'


def test_a_quoted_word_modifying_a_product_noun_is_copy_not_the_subject():
    """Concern 1, forward: `a "Welcome" message is created` accuses POST /message - it must not.

    The review found the one-way gate: nothing after the quote was ever read, so a caption in front
    of the product's own noun was taken for the assertion's subject and the intent table then
    accused. A quoted word followed by a noun the product itself names modifies that noun: it is
    copy or a value, and the claim can never be a repeat.
    """
    product = _verb_claim('a "Welcome" message is created', MESSAGE_CORPUS).detail["product"]
    assert product["near_miss_kind"] == "quoted_copy"
    assert product["verb_agrees"] is True  # the act really does agree - and is still not evidence
    assert product["word"] == "message"
    assert product["display_text"] == "Welcome"
    assert "text a person is shown" in product["reason"]
    assert "not counted as a repeat" in product["reason"]
    assert "display copy" in app.near_miss_sentence(product)

    # A value the product hands back is the same case: `contains` takes the quoted text as its
    # object, so nothing in the sentence names the quoted word as the thing the check is about.
    contained = level_fitness._product_record(
        "I4", 'the response contains "Booking" once it is created', QUOTED_BOOKING_CORPUS,
        level_fitness.PRODUCT_FOUND, "")
    assert contained["near_miss_kind"] == "display_copy"
    assert contained["state"] == "zero"
    assert level_fitness._display_copy('the response contains "Booking" once it is created',
                                       frozenset({"booking", "message"})) == {"booking": "Booking"}


def test_a_verb_after_the_quotes_means_the_quotes_named_the_subject():
    """Concern 1, backward: an intent or existence verb after the run keeps it the subject.

    Both directions are pinned, because a rule that only ever tightened would refuse the assertions
    the ticket exists to protect.
    """
    created = _verb_claim('a "booking" is created', QUOTED_BOOKING_CORPUS)
    assert created.verdict == "repeats_product"
    assert created.detail["product"]["word"] == "booking"
    assert created.detail["product"]["route"] == "POST /booking"
    assert created.detail["product"]["quoted_copy"] == []

    shown = level_fitness.product_match('the "booking" is shown', QUOTED_BOOKING_CORPUS)
    assert shown is not None
    assert shown["word"] == "booking" and shown["display_copy"] is False
    exists = level_fitness.product_match('the "booking" exists', QUOTED_BOOKING_CORPUS)
    assert exists is not None
    assert exists["word"] == "booking" and exists["display_copy"] is False
    assert exists["word_quoted"] is True


def test_punctuation_inside_a_one_word_run_is_the_banner_mark_it_is():
    """Concern 2: `"Saved."` and `"Booking."` are captions, not entities, and go unnoticed today.

    A full stop, a comma or a bracket inside the run is the typography of text a person reads; an
    entity is never quoted with its own punctuation.
    """
    for text, word in (('the "Saved." banner', "saved"),
                       ('the "Booking." dialog appears', "booking"),
                       ('the "Booking," panel', "booking"),
                       ('the "Booking)" label', "booking"),
                       ('the "Booking\u2026" note', "booking"),
                       ('the "Booking..." note', "booking")):
        assert list(level_fitness._display_copy(text)) == [word], text

    # A quoted entity with no punctuation is still the subject.
    assert level_fitness._display_copy('the "booking" is shown') == {}
    # And a one-word run that ends in a bracket is a caption even where a route shares the word.
    refused = _verb_claim('the "Booking." dialog appears', QUOTED_BOOKING_CORPUS).detail["product"]
    assert refused["near_miss_kind"] == "display_copy"
    assert refused["word"] == "booking"


def test_with_two_quoted_runs_the_record_names_the_sentences_subject():
    """Concern 3: the rarest quoted word is not the subject, and it must not accuse.

    `the "booking" is shown in the "message" panel` used to record a repeat on GET /message because
    `message` was rarer than `booking`. The sentence is about the booking; the panel is incidental.
    """
    product = _verb_claim(QUOTED_MESSAGE_PANEL, QUOTED_BOOKING_CORPUS + (GET_MESSAGE,)).detail["product"]
    assert product["word"] == "booking"
    assert product["route"] == "GET /booking/{id}"
    assert product["word_quoted"] is True
    assert "message" not in (product["word"] or "")

    # When no verb governs either run, the first run is the subject.
    listed = level_fitness.product_match('search for "room" in the "list" view', LIST_CORPUS)
    assert listed is not None
    assert listed["word"] == "room"
    assert listed["quotes_ambiguous"] is False


def test_two_quoted_runs_the_sentence_does_not_choose_between_are_named_and_refused():
    """Concern 3, the ambiguous half: name both runs and refuse rather than invent a subject.

    A compound subject, a run either side of the verb, and two clauses each with their own verb all
    leave no subject to name. The record must carry both runs and count nothing as a repeat.
    """
    for text in ('the "booking" and the "message" are created',
                 'the "message" panel shows the "booking"',
                 'the "booking" is created and the "message" is shown'):
        product = _verb_claim(text, QUOTED_BOOKING_CORPUS + (GET_MESSAGE,)).detail["product"]
        assert product["near_miss_kind"] == "ambiguous_quotes", text
        assert product["state"] == "zero", text
        assert product["word"] is None, text
        assert len(product["quoted_runs"]) >= 2, (text, product["quoted_runs"])
        named = " ".join(product["quoted_runs"])
        assert "booking" in named and "message" in named, (text, named)
        assert "counted as a repeat" in product["reason"], text
        assert "booking" in app.near_miss_sentence(product)
        assert "message" in app.near_miss_sentence(product)


def test_a_quoted_display_string_can_never_become_a_repeat_finding():
    """The failure this prevents: a false accusation published on a claim that quotes a caption.

    The review's sharpest form was a single quoted copy word plus an intent verb anywhere in the
    sentence accusing a POST route. Every assertion here reproduces a caption in quotes, and none of
    them may ever be `repeats_product` - whatever else it shares with the product, the claim is
    about text a person is shown.
    """
    cases = [
        ('the user sees "Booking"', QUOTED_BOOKING_CORPUS),
        ('the page shows "Booking created."', QUOTED_BOOKING_CORPUS),
        ('the "Booking Successful" banner', QUOTED_BOOKING_CORPUS),
        ('the "Booking." dialog appears', QUOTED_BOOKING_CORPUS),
        ('the "Saved." banner', QUOTED_BOOKING_CORPUS + (_surface("GET /saved", "get saved"),)),
        ('a "Welcome" message is created', MESSAGE_CORPUS),
        ('the response contains "Booking" once it is created', QUOTED_BOOKING_CORPUS),
        ('the "booking" panel shows "Booking created"', QUOTED_BOOKING_CORPUS),
    ]
    for text, surfaces in cases:
        copied = level_fitness._quoted_copy_runs(
            text, frozenset(word for surface in surfaces for word in level_fitness._product_words(
                " ".join(surface.claims) + " " + str(surface.target))))
        assert copied, f"the copy in {text!r} was not recognised"
        product = level_fitness._product_record("I4", text, surfaces, level_fitness.PRODUCT_FOUND, "")
        assert product["state"] != level_fitness.PRODUCT_FOUND, (text, product)
        assert product["near_miss"] is True, text


# --------------------------------------------------- TESTOPS-85: refusing costs too

# A corpus where both `room` and `booking` are words the product carries, so a compound noun can be
# read either way and the test cannot pass by the quoted word simply not matching anything.
COMPOUND_CORPUS = QUOTED_BOOKING_CORPUS + (GET_ROOM, POST_ROOM)


def test_a_quoted_word_before_a_product_noun_is_an_entity_when_a_verb_governs_it():
    """AC1: `a "room" booking exists` is a claim about a booking, not a caption.

    The quoted word is itself a word the product carries, so `"room" booking` is a compound domain
    noun and the head noun is the subject. A caption in front of a product noun (`a "Welcome"
    message`) has a quoted word the product does not carry and stays copy. Pinned both ways, and
    the intent verb is the same rescue as the existence verb.
    """
    entity = _verb_claim('a "room" booking exists', COMPOUND_CORPUS)
    product = entity.detail["product"]
    assert entity.verdict == "distinct"
    assert product["near_miss"] is True
    assert product["near_miss_kind"] == "no_intent"
    assert product["word"] == "booking"
    assert product["quoted_copy"] == []
    # The head noun is the subject even though only the modifier is quoted.
    assert product["word_quoted"] is False
    assert "booking" in product["reason"]

    created = _verb_claim('a "room" booking is created', COMPOUND_CORPUS)
    assert created.verdict == "repeats_product"
    assert created.detail["product"]["word"] == "booking"
    assert created.detail["product"]["route"] == "POST /booking"

    # The caption side is unchanged: `Welcome` is not a word the product carries.
    caption = _verb_claim('a "Welcome" message is created', MESSAGE_CORPUS).detail["product"]
    assert caption["near_miss_kind"] == "quoted_copy"
    assert caption["word"] == "message"
    assert caption["display_text"] == "Welcome"

    # With no governing verb the pair is still a caption, so nothing is rescued.
    plain = _verb_claim('the "room" booking', COMPOUND_CORPUS).detail["product"]
    assert plain["near_miss"] is True
    assert plain["state"] == "zero"


def test_the_copy_refusal_is_word_aware_and_cannot_hide_an_unquoted_subject():
    """AC2: `the "booking" booking` is assessed on the unquoted `booking`, not refused as copy.

    The same word occurs unquoted and is the only candidate subject, so the quoted run is a
    compound modifier, not a caption. The stored reason must also name the noun rather than print
    an empty pair of quotes.
    """
    product = _verb_claim('the "booking" booking', QUOTED_BOOKING_CORPUS).detail["product"]
    assert product["state"] == "zero"
    assert product["near_miss_kind"] == "no_intent"
    assert product["word"] == "booking"
    assert product["quoted_copy"] == []
    assert product["word_quoted"] is False
    assert '""' not in product["reason"]
    assert "\u201c\u201d" not in product["reason"]
    assert "display copy" not in product["reason"]

    # The word-level logic is what decides: a word with a free occurrence is not suppressed by a
    # copy run elsewhere in the sentence, even though the claim itself is still refused (copy can
    # never become a finding - TESTOPS-82).
    domain = frozenset({"booking", "message", "room"})
    assert level_fitness._quoted_copy_runs('the "booking" booking', domain) == []
    assert level_fitness._quoted_copy_suppressed('the "booking" booking', domain) == {}
    assert level_fitness._quoted_copy_suppressed(
        'the user sees "booking" and a booking exists', domain) == {}
    assert set(level_fitness._quoted_copy_suppressed('a "Welcome" message is created',
                                                     domain)) == {"welcome", "message"}


def test_every_near_miss_state_has_a_reason_a_reader_can_act_on():
    """AC3: no near miss may carry an empty reason, and the page must say the same sentence.

    The fault this pins is the one TESTOPS-78 fixed recurring: a `quoted_copy` record stored
    `quotes display copy ""` because the reason interpolated a field that only carries unquoted
    display copy. Every state the fixtures produce is walked here, and the set is asserted so a
    new state cannot appear without a sentence a reader can act on.
    """
    fixtures = {
        "display_copy": (BANNER, DISPLAY_CORPUS),
        "no_intent": ('the "booking" exists', QUOTED_BOOKING_CORPUS),
        "verb_differs": ('a "booking" is created', BOOKING_CORPUS),
        "quoted_copy": ('a "Welcome" message is created', MESSAGE_CORPUS),
        "ambiguous_quotes": ('the "booking" and the "message" are created',
                             QUOTED_BOOKING_CORPUS + (GET_MESSAGE,)),
        "passive_voice": ('a "room" gets booked', ROOM_CORPUS),
    }
    for kind, (text, surfaces) in fixtures.items():
        product = _verb_claim(text, surfaces).detail["product"]
        assert product["near_miss"] is True, (kind, product)
        assert product["near_miss_kind"] == kind, (kind, product["near_miss_kind"])
        reason = (product["reason"] or "").strip()
        assert reason, (kind, "empty stored reason")
        assert len(reason) > 60, (kind, reason)
        assert "check this one by hand" in reason or "check whether" in reason, (kind, reason)
        assert '""' not in reason and "\u201c\u201d" not in reason, (kind, reason)
        page = app.near_miss_sentence(product)
        assert page.strip(), (kind, "empty page sentence")
        assert '""' not in page and "\u201c\u201d" not in page, (kind, page)
        # Debugging shorthand must never reach a reader.
        assert "I4" not in page and "KP" not in page, (kind, page)


def test_a_passive_claim_is_declared_not_assessed():
    """AC4: `a "room" gets booked` records that a passive claim was not assessed, and why.

    `gets` is spelled like the read intent `get`, so it used to agree with `GET /room` and publish
    a read where the sentence asserts a change of state. The auxiliary is no longer the act; when
    the participle names no act the intent table knows, the record says so in words on the page.
    The control `a "room" gets created` still reads create/POST.
    """
    claim = _verb_claim('a "room" gets booked', ROOM_CORPUS)
    product = claim.detail["product"]
    assert claim.verdict != "repeats_product"
    assert product["state"] == "zero"
    assert product["near_miss_kind"] == "passive_voice"
    assert product["passive"] == "gets booked"
    assert product["assertion_verb"] == ""
    assert product["word"] == "room"
    assert "passive" in product["reason"]
    assert "does not assess" in product["reason"]
    assert "not counted as a repeat" in product["reason"]

    page = app.near_miss_sentence(product)
    assert "passive" in page
    assert "does not assess" in page

    control = _verb_claim('a "room" gets created', ROOM_CORPUS)
    assert control.verdict == "repeats_product"
    assert control.detail["product"]["assertion_verb"] == "create"
    assert control.detail["product"]["route"] == "POST /room"
    assert control.detail["product"]["passive"] == ""
