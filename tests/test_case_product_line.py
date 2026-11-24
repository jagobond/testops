"""TESTOPS-83: the case page shows the product line its verdict rests on.

The page used to say "the product already declares POST /" and link a commit; the reader had to
leave the page to check it. These tests pin the missing half of the argument:

  * the annotation and the method signature are read from the stored blob at the claim's own commit,
    shown as the file's own lines (whitespace untouched) with file, line and commit;
  * the word that decided the match is marked with an accessible name, not colour alone;
  * a long handler states how many of its lines were not shown;
  * every absence (no coordinates, no artefact, no blob, no declaration, several declarations, a
    credential shape) has its own sentence - never a guessed line and never an empty box.
"""
from __future__ import annotations

import html as htmllib
import re
from pathlib import Path

import pytest

from testops import blobs, queries
from testops.store import db
from testops.web import app

TS = "2020-01-01T00:00:00+00:00"
CASE = "case-product-line"
SNAP = "snap-product-line"
RUN = "run-product-line"
TEST_COMMIT = "a" * 40
PRODUCT_COMMIT = "b" * 40
OTHER_COMMIT = "c" * 40
TEST_REPO = "owner/tests"
PRODUCT_REPO = "owner/product"
FEATURE = "features/room.feature"
CONTROLLER = "product/src/RoomController.java"
ROUTE = "POST /"
WORD = "room"
SURFACE = f"api:{ROUTE}@{CONTROLLER}:createRoom"

FEATURE_TEXT = """\
Feature: rooms
  Scenario: create a room
    Given an administrator
    When the administrator adds a room
    Then New room will be created
"""

CONTROLLER_TEXT = """\
package example;

@RestController
public class RoomController {

    @RequestMapping(value = "/", method = RequestMethod.POST)
    public ResponseEntity<Room> createRoom(@RequestBody Room room) {
        return new ResponseEntity<>(new Room(), HttpStatus.CREATED);
    }

    @RequestMapping(value = "/", method = RequestMethod.GET)
    public ResponseEntity<Rooms> getRooms() {
        return new ResponseEntity<>(new Rooms(), HttpStatus.OK);
    }
}
"""


@pytest.fixture(autouse=True)
def _blob_store(tmp_path, monkeypatch):
    monkeypatch.setattr(blobs, "BLOB_DIR", tmp_path / "blobs")


def _seed(tmp_path, *, product_text=CONTROLLER_TEXT, product_surface=SURFACE,
          product_word=WORD, product_state: str | None = "found", product_artefact=True,
          product_blob=True, extra_artefacts=(), snapshot_meta=None):
    conn = db.connect(tmp_path / "product.db")
    meta = snapshot_meta if snapshot_meta is not None else {
        "arms": {"test": TEST_REPO, "product": PRODUCT_REPO}}
    db.upsert_snapshot(conn, SNAP, "fixture", TS,
                       {TEST_REPO: TEST_COMMIT, PRODUCT_REPO: PRODUCT_COMMIT},
                       schema_version=2, meta=meta)
    db.start_run(conn, RUN, "fixture", SNAP, "level_fitness", TS)

    feature_sha = blobs.put(FEATURE_TEXT.encode())
    db.add_artefact(conn, SNAP, f"github:{TEST_REPO}@{TEST_COMMIT}:{FEATURE}", "feature",
                    feature_sha)
    if product_artefact:
        sha = blobs.put(product_text.encode()) if product_blob else "0" * 64
        db.add_artefact(conn, SNAP,
                        f"github:{PRODUCT_REPO}@{PRODUCT_COMMIT}:{CONTROLLER}", "code", sha,
                        {"role": "product"})
    for uri, kind, text in extra_artefacts:
        db.add_artefact(conn, SNAP, uri, kind, blobs.put(text.encode()), {"role": "product"})

    product = None if product_state is None else {
        "state": product_state, "route": ROUTE, "word": product_word,
        "surface": product_surface, "shared_with": 6, "surfaces": 25, "claim": "create room",
        "near_miss": False,
    }
    detail = {"product": product} if product is not None else {}
    claim_id = db.add_claim(conn, RUN, "level_fitness", "0.13.0",
                            "scenario:features/room.feature#create a room",
                            "The product already publishes this route.", "repeats_product", 0.5, [],
                            schema_version=2, assertion_text="New room will be created",
                            assertion_path=FEATURE, assertion_line=5,
                            assertion_commit=TEST_COMMIT, interaction_label="needs a browser",
                            interaction_code="I4", span=["ui"],
                            established_by="the words name creation",
                            sources_assessed=True, sources_missing=[],
                            proposed_action="Assert this at the API.")
    db.add_inference(conn, claim_id, "none", "", "0", [], detail)
    conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at,"
                 " summary) VALUES (?,?,?,?,?,?,?)",
                 (CASE, RUN, "fixture", "level_fitness", SNAP, TS, "{}"))
    conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                 " VALUES (?,?,?,?,?)",
                 (CASE, "already exposed", "high", "f" * 32, db.j([claim_id])))
    conn.commit()
    return conn


