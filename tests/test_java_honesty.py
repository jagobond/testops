"""TESTOPS-74: two ways the Java reader was silently wrong, and the words the run uses to say so.

Both defects are the one failure mode a reader of source code must never have - a wrong answer that
looks like a right one:

- AC1: an inherited class-level ``@RequestMapping`` prefix was dropped, so ``GET /booking/{id}``
  came out as ``GET /{id}``. It is now resolved from the superclass in the same repository (one
  level, with the resolution recorded), or the mapping is unread and names the superclass.
- AC2: a mapping path that is not a string literal fabricated ``GET /``. It is now unread, with a
  reason naming the expression, and produces no surface at all.
- AC3: unread mappings appear on the run page, where the run reports what it could not read.
- AC4: the assessment sentence names what its count counts - files fetched - instead of "items".

Nothing here touches the network: the fixtures are under ``tests/fixtures/java`` and the runs are
over in-memory trees written to throwaway stores.
"""
from __future__ import annotations

import json
from pathlib import Path

from testops import config, pipeline
from testops.collectors import github
from testops.surfaces import discover as surface_discovery
from testops.surfaces import java

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "java"


def _fixtures() -> dict[str, str]:
    return {path.name: path.read_text(encoding="utf-8") for path in sorted(FIXTURES.glob("*.java"))}


def _discover(*names: str):
    files = _fixtures()
    return surface_discovery.discover({name: files[name] for name in names})


def _targets(discovery) -> set[str]:
    return {surface.target for surface in discovery.surfaces}


# --------------------------------------------------------------------------- AC1: inherited prefix

def test_a_prefix_inherited_from_a_base_controller_is_resolved_and_recorded():
    """The base controller carries @RequestMapping("/booking"); the child must serve /booking/{id}."""
    discovery = _discover("BaseController.java", "BookingChildController.java")

    assert _targets(discovery) == {"GET /booking/{id}"}
    assert "GET /{id}" not in _targets(discovery), "the dropped-prefix route must not be emitted"

    record = discovery.record()
    assert record["inherited_prefixes"] == [{
        "source": "BookingChildController.java",
        "type": "BookingChildController",
        "superclass": "BaseController",
        "read_from": "BaseController.java",
        "prefix": ["/booking"],
    }]


def test_an_inherited_prefix_the_repository_cannot_supply_is_unread_and_names_the_superclass():
    discovery = _discover("OrphanController.java")

    assert discovery.surfaces == (), "a route with an unknown prefix is not a route"
    assert len(discovery.unread) == 1
    entry = discovery.unread[0]
    assert entry.method == "getOrder"
    assert entry.reason == java.REASON_PREFIX_NOT_READ
    assert "RemoteBaseController" in entry.detail
    assert discovery.record()["unread"][0]["detail"] == entry.detail
    assert "RemoteBaseController" in json.dumps(discovery.record())


def test_an_inherited_prefix_is_read_one_level_and_the_deeper_case_is_unread():
    """A grandparent's prefix is not chased: the run says so rather than guessing the route."""
    texts = {
        "GrandController.java": """\
@RequestMapping("/orders")
public abstract class GrandController { }
""",
        "MiddleController.java": """\
public abstract class MiddleController extends GrandController { }
""",
        "LeafController.java": """\
@RestController
public class LeafController extends MiddleController {
    @GetMapping("/{id}")
    public ResponseEntity<Order> getOrder() { return null; }
}
""",
    }
    discovery = surface_discovery.discover(texts)

    assert discovery.surfaces == ()
    assert len(discovery.unread) == 1
    assert discovery.unread[0].reason == java.REASON_PREFIX_NOT_READ
    assert "GrandController" in discovery.unread[0].detail
    assert "one level" in discovery.unread[0].detail


def test_a_superclass_that_declares_no_prefix_is_not_a_reason_to_refuse_the_route():
    texts = {
        "PlainBase.java": "public abstract class PlainBase { }",
        "Child.java": """\
@RestController
public class Child extends PlainBase {
    @GetMapping("/child")
    public ResponseEntity<Void> getChild() { return null; }
}
""",
    }
    discovery = surface_discovery.discover(texts)

    assert _targets(discovery) == {"GET /child"}
    assert discovery.unread == ()
    assert discovery.record()["inherited_prefixes"] == []


# ------------------------------------------- AC1, amended: the same defect through an interface

