"""TESTOPS-54: every page leads somewhere - a case links to its run, and /config is reachable.

The blind contract author (TESTOPS-7) could not walk from a case back to the run that produced it -
the case page linked `/`, `/runs` and GitHub, and nothing else - and could not reach `/config` from
any page at all. The brief's P5 forbids exactly that.

Four obligations, one per acceptance criterion:

  * AC1 - a case page links **its own run**, and the link says what it is rather than "back".
  * AC2 - `/config` is reachable from **every** page, through the same visible affordance.
  * AC3 - the round trip works: run -> case -> the same run, walked by parsing links only.
  * AC4 - no new dead ends: every internal href on every page resolves to 200.

The suite's store is a temp file, and the server it walks listens on an ephemeral port. It never
touches the live store or port 8791 (that hazard is TESTOPS-53's subject; this file does not add to
it).
"""
from __future__ import annotations

import sqlite3
import threading
import urllib.error
import urllib.request
from html.parser import HTMLParser
from http.server import ThreadingHTTPServer

import pytest

import test_claim_headline as rows
from testops import services
from testops.store import db
from testops.web import app

# The three projects the blind author named, and the analysers this build registers. The build has
# two analysers, so "a case from each" is as many distinct analysers as exist; both are covered.
PROJECTS = (("demo-product", "TestCraft DEMO", "level_fitness"),
            ("demo-service", "DemoService", "duplication"),
            ("demo-booking", "demo-booking", "level_fitness"))


# --------------------------------------------------------------------------- HTML helpers

class _Links(HTMLParser):
    """Every ``<a href>`` on a page, with the text a reader sees on it."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href is None:
            return
        self._href, self._text = href, []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.anchors.append((self._href, " ".join("".join(self._text).split())))
            self._href = None


def links(markup: str) -> list[tuple[str, str]]:
    parser = _Links()
    parser.feed(markup)
    parser.close()
    return parser.anchors


def hrefs(markup: str) -> list[str]:
    return [href for href, _text in links(markup)]


class _Forms(HTMLParser):
    """Every ``<form action>`` on a page: the address a reader's button posts to."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.actions: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag != "form":
            return
        attrs = dict(attrs)
        action = attrs.get("action")
        if action:
            self.actions.append((action, (attrs.get("method") or "get").lower()))


def form_actions(markup: str) -> list[tuple[str, str]]:
    parser = _Forms()
    parser.feed(markup)
    parser.close()
    return parser.actions


def internal(markup: str) -> list[str]:
    """In-page links only: an external repository link is not this tool's to keep alive."""
    seen: list[str] = []
    for href in hrefs(markup):
        if href.startswith("/") and href not in seen:
            seen.append(href.split("#")[0] or "/")
    return seen


# --------------------------------------------------------------------------- store + server

def _seeded(path):
    conn = db.connect(path)
    for project, name, analyser in PROJECTS:
        rows._seed_case(conn, case_id=f"case-{project}", project=project, analyser=analyser)
        services.add_project(conn, project, name)
    return conn


def _connect_factory(path):
    real = db.connect

    def connect(_path=None):
        return real(path)

    return connect


@pytest.fixture()
def store(tmp_path):
    conn = _seeded(tmp_path / "navigation.db")
    yield conn
    conn.close()


@pytest.fixture()
def served(tmp_path, monkeypatch):
    """A temp store and a server on an ephemeral port - never the live store or 8791 (TESTOPS-53).

    Yields ``(store path, base url)`` so a test can put the store into a state the product's own
    writes cannot reach (the orphaned case below) and still fetch the rendered page over HTTP.
    """
    path = tmp_path / "served.db"
    _seeded(path).close()
    monkeypatch.setattr(app.db, "connect", _connect_factory(path))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield path, f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture()
def live(served):
    return served[1]