def _html(conn) -> str:
    return app.case_page(conn, CASE).decode("utf-8")


def _product_figure(body: str) -> str | None:
    match = re.search(r'<figure class="snippet product".*?</figure>', body, re.S)
    return match.group(0) if match else None


def _shown_lines(figure: str) -> list[tuple[int, str]]:
    """(line number, text) as the page renders them, tags removed and text unescaped."""
    out = []
    for number, content in re.findall(
            r'<span class="sline[^"]*"><span class="ln">(\d+)</span>(.*?)</span>', figure, re.S):
        text = htmllib.unescape(re.sub(r"<[^>]+>", "", content))
        out.append((int(number), text))
    return out


def _text(body: str) -> str:
    text = re.sub(r"<style>.*?</style>", " ", body, flags=re.S)
    text = re.sub(r"<head>.*?</head>", " ", text, flags=re.S)
    return " ".join(htmllib.unescape(re.sub(r"<[^>]+>", " ", text)).split())


# --------------------------------------------------------------------------- AC2/AC3

def test_the_annotation_and_signature_are_shown_verbatim_from_the_stored_blob(tmp_path):
    conn = _seed(tmp_path)
    try:
        body = _html(conn)
    finally:
        conn.close()
    figure = _product_figure(body)
    assert figure is not None, body[:600]
    # The two lines the verdict rests on: the mapping annotation and the method signature.
    assert _shown_lines(figure)[0] == (6, "    @RequestMapping(value = \"/\", method = "
                                          "RequestMethod.POST)")
    assert _shown_lines(figure)[1][0] == 7
    assert "public ResponseEntity<Room> createRoom(@RequestBody Room room) {" in \
        _shown_lines(figure)[1][1]
    # Verbatim: every shown line is the blob's own line, character for character.
    lines = CONTROLLER_TEXT.splitlines()
    for number, text in _shown_lines(figure):
        assert text == lines[number - 1], number
    # File, line and commit are named together in the caption.
    caption = re.search(r"<figcaption>(.*?)</figcaption>", figure, re.S).group(1)
    assert f"{CONTROLLER}:6" in caption
    assert f"{PRODUCT_COMMIT[:8]}" in caption
    assert _text(body).count("The product’s own declaration") == 1


def test_the_product_line_is_read_at_the_runs_own_commit_not_any_other(tmp_path):
    def decoy(method: str) -> str:
        return ("package example;\n\n// decoy\n"
                "@RequestMapping(value = \"/\", method = RequestMethod.POST)\n"
                f"public ResponseEntity<Room> {method}() {{ return null; }}\n")

    conn = _seed(tmp_path, extra_artefacts=[
        (f"github:{PRODUCT_REPO}@{OTHER_COMMIT}:{CONTROLLER}", "code", decoy("createRoom"))])
    try:
        body = _html(conn)
    finally:
        conn.close()
    figure = _product_figure(body)
    assert figure is not None
    shown = htmllib.unescape(figure)
    assert "decoy" not in shown
    assert '@RequestMapping(value = "/", method = RequestMethod.POST)' in shown


