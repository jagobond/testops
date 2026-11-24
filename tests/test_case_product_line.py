"""TESTOPS-83: the case page shows the product line its verdict rests on.

The page used to say "the product already declares POST /" and link a commit; the reader had to
leave the page to check it. These tests pin the missing half of the argument:

  * the annotation and the method signature are read from the stored blob at the claim's own commit,
    shown as the file's own lines (whitespace untouched) with file, line and commit;
  * the word that decided the match is marked with an accessible name, not colour alone;
  * a located declaration is in exactly one of three states, each said in words: complete (the
    whole declaration is shown), trimmed (a count, an ellipsis and what the remainder is), and
    undelimitable (the walk could not close the body, so the block is only its beginning);
  * a long handler states how many of its lines were not shown, and never blames the 8-line cap
    for a body the page does not print;
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
    # two are shown. The sentence names what was shown, out of what, and what the rest is - the
    # body this page does not print - so the reader cannot read the 8-line cap as the cause.
    assert ("The signature is 2 of 404 lines of this declaration (lines 5–6); the other 402 lines "
            "are the body, which this page does not print.") in _text(page)
    assert "At most 8 lines are shown" not in _text(page)
    assert '<span class="sline omission"' in figure
    assert "\u2026" in figure
    assert 'aria-label="402 lines of the declaration not shown"' in figure


def test_a_cap_that_cuts_the_signature_says_the_cap_did_it(tmp_path):
    # A signature with more parameters than the cap: the cap, not the body, is what is missing.
    parameters = ",\n".join(f"        @RequestParam(name = \"p{number}\") String p{number}"
                            for number in range(8))
    text = ("package example;\n\npublic class RoomController {\n"
            "    @RequestMapping(value = \"/\", method = RequestMethod.POST)\n"
            "    public ResponseEntity<Room> createRoom(\n"
            f"{parameters}) {{\n"
            "        return null;\n    }\n}\n")
    conn = _seed(tmp_path, product_text=text)
    try:
        page = _html(conn)
    finally:
        conn.close()
    figure = _product_figure(page)
    assert figure is not None
    shown = [number for number, _text_line in _shown_lines(figure)]
    assert shown == [4, 5, 6, 7, 8, 9, 10, 11]
    assert ("The 8-line cap shows 8 of 12 lines of this declaration (lines 4–11); the other 4 "
            "lines are not shown, including the rest of the signature.") in _text(page)


# --------------------------------------------------------------------------- AC1/AC3, by state

TRUNCATED_CONTROLLER_TEXT = """\
package example;

public class RoomController {