def test_a_prefix_on_an_implemented_interface_is_resolved_and_recorded():
    """Spring serves @RequestMapping on an interface; the class's route is /booking/{id}."""
    discovery = _discover("BookingPrefixApi.java", "InterfaceChildController.java")

    assert _targets(discovery) == {"GET /booking/{id}"}
    assert "GET /{id}" not in _targets(discovery), "the dropped-prefix route must not be emitted"
    assert discovery.record()["inherited_prefixes"] == [{
        "source": "InterfaceChildController.java",
        "type": "InterfaceChildController",
        "interface": "BookingPrefixApi",
        "read_from": "BookingPrefixApi.java",
        "prefix": ["/booking"],
    }]


def test_an_interface_prefix_the_repository_cannot_supply_is_unread_and_names_the_interface():
    texts = {
        "RemoteInterfaceController.java": """\
@RestController
public class RemoteInterfaceController implements RemoteApi {
    @GetMapping("/{id}")
    public ResponseEntity<Booking> getBooking() { return null; }
}
""",
    }
    discovery = surface_discovery.discover(texts)

    assert discovery.surfaces == (), "a route whose interface is not held is not a route"
    assert len(discovery.unread) == 1
    entry = discovery.unread[0]
    assert entry.reason == java.REASON_PREFIX_NOT_READ
    assert "RemoteApi" in entry.detail
    assert "does not hold" in entry.detail


def test_an_interface_with_no_class_prefix_is_not_a_reason_to_refuse_the_route():
    texts = {
        "MarkerApi.java": "public interface MarkerApi { String find(int id); }",
        "MarkerController.java": """\
@RestController
public class MarkerController implements MarkerApi {
    @GetMapping("/marker/{id}")
    public String find(int id) { return null; }
}
""",
    }
    discovery = surface_discovery.discover(texts)

    assert _targets(discovery) == {"GET /marker/{id}"}
    assert discovery.unread == ()


def test_a_child_of_a_parent_whose_prefix_is_a_constant_is_unread_with_the_parents_reason():
    """The parent's own prefix is a constant; the child must not read that as 'no prefix'."""
    discovery = _discover("ConstantPrefixBase.java", "ConstantPrefixChild.java")

    assert discovery.surfaces == ()
    assert len(discovery.unread) == 1
    entry = discovery.unread[0]
    assert entry.reason == java.REASON_CLASS_PATH_CONSTANT
    assert "ConstantPrefixBase" in entry.detail
    assert "Paths.BASE" in entry.detail


def test_a_superclass_file_that_does_not_lex_says_the_file_could_not_be_read():
    """The repository holds the file; this reader could not read it. Say that, not 'does not hold'."""
    texts = {
        "BrokenBase.java": "public abstract class BrokenBase {\n",     # unbalanced: not lexed
        "BrokenChild.java": """\
@RestController
public class BrokenChild extends BrokenBase {
    @GetMapping("/{id}")
    public String getItem(int id) { return null; }
}
""",
    }
    discovery = surface_discovery.discover(texts)

    assert discovery.surfaces == ()
    assert len(discovery.unread) == 1
    entry = discovery.unread[0]
    assert entry.reason == java.REASON_PREFIX_NOT_READ
    assert "BrokenBase" in entry.detail and "BrokenBase.java" in entry.detail
    assert "could not read" in entry.detail
    assert "does not hold" not in entry.detail


# --------------------------------------------------------------------------- AC2: constant paths

def test_a_mapping_path_that_is_a_constant_is_unread_and_invents_no_route():
    discovery = _discover("ConstantPathController.java")

    assert discovery.surfaces == (), "no surface may carry a route the reader invented"
    reasons = [(entry.method, entry.reason, entry.detail) for entry in discovery.unread]
    assert ("getBooking", java.REASON_PATH_CONSTANT, "Paths.BOOKING") in reasons
    assert ("getItems", java.REASON_PATH_CONSTANT, "Paths.ITEMS") in reasons
    assert "GET /" not in _targets(discovery)


def test_a_class_prefix_that_is_a_constant_makes_every_mapping_under_it_unread():
    discovery = _discover("ConstantPrefixController.java")

    assert discovery.surfaces == ()
    assert [(entry.reason, entry.detail) for entry in discovery.unread] == [
        (java.REASON_CLASS_PATH_CONSTANT, "Paths.CATALOGUE")]