def test_the_matched_word_is_marked_with_an_accessible_name(tmp_path):
    conn = _seed(tmp_path)
    try:
        body = _html(conn)
    finally:
        conn.close()
    figure = _product_figure(body)
    assert figure is not None
    assert '<mark class="hit" role="mark" aria-label="matched word: room">Room</mark>' in figure
    # The region is named, and the code block can be reached by keyboard.
    assert 'aria-label="Product code at product/src/RoomController.java:6"' in figure
    assert 'role="group"' in figure
    assert '<pre class="snippet" tabindex="0">' in figure


# --------------------------------------------------------------------------- AC5

def test_a_long_handler_says_how_many_of_its_lines_are_not_shown(tmp_path):
    body_lines = "\n".join(f"        int value{number} = {number};" for number in range(400))
    text = ("package example;\n\npublic class RoomController {\n\n"
            "    @RequestMapping(value = \"/\", method = RequestMethod.POST)\n"
            "    public ResponseEntity<Room> createRoom(@RequestBody Room room) {\n"
            f"{body_lines}\n"
            "        return null;\n    }\n}\n")
    conn = _seed(tmp_path, product_text=text)
    try:
        page = _html(conn)
    finally:
        conn.close()
    figure = _product_figure(page)
    assert figure is not None
    # The annotation and signature only, never the body.
    assert [number for number, _text_line in _shown_lines(figure)] == [5, 6]
    # The declaration runs from the annotation to the method's closing brace: 404 lines, of which
    # two are shown. The maximum, the true count and the omitted count are all stated.
    assert ("At most 8 lines are shown: lines 5–6 of a 404-line declaration, so 402 lines are not "
            "shown.") in _text(page)
    assert '<span class="sline omission"' in figure
    assert "\u2026" in figure
    assert 'aria-label="402 lines of the declaration not shown"' in figure


# --------------------------------------------------------------------------- the absences

def test_a_declaration_the_store_cannot_find_says_so_rather_than_guessing(tmp_path):
    conn = _seed(tmp_path, product_text=CONTROLLER_TEXT, product_surface=(
        f"api:{ROUTE}@{CONTROLLER}:noSuchMethod"))
    try:
        page = _html(conn)
    finally:
        conn.close()
    assert _product_figure(page) is None
    assert "The product line could not be located" in _text(page)
    assert "holds no declaration named noSuchMethod" in _text(page)


def test_a_surface_without_recorded_coordinates_says_the_line_cannot_be_shown(tmp_path):
    conn = _seed(tmp_path, product_surface="engine:src/rooms.py")
    try:
        page = _html(conn)
    finally:
        conn.close()
    assert _product_figure(page) is None
    assert "but not the file and declaration it came from" in _text(page)
    assert "engine:src/rooms.py" in _text(page)


def test_a_blob_the_store_no_longer_holds_says_recorded_but_not_stored(tmp_path):
    conn = _seed(tmp_path, product_blob=False)
    try:
        page = _html(conn)
    finally:
        conn.close()
    assert _product_figure(page) is None
    assert "its content is not in this store" in _text(page)


def test_an_artefact_the_run_did_not_store_says_the_line_cannot_be_shown(tmp_path):
    conn = _seed(tmp_path, product_artefact=False)
    try:
        page = _html(conn)
    finally:
        conn.close()
    assert _product_figure(page) is None
    assert "but not the file and declaration it came from" in _text(page)


# --------------------------------------------------------------------------- AC4

