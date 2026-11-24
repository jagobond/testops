"""TESTOPS-92. A switch that ignores a value is a switch that lies.

The defect: the ``?agent=`` flag accepted only the literal ``on``. Harry opened the same case page
twice, plain and with ``?agent=true``, saw the same page, and concluded the feature was broken. It
was working - it simply never read his value.

What is pinned here, in the ticket's order:

  * AC1 - eight accepted spellings (case-insensitive, trimmed), and the two defaults: an empty value
    and an absent parameter both mean off.
  * AC2 - an unrecognised value is never silent: the agent-off page plus one line that says the
    value was not understood and names what is accepted. It appears for ``maybe``, ``2`` and
    ``onn``, and for no accepted value and for no parameter at all.
  * AC3 - ``agent=off`` and no parameter are byte-identical to each other and to the pre-ticket page
    over all 275 real pages, by the same golden digests the TESTOPS-88 AC1 gate uses.
  * AC4 - ``/agent-report`` shows which flag values it saw, so a demo-day typo is a row in the
    meter rather than a silence between two rows.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import test_agent_case as ac
from testops.judgement import agent
from testops.store import db
from testops.web import app

CASE = ac.CASE


def _text(body: bytes) -> str:
    import html as htmllib
    text = body.decode("utf-8")
    text = re.sub(r"<style>.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(htmllib.unescape(text).split())


# --------------------------------------------------------------------------- AC1: the eight values

@pytest.mark.parametrize("value", ["on", "true", "1", "yes", "ON", "True", " YES ", "1"])
def test_the_show_values_mean_show(value):
    flag = app.parse_agent_flag(value)
    assert flag.variant == agent.VARIANT_ON
    assert flag.understood, f"{value!r} is one of the accepted spellings"


@pytest.mark.parametrize("value", ["off", "false", "0", "no", "OFF", "False", " No ", "0"])
def test_the_hide_values_mean_hide(value):
    flag = app.parse_agent_flag(value)
    assert flag.variant == agent.VARIANT_OFF
    assert flag.understood, f"{value!r} is one of the accepted spellings"


@pytest.mark.parametrize("value", ["", None])
def test_an_empty_value_and_an_absent_parameter_are_the_default_off(value):
    flag = app.parse_agent_flag(value)
    assert flag.variant == agent.VARIANT_OFF
    # An absent flag is the documented default, not a mistake: it must never warn at a reader.
    assert flag.understood


def test_every_accepted_spelling_is_pinned_as_a_table():
    """AC1's table, in one place: eight values, split the two ways the ticket names them."""
    assert app.FLAG_SHOW == ("on", "true", "1", "yes")
    assert app.FLAG_HIDE == ("off", "false", "0", "no")
    assert len(app.FLAG_ACCEPTED) == 8
    for value in app.FLAG_ACCEPTED:
        assert app.parse_agent_flag(value).understood


# --------------------------------------------------------------------------- AC2: never silent

@pytest.mark.parametrize("value", ["maybe", "2", "onn"])
def test_an_unrecognised_value_adds_exactly_one_line_to_the_off_page(tmp_path, value):
    conn = ac._seed(tmp_path)
    try:
        off = app.case_page(conn, CASE)
        flag = app.parse_agent_flag(value)
        assert not flag.understood and flag.variant == agent.VARIANT_OFF
        page, code = app.case_response(conn, CASE, variant=flag.variant, flag=flag)
    finally:
        conn.close()
    assert code == 200
    text = page.decode("utf-8")
    notes = re.findall(r'<p class="agent-flag-note">.*?</p>', text, re.S)
    assert len(notes) == 1, f"{value!r} must be said once, and in one place"
    # The explanation is not shown - the page is the off page - and the line says why.
    assert "Explanation of this case" not in text
    assert "agent-text" not in text
    assert value in _text(notes[0].encode())
    assert "not understood" in notes[0]
    # It names what is accepted, so a reader who typed something wrong can fix it.
    for accepted in app.FLAG_ACCEPTED:
        assert accepted in notes[0], f"the line must name {accepted!r}"
    # Nothing else changed: remove the line and the page is the agent-off page, byte for byte.
    assert text.replace(notes[0], "") == off.decode("utf-8")


@pytest.mark.parametrize("value", ["off", "false", "0", "no", None, ""])
def test_a_recognised_value_or_no_parameter_carries_no_line(tmp_path, value):
    conn = ac._seed(tmp_path)
    try:
        off = app.case_page(conn, CASE)
        flag = app.parse_agent_flag(value)
        page, code = app.case_response(conn, CASE, variant=flag.variant, flag=flag)
    finally:
        conn.close()
    assert code == 200
    assert page == off
    assert b"agent-flag-note" not in page