def test_a_reader_refuses_a_path_that_mixes_a_literal_and_a_constant():
    text = """\
@RestController
public class Mixed {
    @GetMapping(Paths.PREFIX + "/{id}")
    public ResponseEntity<Booking> get() { return null; }
}
"""
    discovery = surface_discovery.discover({"Mixed.java": text})

    assert discovery.surfaces == ()
    assert discovery.unread[0].reason == java.REASON_PATH_CONSTANT
    assert "Paths.PREFIX" in discovery.unread[0].detail


# --------------------------------------------------------------------------- run page and sentence

TEXTS: dict[str, str] = {
    "sha:feature": """\
Feature: the guest books
  Scenario: a booking is accepted
    Then the booking is stored
""",
    "sha:steps": """\
public class Steps {
  [Then("the booking is stored")]
  public void ThenStored() { using var client = new HttpClient(); }
}
""",
}


def _levels_run(monkeypatch, tmp_path, product_files):
    from testops.collectors.github import Collected
    from testops.store import db

    path = tmp_path / "t74.db"
    real_connect = db.connect
    test_arm = Collected(commit="c" * 40, role="test",
                         files={"features/one.feature": ("sha:feature", "feature"),
                                "steps/Steps.cs": ("sha:steps", "stepdef")})
    product_arm = Collected(commit="p" * 40, role="product", files=product_files)
    arms = {"test": test_arm, "product": product_arm}

    monkeypatch.setattr(pipeline, "load_env", lambda: {})
    monkeypatch.setattr(pipeline.db, "connect", lambda: real_connect(path))
    monkeypatch.setattr(pipeline.blobs, "text", lambda sha: TEXTS[sha])
    monkeypatch.setattr(pipeline.github, "collect",
                        lambda repo, token, role="product": arms[role])

    project = config.Project("specimen", config.Repo("o", "product"),
                             config.Repo("o", "tests"), jira_key="")
    return pipeline.run_level_fitness(project, "token"), real_connect(path)


def _run_page(monkeypatch, tmp_path, product_files: dict[str, tuple[str, str]]):
    from testops.web import app

    result, conn = _levels_run(monkeypatch, tmp_path, product_files)
    try:
        body = app.run_response(conn, result.run_id)[0].decode("utf-8")
        meta = json.loads(conn.execute("SELECT meta FROM snapshot WHERE id = ?",
                                       (result.snapshot_id,)).fetchone()["meta"])
    finally:
        conn.close()
    return result, body, meta


def test_unread_mappings_are_reported_where_the_run_says_what_it_could_not_read(
        monkeypatch, tmp_path):
    """AC3: '2 mappings unread: path is a constant', not a surface count that silently excludes them."""
    fixtures = _fixtures()
    TEXTS["sha:constants"] = fixtures["ConstantPathController.java"]
    try:
        _result, body, meta = _run_page(monkeypatch, tmp_path, {
            "src/main/java/ConstantPathController.java": ("sha:constants", "source")})
    finally:
        TEXTS.pop("sha:constants", None)

    assert meta["surfaces"]["surfaces"] == 0
    assert len(meta["surfaces"]["unread"]) == 2
    assert "What the surface reader could not read" in body
    assert "2 mappings unread: path is a constant" in body
    assert "Paths.BOOKING" in body and "Paths.ITEMS" in body


def test_the_assessment_sentence_names_files_not_items(monkeypatch, tmp_path):
    """AC4: a reader can check 'returned 3 files' against the run's own artefact list."""
    TEXTS["sha:booking"] = _fixtures()["BookingController.java"]
    try:
        result, body, meta = _run_page(monkeypatch, tmp_path, {
            "booking/src/main/java/BookingController.java": ("sha:booking", "source")})
    finally:
        TEXTS.pop("sha:booking", None)

    assert result.stats["surfaces"] > 0
    assert meta["count_unit"] == "file"
    assert "Assessed: code and test code were consulted and returned 3 files." in body
    assert "items" not in body


def test_a_stored_snapshot_without_the_noun_keeps_the_sentence_it_rendered():
    """Nothing is retro-fitted: a record written before TESTOPS-74 still counts 'items'."""
    from testops import sources

    assessment = sources.Assessment((sources.CODE, sources.TEST_CODE), sources.FOUND, 2, (),
                                    (sources.Reading(sources.CODE, observed=1),
                                     sources.Reading(sources.TEST_CODE, observed=1)))
    assert assessment.sentence() == ("Assessed: code and test code were consulted and returned "
                                     "2 items.")