def test_a_credential_shaped_declaration_is_withheld_and_never_printed(tmp_path):
    # The credential shape is on the signature, which is what the page would print: a body-only
    # secret is never shown at all, so it cannot leak.
    text = CONTROLLER_TEXT.replace(
        "    public ResponseEntity<Room> createRoom(@RequestBody Room room) {",
        "    public ResponseEntity<Room> createRoom(@RequestBody Room room,\n"
        "                                           String password = \"hunter2-the-real-one\") {")
    conn = _seed(tmp_path, product_text=text)
    try:
        page = _html(conn)
    finally:
        conn.close()
    assert _product_figure(page) is None
    assert "hunter2-the-real-one" not in page
    assert "withheld rather than printed" in _text(page)
    assert "credential" in _text(page)


def test_markup_in_the_product_source_renders_as_text(tmp_path):
    text = CONTROLLER_TEXT.replace(
        "    public ResponseEntity<Room> createRoom(@RequestBody Room room) {",
        "    public ResponseEntity<Room> createRoom(String x = \"<script>alert(1)</script>\") {")
    conn = _seed(tmp_path, product_text=text)
    try:
        page = _html(conn)
    finally:
        conn.close()
    figure = _product_figure(page)
    assert figure is not None
    assert "<script" not in figure.lower()
    assert "&lt;script&gt;" in figure
    assert "alert(1)" in htmllib.unescape(re.sub(r"<[^>]+>", "", figure))


def test_rendering_the_product_line_opens_no_socket(tmp_path, monkeypatch):
    import socket

    def refuse(*_args, **_kwargs):
        raise AssertionError("the case page attempted network access at render time")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    conn = _seed(tmp_path)
    try:
        page = _html(conn)
    finally:
        conn.close()
    assert "RoomController" in page
    assert "create" in page


# --------------------------------------------------------------------------- a Python surface

def test_a_python_route_shows_its_decorator_and_function_signature(tmp_path):
    source = """\
from flask import Flask

app = Flask(__name__)


@app.route("/booking", methods=["GET"])
def get_booking(booking_id: int):
    booking = load(booking_id)
    return booking
"""
    conn = _seed(tmp_path, product_surface="api:GET /booking", product_word="booking",
                 extra_artefacts=[
                     (f"github:{PRODUCT_REPO}@{PRODUCT_COMMIT}:service/booking.py", "code",
                      source)])
    try:
        page = _html(conn)
    finally:
        conn.close()
    figure = _product_figure(page)
    assert figure is not None, _text(page)
    shown = _shown_lines(figure)
    assert shown[0] == (6, '@app.route("/booking", methods=["GET"])')
    assert shown[1] == (7, "def get_booking(booking_id: int):")
    assert '<mark class="hit" role="mark" aria-label="matched word: booking">booking</mark>' in figure
    assert "service/booking.py:6" in figure


# --------------------------------------------------------------------------- nothing to show

def test_a_claim_the_product_is_not_evidence_about_renders_no_product_block(tmp_path):
    conn = _seed(tmp_path, product_state=None)
    try:
        page = _html(conn)
    finally:
        conn.close()
    assert "What the product says" not in _text(page)
    assert _product_figure(page) is None


# --------------------------------------------------------------------------- the golden

GOLDEN = Path(__file__).parent / "fixtures" / "product_line" / "case-product-line-missing.html"


def test_the_not_located_page_is_pinned_byte_for_byte_by_a_golden(tmp_path, monkeypatch):
    """One case where the product line could not be located, kept as a checked-in page.

    The corpus has no such case - every recorded product surface in it resolves - so this golden is
    the only page that witnesses the "could not be located" state. Regenerating it is a deliberate
    act: render this fixture with ``app.age`` frozen to "a fixed time ago" and write the bytes to
    ``fixtures/product_line/case-product-line-missing.html``.
    """
    monkeypatch.setattr(app, "age", lambda iso: "a fixed time ago")
    conn = _seed(tmp_path, product_surface=f"api:{ROUTE}@{CONTROLLER}:noSuchMethod")
    try:
        rendered = app.case_page(conn, CASE)
    finally:
        conn.close()
    assert rendered == GOLDEN.read_bytes()