    @RequestMapping(value = "/", method = RequestMethod.POST)
    public ResponseEntity<Room> createRoom(@RequestBody Room room) {
        return new ResponseEntity<>(new Room(), HttpStatus.CREATED);
"""


def test_a_method_body_with_no_closing_brace_is_never_rendered_as_complete(tmp_path):
    # The stored file ends inside the body: the signature's ``{`` is found and never closed.
    conn = _seed(tmp_path, product_text=TRUNCATED_CONTROLLER_TEXT)
    try:
        page = _html(conn)
    finally:
        conn.close()
    figure = _product_figure(page)
    assert figure is not None, _text(page)
    shown = _text(page)
    # The inability is stated in words, with the exact sentence, and the block is marked as cut.
    assert ("The rest of this declaration could not be delimited: its opening brace was found and "
            "its closing brace was not, so this page shows only its beginning and cannot say how "
            "many lines follow.") in shown
    assert '<span class="sline omission"' in figure
    assert 'aria-label="the rest of this declaration could not be delimited"' in figure
    assert "\u2026" in figure
    # And it is not dressed as a complete declaration: no cap sentence, no count.
    assert "lines of this declaration" not in shown
    assert "The whole declaration is shown" not in shown


def test_a_complete_small_declaration_says_so_and_shows_no_ellipsis(tmp_path):
    # A declaration whose whole extent is its annotation and signature: a body on the same line.
    text = CONTROLLER_TEXT.replace(
        "    public ResponseEntity<Room> createRoom(@RequestBody Room room) {\n"
        "        return new ResponseEntity<>(new Room(), HttpStatus.CREATED);\n    }",
        "    public ResponseEntity<Room> createRoom(@RequestBody Room room) "
        "{ return null; }")
    conn = _seed(tmp_path, product_text=text)
    try:
        page = _html(conn)
    finally:
        conn.close()
    figure = _product_figure(page)
    assert figure is not None
    assert "The whole declaration is shown." in _text(page)
    assert '<span class="sline omission"' not in figure
    assert "of this declaration" not in _text(page)
    assert "could not be delimited" not in _text(page)


def test_the_three_states_are_three_different_sentences(tmp_path):
    """The same page furniture, three truths: nothing cut, a cut that is counted, an unknown end."""
    complete = CONTROLLER_TEXT.replace(
        "    public ResponseEntity<Room> createRoom(@RequestBody Room room) {\n"
        "        return new ResponseEntity<>(new Room(), HttpStatus.CREATED);\n    }",
        "    public ResponseEntity<Room> createRoom(@RequestBody Room room) "
        "{ return null; }")
    cases = {
        "complete": (complete, "The whole declaration is shown."),
        "trimmed": (CONTROLLER_TEXT.replace(
            "        return new ResponseEntity<>(new Room(), HttpStatus.CREATED);",
            "\n".join("        int value%d = %d;" % (n, n) for n in range(60)) + "\n"
            "        return new ResponseEntity<>(new Room(), HttpStatus.CREATED);"),
                    "The signature is 2 of 64 lines of this declaration (lines 6–7); the other 62 "
                    "lines are the body, which this page does not print."),
        "undelimitable": (TRUNCATED_CONTROLLER_TEXT,
                          "The rest of this declaration could not be delimited: its opening brace "
                          "was found and its closing brace was not, so this page shows only its "
                          "beginning and cannot say how many lines follow."),
    }
    for state, (text, sentence) in cases.items():
        directory = tmp_path / state
        directory.mkdir()
        conn = _seed(directory, product_text=text)
        try:
            page = _html(conn)
        finally:
            conn.close()
        figure = _product_figure(page)
        assert figure is not None, state
        assert sentence in _text(page), state
        # Each sentence is a different claim about what the block is.
        others = [other for name, (_t, other) in cases.items() if name != state]
        assert all(other not in _text(page) for other in others), state


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


def test_a_python_complete_declaration_is_decorator_and_def_and_ends_at_the_dedent(tmp_path):
    source = """\
from flask import Flask

app = Flask(__name__)


@app.route("/booking")
def get_booking(booking_id: int): return load(booking_id)
"""
    conn = _seed(tmp_path, product_surface="api:GET /booking", product_word="booking",
                 extra_artefacts=[
                     (f"github:{PRODUCT_REPO}@{PRODUCT_COMMIT}:service/short.py", "code", source)])
    try:
        page = _html(conn)
    finally:
        conn.close()
    figure = _product_figure(page)
    assert figure is not None, _text(page)
    shown = _shown_lines(figure)
    # The unit is the decorator plus the def, and the whole of it fits: no count, no ellipsis.
    assert [n for n, _t in shown] == [6, 7]
    assert "The whole declaration is shown." in _text(page)
    assert '<span class="sline omission"' not in figure
    assert "could not be delimited" not in _text(page)


def test_a_docstring_heavy_python_handler_is_trimmed_not_undelimitable(tmp_path):
    docstring = "\n".join('    """' if n == 0 else f"    line {n} of what this handler promises"
                          for n in range(30)) + '\n    """'
    source = ("from flask import Flask\n\napp = Flask(__name__)\n\n\n"
              "@app.route(\"/booking\")\ndef get_booking(booking_id: int):\n"
              f"{docstring}\n    booking = load(booking_id)\n    return booking\n")
    conn = _seed(tmp_path, product_surface="api:GET /booking", product_word="booking",
                 extra_artefacts=[
                     (f"github:{PRODUCT_REPO}@{PRODUCT_COMMIT}:service/long.py", "code", source)])
    try:
        page = _html(conn)
    finally:
        conn.close()
    figure = _product_figure(page)
    assert figure is not None, _text(page)
    assert [n for n, _t in _shown_lines(figure)] == [6, 7]
    # A body the parser delimited: the count is stated, and the unknown is not claimed.
    assert ("The signature is 2 of 35 lines of this declaration (lines 6–7); the other 33 lines "
            "are the body, which this page does not print.") in _text(page)
    assert "could not be delimited" not in _text(page)
    assert 'aria-label="33 lines of the declaration not shown"' in figure


def test_an_unparseable_python_file_says_the_end_could_not_be_established(tmp_path):
    source = """\
from flask import Flask

app = Flask(__name__)


@app.route("/booking")
def get_booking(booking_id: int):
    booking = load(booking_id
    return booking
"""
    conn = _seed(tmp_path, product_surface="api:GET /booking", product_word="booking",
                 extra_artefacts=[
                     (f"github:{PRODUCT_REPO}@{PRODUCT_COMMIT}:service/broken.py", "code", source)])
    try:
        page = _html(conn)
    finally:
        conn.close()
    figure = _product_figure(page)
    assert figure is not None, _text(page)
    assert [n for n, _t in _shown_lines(figure)] == [6, 7]
    assert ("The rest of this declaration could not be delimited: the stored file could not be "
            "parsed, so this page shows only its beginning and cannot say how many lines follow.") \
        in _text(page)
    assert 'aria-label="the rest of this declaration could not be delimited"' in figure
    assert "lines of this declaration" not in _text(page)


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
    assert rendered == _golden_bytes(GOLDEN), (
        "the golden page changed; regenerating it is a deliberate act (see the docstring)")


# The golden files are checked out with the platform's line endings under core.autocrlf; the page
# is rendered with LF. A CRLF checkout is not a changed page, so compare on normalised bytes.
def _golden_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(bytes([13, 10]), bytes([10]))


# The three states of a located declaration, each pinned as a checked-in page. Regenerate with
# ``fixtures/product_line/README.md``'s recipe; a changed sentence must fail here first.
STATE_GOLDENS = {
    "complete": Path(__file__).parent / "fixtures" / "product_line" /
                "case-product-line-complete.html",
    "trimmed": Path(__file__).parent / "fixtures" / "product_line" /
               "case-product-line-trimmed.html",
    "undelimitable": Path(__file__).parent / "fixtures" / "product_line" /
                     "case-product-line-undelimitable.html",
}


def test_the_three_states_are_pinned_byte_for_byte_by_golden_pages(tmp_path, monkeypatch):
    """Every located declaration is in exactly one of three states, and each has a page.

    complete: the whole declaration is shown, no ellipsis, no count.
    trimmed: the signature is shown and the rest of the declaration is counted, with an ellipsis.
    undelimitable: the end could not be established, said in words, with an ellipsis and no count.
    """
    monkeypatch.setattr(app, "age", lambda iso: "a fixed time ago")
    texts = {
        "complete": CONTROLLER_TEXT.replace(
            "    public ResponseEntity<Room> createRoom(@RequestBody Room room) {\n"
            "        return new ResponseEntity<>(new Room(), HttpStatus.CREATED);\n    }",
            "    public ResponseEntity<Room> createRoom(@RequestBody Room room) "
            "{ return null; }"),
        "trimmed": CONTROLLER_TEXT.replace(
            "        return new ResponseEntity<>(new Room(), HttpStatus.CREATED);",
            "\n".join("        int value%d = %d;" % (n, n) for n in range(60)) + "\n"
            "        return new ResponseEntity<>(new Room(), HttpStatus.CREATED);"),
        "undelimitable": TRUNCATED_CONTROLLER_TEXT,
    }
    for state, text in texts.items():
        directory = tmp_path / state
        directory.mkdir()
        conn = _seed(directory, product_text=text)
        try:
            rendered = app.case_page(conn, CASE)
        finally:
            conn.close()
        assert rendered == _golden_bytes(STATE_GOLDENS[state]), (
            f"the {state} golden page is stale")