def _get(base: str, path: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(base + path, timeout=10) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


# --------------------------------------------------------------------------- AC1

def test_a_case_page_links_its_own_run_and_the_link_says_what_it_is(store):
    """AC1: the case names the run that raised it - three projects, both analysers."""
    analysed = set()
    for project, _name, analyser in PROJECTS:
        case_id = f"case-{project}"
        run_id = f"run-{case_id}"
        page = app.case_page(store, case_id).decode("utf-8")
        anchors = dict(links(page))

        assert f"/run/{run_id}" in anchors, (
            f"the case page /case/{case_id} has no link to its run /run/{run_id}; a reader cannot "
            f"get back to the analysis that produced it (AC1). Links: {sorted(anchors)}")
        label = anchors[f"/run/{run_id}"]
        assert label == run_id, (
            f"the link to the case's run reads {label!r}; it must name the run, not say 'back'")
        assert "back" not in label.lower(), f"a bare 'back' link is not a named destination: {label!r}"
        analysed.add(analyser)

    assert analysed == {"level_fitness", "duplication"}, (
        f"AC1 was only exercised against {sorted(analysed)}; the build registers two analysers")


# --------------------------------------------------------------------------- AC2

def test_every_page_offers_the_same_visible_way_to_configuration(live):
    """AC2: /config is reachable from every page, by the same affordance, and it is visible text."""
    pages = ["/", "/runs", "/run/run-case-demo-product", "/case/case-demo-product", "/config", "/no-such-page"]
    affordances = {}
    for path in pages:
        status, body = _get(live, path)
        if path != "/no-such-page":
            assert status == 200, f"{path} returned HTTP {status}"
        config_links = [(href, text) for href, text in links(body) if href == "/config"]
        assert config_links, (
            f"the page {path} has no link to the configuration page (/config): it can only be "
            f"reached by guessing the URL (AC2)")
        assert all(text.strip() for _href, text in config_links), (
            f"the page {path} links /config with no visible text")
        affordances[path] = set(config_links)

    assert len({frozenset(a) for a in affordances.values()}) == 1, (
        "the way to /config differs from page to page: " + repr(
            {path: sorted(a) for path, a in affordances.items()}))


# --------------------------------------------------------------------------- AC3

def test_run_to_case_and_back_to_the_same_run(live):
    """AC3: the round trip, walked by following parsed links and constructing no URL."""
    status, run_html = _get(live, "/run/run-case-demo-service")
    assert status == 200
    run_href = "/run/run-case-demo-service"

    case_links = [h for h in internal(run_html) if h.startswith("/case/")]
    assert case_links, "the run page links no case"
    case_href = case_links[0]
    status, case_html = _get(live, case_href)
    assert status == 200

    back = [h.strip() for h in internal(case_html) if h.startswith("/run/")]
    assert back == [run_href], (
        f"walking run -> case -> back from {run_href} landed on {back}; the round trip must return "
        f"to the same run (AC3)")

    status, run_again = _get(live, back[0])
    assert status == 200
    assert case_href in internal(run_again), (
        f"the run page {back[0]} does not list the case {case_href} it was reached through")


# --------------------------------------------------------------------------- the orphaned run

def test_a_case_whose_run_is_gone_says_so_instead_of_linking_a_dead_page(served):
    """A case can outlive its run; the page must say so, not link a 404.

    The review manufactured this state in a store copy: a case row whose ``run_id`` names a run
    that is not there. No product write reaches it today (retention deletes case and run together,
    and the foreign key refuses the rest), so it is manufactured here the same way - with the
    foreign key off on this connection - and the assertion is the reviewer's: HTTP 200, no link to
    ``/run/<missing>``, and no href on the page answering 404.
    """
    path, base = served
    conn = db.connect(path)
    try:
        rows._seed_case(conn, case_id="case-orphan", findings=1)
        rows._seed_case(conn, case_id="case-orphan-empty", findings=0)
    finally:
        conn.close()

    store = sqlite3.connect(path)
    store.execute("PRAGMA foreign_keys = OFF")
    store.execute("UPDATE case_ SET run_id = 'run-deleted-forever' WHERE id LIKE 'case-orphan%'")
    store.commit()
    store.close()

    for case_id in ("case-orphan", "case-orphan-empty"):
        status, body = _get(base, f"/case/{case_id}")
        assert status == 200, f"/case/{case_id} answered HTTP {status}; the case row is still there"
        assert "/run/run-deleted-forever" not in hrefs(body), (
            f"the case page {case_id} links a run the store does not hold, so the reader lands on "
            f"a 404 (the unguarded run link the review found)")
        assert "run-deleted-forever" in body, (
            f"the case page {case_id} does not name the run it was raised by at all")
        assert "not in the store any more" in body, (
            f"the case page {case_id} does not say the run it names is gone")
        for href in internal(body):
            code, _ = _get(base, href)
            assert code == 200, f"the case page {case_id} links {href}, which returned HTTP {code}"


# --------------------------------------------------------------------------- AC4

def test_every_internal_link_on_every_page_resolves(live):
    """AC4: every internal href and every form action on every page resolves to a live address.

    The href sweep follows the crawl. The form sweep checks each ``<form action>``, because a
    button that posts to a 404 is the same dead end as a link that does (TESTOPS-54 review,
    concern 3). A POST-only address answers 405 on a GET - the address exists, the method does
    not - so a form target must be *not 404*, not necessarily 200.
    """
    frontier, seen, broken = ["/"], {"/"}, []
    pages_html: dict[str, str] = {}
    while frontier:
        path = frontier.pop(0)
        status, body = _get(live, path)
        if status != 200:
            broken.append(f"{path} (linked from another page) returned HTTP {status}")
            continue
        pages_html[path] = body
        for href in internal(body):
            if href not in seen:
                seen.add(href)
                frontier.append(href)

    kinds = {"front": "/", "runs": "/runs", "run": "/run/run-case-demo-product",
             "case": "/case/case-demo-product", "config": "/config"}
    for kind, path in kinds.items():
        status, body = _get(live, path)
        assert status == 200, f"the {kind} page returned HTTP {status}"
        pages_html.setdefault(path, body)
        for href in internal(body):
            code, _ = _get(live, href)
            if code != 200:
                broken.append(f"the {kind} page links {href}, which returned HTTP {code}")

    forms = 0
    for path, body in pages_html.items():
        for action, method in form_actions(body):
            forms += 1
            if not action.startswith("/"):
                broken.append(f"the page {path} posts a form to {action!r}, which is not this tool")
                continue
            code, _ = _get(live, action)
            if code == 404 or code >= 500:
                broken.append(f"the page {path} posts a {method} form to {action}, which returned "
                              f"HTTP {code}")

    assert forms, "no form action was found on any page; the form sweep proved nothing"
    assert not broken, "pages with dead ends:\n" + "\n".join(sorted(set(broken)))