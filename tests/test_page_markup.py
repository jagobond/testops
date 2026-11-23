"""TESTOPS-52 AC4: no served page carries malformed markup, and a badge keeps its tone.

The blind contract author found ``<span class="badge class="hot">`` on the run pages: a quote
inside the ``class`` attribute, so the attribute ends at ``badge class=`` and ``hot`` becomes an
inert attribute name. The styling silently did nothing, and the emphasis a reader was owed was
missing - a badge that says "a problem" looked like every other badge.

This test parses every rendered page with ``html.parser`` - the front, the runs index, a run, the
case pages and the configuration page - and asserts, structurally:

  * no tag carries two ``class`` attributes;
  * every attribute name is a well-formed name (a stray quote inside a value becomes a junk name);
  * every ``class`` value is a single whitespace-separated list of simple tokens - never a value
    that contains another ``class=``;
  * the badges carry the tone their state intends: an open case's badge wears ``hot``, a placed
    verdict with a problem wears ``hot``, a verdict that could not be concluded wears ``soft``,
    and a settled verdict wears neither.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

import test_claim_headline as rows
from testops import cases, services
from testops.store import db
from testops.web import app

TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")
NAME = re.compile(r"[A-Za-z_:][-A-Za-z0-9_:.]*\Z")


class _Tags(HTMLParser):
    """Every start tag the page emitted, with its parsed attribute list."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, list[tuple[str, str | None]]]] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, attrs))

    def handle_startendtag(self, tag, attrs):
        self.tags.append((tag, attrs))


def _tags(markup: str) -> list[tuple[str, list[tuple[str, str | None]]]]:
    parser = _Tags()
    parser.feed(markup)
    parser.close()
    return parser.tags


def _malformed(page: str, markup: str) -> list[str]:
    """Every tag on the page whose attributes are not well formed, named by page and tag."""
    problems: list[str] = []
    for tag, attrs in _tags(markup):
        rendered = f"<{tag} {attrs}>"
        for name, _value in attrs:
            if not NAME.match(name):
                problems.append(f"{page}: ill-formed attribute name in {rendered}")
        values = [value for name, value in attrs if name == "class"]
        if len(values) > 1:
            problems.append(f"{page}: two class attributes on {rendered}")
        for value in values:
            if value is None:
                problems.append(f"{page}: class with no value on {rendered}")
            elif "class=" in value or '"' in value:
                problems.append(f"{page}: 'class=' inside a class value on {rendered}")
            elif not all(TOKEN.match(token) for token in value.split()):
                problems.append(f"{page}: class value is not a token list on {rendered}")
    return problems


def _badges(markup: str) -> list[tuple[str, set[str]]]:
    """(visible-ish marker, class tokens) for every badge, so a test can read its tone class."""
    out = []
    for tag, attrs in _tags(markup):
        value = next((v for name, v in attrs if name == "class"), "") or ""
        tokens = set(value.split())
        if "badge" in tokens:
            out.append((tag, tokens))
    return out


def _store(tmp_path):
    """Two rows and a case page: one verdict asserting a problem, one that could not conclude."""
    conn = db.connect(tmp_path / "markup.db")
    rows._seed_case(conn, case_id="case-open", project="alpha", verdict="duplicate")
    rows._seed_case(conn, case_id="case-soft", project="alpha", verdict="unplaced",
                    analyser="duplication", created_at="2020-01-02T00:00:00+00:00")
    services.add_project(conn, "alpha", "Alpha")
    cases.set_state(conn, "case-open", "open", "harry", "")
    return conn


def _pages(conn) -> dict[str, str]:
    return {
        "front": app.index(conn).decode("utf-8"),
        "runs": app.runs_index(conn).decode("utf-8"),
        "run": app.run_response(conn, "run-case-open")[0].decode("utf-8"),
        "case-open": app.case_page(conn, "case-open").decode("utf-8"),
        "case-soft": app.case_page(conn, "case-soft").decode("utf-8"),
        "config": app.config_page(conn).decode("utf-8"),
    }


def test_no_served_page_carries_malformed_attributes(tmp_path):
    conn = _store(tmp_path)
    try:
        pages = _pages(conn)
    finally:
        conn.close()

    problems = [problem for page, markup in pages.items() for problem in _malformed(page, markup)]
    assert not problems, "malformed markup is served:\n" + "\n".join(problems)


def test_every_badge_keeps_the_tone_its_state_intends(tmp_path):
    conn = _store(tmp_path)
    try:
        front = app.index(conn).decode("utf-8")
        run = app.run_response(conn, "run-case-open")[0].decode("utf-8")
    finally:
        conn.close()

    front_tokens = [tokens for _tag, tokens in _badges(front)]
    run_tokens = [tokens for _tag, tokens in _badges(run)]

    # An alarm badge is an alarm: the run page's open case and the front's "Not proved" verdict.
    assert any("hot" in tokens for tokens in run_tokens), "no badge wears the alarm tone"
    assert any("hot" in tokens and "verdict" in tokens for tokens in front_tokens), \
        "an asserting verdict's badge does not wear the alarm tone"
    # A verdict that could not be concluded is dashed, not alarmed.
    assert any("soft" in tokens and "verdict" in tokens for tokens in front_tokens), \
        "an inconclusive verdict's badge does not wear the soft tone"
    # Nothing wearing both: a badge cannot be alarmed and uncertain at once.
    assert not [tokens for tokens in front_tokens + run_tokens
                if {"hot", "soft"} <= tokens], "a badge wears both tones"
