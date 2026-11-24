"""TESTOPS-70: a Java product is read for its Spring routes, and what each one claims.

The finding: ``surfaces/discover.py`` parsed Python only, so a Java/Spring product was
``not_assessable`` - honest, and useless. These tests pin the reading, not a count:

- AC1: ``.java`` is a language the reader parses, the files are reported as parsed, and ``.java`` is
  no longer an unread kind for the collector.
- AC2: the six Spring MVC mappings produce surfaces, a class-level ``@RequestMapping`` prefixes its
  methods, and the three joining cases are pinned exactly.
- AC3: ``target`` reads ``GET /booking/{id}``, layer is ``api``, ids are stable across runs, and two
  methods mapping the same route are two surfaces.
- AC4: claims come from ``@Operation(summary=...)``, else the method's Javadoc first sentence, else
  the humanised method name; an unannotated method is not a surface at all.
- AC5: ``found`` / ``zero`` / ``not_assessable`` stay distinct for a Java repository, and a mixed
  repository reports both languages with their counts.
- AC6: the fixtures are small synthetic Spring controllers under ``tests/fixtures/java``. Nothing
  here touches the network or clones a repository.

The reader lexes before it parses, so a mapping annotation inside a comment or a string literal is
not a route; two tests below hold that line.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

from testops import config, pipeline
from testops.collectors import github
from testops.surfaces import discover as surface_discovery
from testops.surfaces import java

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "java"


def _fixtures() -> dict[str, str]:
    """Every synthetic controller under ``tests/fixtures/java``, path -> text. No network."""
    return {path.name: path.read_text(encoding="utf-8") for path in sorted(FIXTURES.glob("*.java"))}


def _discover(*names: str):
    files = _fixtures()
    return surface_discovery.discover({name: files[name] for name in names})


def _targets(discovery) -> set[str]:
    return {surface.target for surface in discovery.surfaces}


# --------------------------------------------------------------------------- AC1: a parsed language

def test_java_is_a_language_the_reader_parses_and_its_files_are_reported_as_parsed():
    assert surface_discovery.LANGUAGES[".java"] == "Java"

    discovery = _discover("BookingController.java", "PlainController.java")

    assert discovery.state == surface_discovery.FOUND
    assert discovery.parsed == 2, "both .java files were read"
    assert (".java", 2) in discovery.languages
    assert discovery.record()["parsed"] == 2


def test_java_is_no_longer_a_kind_the_collector_refuses(monkeypatch):
    """AC1: `.java` leaves the unsupported-kind report because a reader now reads it."""
    assert ".java" in {rule.suffix for rule in config.FILE_KINDS}

    entries = [{"type": "blob", "path": "src/App.java", "size": 10, "sha": "sha:App.java"},
               {"type": "blob", "path": "src/Notes.kt", "size": 10, "sha": "sha:Notes.kt"}]

    def get_json(url, headers=None):
        if "/git/trees/" in url:
            return {"tree": entries}
        return {"content": base64.b64encode(b"class App {}").decode()}

    monkeypatch.setattr(github, "get_json", get_json)
    monkeypatch.setattr(github.blobs, "put", lambda raw: "blob:" + raw.decode())
    collected = github.collect(config.Repo("o", "product"), "token",
                               commit="c" * 40, role="product")

    assert "src/App.java" in collected.files
    assert "src/App.java" not in [path for entry in collected.skipped for path in entry.files]
    unsupported = {entry.kind for entry in collected.skipped if entry.reason == github.UNSUPPORTED}
    assert ".java" not in unsupported
    assert unsupported == {".kt"}
    assert collected.counts.get("code") == 1


# --------------------------------------------------------------------------- AC2: the mappings

def test_each_spring_mapping_annotation_produces_a_surface():
    discovery = _discover("BookingController.java")
    targets = _targets(discovery)

    assert "GET /booking" in targets            # @GetMapping("/") under @RequestMapping("/booking")
    assert "GET /booking/{id}" in targets        # @GetMapping("/{id}")
    assert "POST /booking" in targets            # @PostMapping with no path
    assert "PATCH /booking/{id}" in targets      # @PatchMapping
    assert "DELETE /booking/{id}" in targets     # @DeleteMapping
    assert "PUT /booking/{id}" in targets        # @PutMapping


def test_a_multi_path_annotation_is_one_surface_per_path():
    discovery = _discover("MultiPathController.java")

    assert _targets(discovery) == {"GET /rooms/a", "GET /rooms/b"}


def test_request_mapping_with_method_and_paths_is_read_both_ways_round():
    discovery = _discover("RequestMappingController.java")
    targets = _targets(discovery)

    assert "GET /legacy" in targets
    # value = {"/multi", "/many"}, method = {GET, POST}: two paths, two verbs, four surfaces.
    assert {"GET /multi", "POST /multi", "GET /many", "POST /many"} <= targets
    # `path` is an alias of `value`, and is read as one.
    assert "GET /by-path" in targets
    assert len(discovery.surfaces) == 6


def test_the_three_joining_cases_are_pinned():
    """AC2: `/booking` + `/`, `/booking` + `/{id}`, and a method with no class prefix."""
    assert java._join("/booking", "/") == "/booking"
    assert java._join("/booking", "/{id}") == "/booking/{id}"
    assert java._join("", "/booking") == "/booking"
    # And through the reader, so the helper is not tested on its own.
    targets = _targets(_discover("BookingController.java"))
    assert "GET /booking" in targets and "GET /booking/{id}" in targets


def test_an_interface_declares_surfaces_and_an_unannotated_method_does_not():
    discovery = _discover("BookingApi.java")

    assert _targets(discovery) == {"GET /booking/{id}"}
    assert all(s.claims != ["describe"] for s in discovery.surfaces)


# --------------------------------------------------------------------------- AC3: the surface

def test_target_layer_and_stable_ids_read_like_a_python_surface():
    first = _discover("BookingController.java")
    second = _discover("BookingController.java")

    surface = next(s for s in first.surfaces if s.target == "GET /booking/{id}")
    assert surface.layer == "api"
    assert surface.id == next(s.id for s in second.surfaces if s.target == "GET /booking/{id}")
    assert [s.id for s in first.surfaces] == [s.id for s in second.surfaces]


def test_two_methods_mapping_the_same_route_are_two_surfaces():
    discovery = _discover("DuplicateRouteController.java")

    same = [s for s in discovery.surfaces if s.target == "GET /dupes/same"]
    assert len(same) == 2, "a duplicate route is a fact worth showing, not a surface to fold away"
    assert len({s.id for s in same}) == 2
    assert {claim for s in same for claim in s.claims} == {"Reads a duplicate.",
                                                           "Reads the same route again: two "
                                                           "declarations, two surfaces."}


# --------------------------------------------------------------------------- AC4: the claims

def test_claims_prefer_the_operation_summary_then_the_javadoc_then_the_humanised_name():
    discovery = _discover("BookingController.java")
    claims = {s.target: s.claims for s in discovery.surfaces}

    assert claims["POST /booking"] == ["Creates a booking from the request body"]
    assert claims["GET /booking/{id}"] == ["Returns one booking by its id."]
    assert claims["PUT /booking/{id}"] == ["update booking"]


def test_a_method_with_no_mapping_annotation_is_not_a_surface():
    discovery = _discover("BookingController.java")

    assert all("helper" not in s.id for s in discovery.surfaces)
    assert all("anUnannotatedHelper" not in " ".join(s.claims) for s in discovery.surfaces)


def test_an_annotation_in_a_comment_or_a_string_is_not_a_route():
    """The reader lexes: structure inside comments and literals is not structure in the file."""
    discovery = _discover("BookingController.java")

    assert all("not-a-route" not in s.target for s in discovery.surfaces)
    assert all("also-not-a-route" not in s.target for s in discovery.surfaces)

    text = _fixtures()["BookingController.java"]
    assert [route for route in (java.routes(text) or []) if "route" in route.path] == []


# --------------------------------------------------------------------------- AC5: three states

def test_a_java_repository_that_declares_routes_is_found_never_not_assessable():
    discovery = _discover("BookingController.java", "PlainController.java")

    assert discovery.state == surface_discovery.FOUND
    assert discovery.surfaces
    assert discovery.state != surface_discovery.NOT_ASSESSABLE


def test_a_java_repository_with_no_routes_is_zero_and_not_not_assessable():
    discovery = _discover("PlainController.java")

    assert discovery.state == surface_discovery.ZERO
    assert discovery.surfaces == ()
    assert discovery.reason == ""
    assert discovery.parsed == 1


def test_nothing_parseable_is_not_assessable_with_the_languages_and_counts():
    discovery = surface_discovery.discover({
        "src/App.kt": "class A",
        "src/App.scala": "object A",
    })

    assert discovery.state == surface_discovery.NOT_ASSESSABLE
    assert discovery.parsed == 0
    assert "Java" in discovery.reason and ".java" in discovery.reason
    assert {entry["suffix"]: entry["count"] for entry in discovery.record()["languages"]} == \
        {".kt": 1, ".scala": 1}


def test_a_mixed_repository_reports_both_languages_and_their_counts():
    files = _fixtures()
    discovery = surface_discovery.discover({
        "src/service.py": "def index():\n    return '/api/health'\n",
        "src/BookingController.java": files["BookingController.java"],
    })

    assert discovery.state == surface_discovery.FOUND
    assert {suffix: count for suffix, count in discovery.languages} == \
        {".java": 1, ".py": 1}
    assert any(s.layer == "api" and s.target.startswith("GET /") for s in discovery.surfaces)


# --------------------------------------------------------------------------- AC5: on a real run

TEXTS = {
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
    """A real levels run over an in-memory pair of repositories, written to a throwaway store."""
    from testops.collectors.github import Collected
    from testops.store import db

    path = tmp_path / "t70.db"
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


def test_a_java_product_run_reports_surfaces_and_its_page_never_says_not_assessable(
        monkeypatch, tmp_path):
    from testops.store import db
    from testops.web import app

    text = _fixtures()["BookingController.java"]
    TEXTS["sha:booking"] = text
    try:
        result, conn = _levels_run(
            monkeypatch, tmp_path,
            {"booking/src/main/java/BookingController.java": ("sha:booking", "source")})
        try:
            body = app.run_response(conn, result.run_id)[0].decode("utf-8")
            meta = json.loads(conn.execute(
                "SELECT meta FROM snapshot WHERE id = ?", (result.snapshot_id,)).fetchone()["meta"])
        finally:
            conn.close()
    finally:
        TEXTS.pop("sha:booking", None)

    assert result.stats["surfaces_state"] == "found"
    assert result.stats["surfaces"] > 0
    record = meta["surfaces"]
    assert record["state"] == "found" and record["parsed"] == 1
    assert {entry["suffix"] for entry in record["languages"]} == {".java"}
    assert "What the surface reader could not read" not in body
    assert "not assessable" not in body.lower()