def test_the_warning_line_appears_for_no_show_value_and_no_accepted_hide_value():
    """The full table at the block level: exactly the unrecognised values produce a line."""
    refused = {value for value in ("maybe", "2", "onn", "o", "tru", "yes please", "-1")
               if app.flag_note_block(app.parse_agent_flag(value))}
    assert refused == {"maybe", "2", "onn", "o", "tru", "yes please", "-1"}
    for value in (*app.FLAG_ACCEPTED, None, ""):
        assert app.flag_note_block(app.parse_agent_flag(value)) == []


# --------------------------------------------------------------------------- AC3: off is untouched

def test_off_and_no_parameter_are_the_same_bytes_on_all_275_real_pages(monkeypatch):
    """AC3 over the product's own store: 226 case pages and 49 run pages, all 275.

    The digests are the ones the TESTOPS-88 AC1 gate uses, captured from the build before that
    ticket with the clock pinned. ``agent=off`` must render the very same bytes as no parameter at
    all, or the two ways of asking for the same page would be two different pages.
    """
    golden = json.loads(ac.GOLDEN.read_text(encoding="utf-8"))
    conn = ac._real_store()
    monkeypatch.chdir(ac.ROOT)
    monkeypatch.setattr(app, "dt", ac._DtShim)
    compared, absent, mismatched = 0, [], []
    explicit = app.parse_agent_flag("off")
    try:
        for case_id, digest in sorted(golden["cases"].items()):
            if conn.execute("SELECT 1 FROM case_ WHERE id = ?", (case_id,)).fetchone() is None:
                absent.append(case_id)
                continue
            plain = app.case_page(conn, case_id)
            stated, code = app.case_response(conn, case_id, variant=explicit.variant, flag=explicit)
            assert code == 200
            compared += 1
            if plain != stated or hashlib.sha256(plain).hexdigest() != digest:
                mismatched.append(case_id)
        for run_id, digest in sorted(golden["runs"].items()):
            if conn.execute("SELECT 1 FROM run WHERE id = ?", (run_id,)).fetchone() is None:
                absent.append(run_id)
                continue
            rendered = app.run_page(conn, run_id)
            compared += 1
            if hashlib.sha256(rendered).hexdigest() != digest:
                mismatched.append(run_id)
    finally:
        conn.close()
    assert not mismatched, f"the off page changed for: {mismatched[:5]}"
    assert not absent, f"the store no longer holds {len(absent)} of the golden pages"
    assert compared == 275, f"compared {compared} pages, not the 275 the golden holds"


# --------------------------------------------------------------------------- AC4: the meter

def _connect_factory(path):
    real = db.connect

    def connect(_path=None):
        return real(path)

    return connect


def _server(handler):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def _get(url: str) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.status, response.read().decode("utf-8")


def test_the_handler_records_what_was_typed_and_the_report_shows_it(tmp_path, monkeypatch):
    """A demo-day typo is visible in the meter, not inferred from an empty column."""
    conn = ac._seed(tmp_path)
    path = tmp_path / "agent.db"
    conn.close()
    monkeypatch.setattr(app.db, "connect", _connect_factory(path))
    httpd, base = _server(app.Handler)
    try:
        status, typed_badly = _get(f"{base}/case/{CASE}?agent=maybe")
        _get(f"{base}/case/{CASE}?agent=off")
        _get(f"{base}/case/{CASE}")
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert status == 200
    assert "was not understood" in typed_badly

    conn = db.connect(path)
    try:
        rows = {row["value"]: row for row in agent.flag_values(conn)}
        report = app.agent_report(conn)
    finally:
        conn.close()
    assert rows["maybe"]["variant"] == "off" and not rows["maybe"]["understood"]
    assert rows["maybe"]["views"] == 1
    assert rows["off"]["understood"] and rows["off"]["variant"] == "off"
    assert rows[""]["understood"] and rows[""]["variant"] == "off"      # no parameter
    text = _text(report)
    assert "The flag values readers typed" in text
    assert "maybe" in text
    assert "Agent off" in text
    # The typo's row says it was not understood; the accepted rows say they were.
    assert re.search(r"maybe\s+Agent off\s+no\s+1", text), text[:2000]
    assert re.search(r"off\s+Agent off\s+yes\s+1", text)


def test_the_report_says_when_no_flag_has_been_recorded(tmp_path):
    """An empty meter is "nothing was measured", never "every value was understood"."""
    conn = ac._seed(tmp_path)
    try:
        text = _text(app.agent_report(conn))
    finally:
        conn.close()
    assert "The flag values readers typed" in text
    assert "No case page has recorded its flag yet" in text
