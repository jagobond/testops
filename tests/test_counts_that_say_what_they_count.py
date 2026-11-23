"""TESTOPS-55: counts that say what they count.

Two failures from the blind author, both about a reader being unable to state what exists or what
was read:

  * AC1 - the front page listed projects but never said how many, and never used the word
    "projects". A newcomer could not say what the store holds.
  * AC2 - a run page said "27 files read" per repository and listed *skipped* files by kind, but
    gave no per-kind read count and no explicit zero. "0 .js files" and "this page never mentions
    .js" were the same screen.

The counts are derived from the store at render time. These tests prove that by building real runs
through the pipeline (not hand-written rows) and by moving the store under the page and watching
the numbers follow.
"""
from __future__ import annotations

import html as htmllib
import re
import sqlite3

import pytest

from testops import blobs, config, pipeline, queries, services
from testops.collectors import github
from testops.store import db
from testops.web import app

from support_fixtures import add_v2_claim, seed_run


def _text(body) -> str:
    text = body.decode("utf-8") if isinstance(body, bytes) else body
    text = re.sub(r"(?is)<style.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return " ".join(htmllib.unescape(text).split())


def _ledger(conn) -> dict[str, int]:
    """The store's own counts, read here rather than taken from the page."""
    return {
        "projects": conn.execute(
            "SELECT COUNT(*) FROM (SELECT slug FROM project UNION SELECT project FROM run)"
        ).fetchone()[0],
        "runs": conn.execute("SELECT COUNT(*) FROM run").fetchone()[0],
        "cases": conn.execute("SELECT COUNT(*) FROM case_").fetchone()[0],
    }


def _stated(text: str, noun: str) -> int:
    """The count the page states for a noun, singular or plural - read, not assumed."""
    stem = noun[:-1] if noun.endswith("s") else noun
    found = re.search(r"\b(\d+)\s+%ss?\b" % re.escape(stem), text)
    assert found, f"the page states no count of {noun}: {text[:400]!r}"
    return int(found.group(1))


def _repository_sentence(body: bytes | str, role: str) -> str:
    """The page's one sentence saying what this role's repository gave the run."""
    markup = body.decode("utf-8") if isinstance(body, bytes) else body
    found = re.search(r"<p>From the %s repository.*?</p>" % role, markup, re.S)
    assert found, f"the page has no read sentence for the {role} repository"
    return _text(found.group(0))


# --------------------------------------------------------------------------- AC1: front totals

def _store_with_cases(tmp_path, *, projects=1, cases=2) -> sqlite3.Connection:
    conn = db.connect(tmp_path / "t55-front.db")
    run_id = seed_run(conn)
    add_v2_claim(conn, run_id)
    for number in range(projects):
        services.add_project(conn, f"project-{number}", f"Project {number}")
    for number in range(cases):
        conn.execute(
            "INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at, summary)"
            " VALUES (?,?,?,?,?,?,?)",
            (f"case-{number}", run_id, "project-0", "level_fitness", "snap-schema",
             "2020-01-01T00:00:00+00:00", "{}"))
    conn.commit()
    return conn


def test_the_front_page_states_projects_runs_and_cases_as_labelled_totals(tmp_path):
    """AC1: three counts, each carrying the noun it counts, and each equal to the store's own."""
    conn = _store_with_cases(tmp_path, projects=3, cases=4)
    try:
        page = _text(app.index(conn))
        ledger = _ledger(conn)
    finally:
        conn.close()

    for noun, actual in ledger.items():
        assert _stated(page, noun) == actual, (
            f"the front page's {noun} count is not the store's {actual}: {page[:400]!r}")


def test_the_totals_are_derived_so_they_move_when_the_store_does(tmp_path):
    """AC1/AC4: nothing is a text literal - adding to the store changes what the page states."""
    conn = _store_with_cases(tmp_path, projects=1, cases=1)
    try:
        before = _text(app.index(conn))
        ledger_before = _ledger(conn)
        services.add_project(conn, "second", "Second")
        conn.execute(
            "INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at, summary)"
            " VALUES (?,?,?,?,?,?,?)",
            ("case-second", seed_run(conn, run_id="run-second"), "second", "level_fitness",
             "snap-schema", "2020-01-02T00:00:00+00:00", "{}"))
        conn.commit()
        after = _text(app.index(conn))
        ledger = _ledger(conn)
    finally:
        conn.close()

    for noun, actual in ledger_before.items():
        assert _stated(before, noun) == actual
    for noun, actual in ledger.items():
        assert _stated(after, noun) == actual
    assert ledger["projects"] == ledger_before["projects"] + 1
    assert ledger["cases"] == ledger_before["cases"] + 1
    assert ledger["runs"] == ledger_before["runs"] + 1


# --------------------------------------------------------------------------- a real run, no network

FEATURE = """\
Feature: the guest books
  Scenario: a booking is accepted
    Then the booking is stored
"""
STEPS = """\
public class Steps {
  [Then("the booking is stored")]
  public void ThenStored() { using var client = new HttpClient(); }
}
"""
PRODUCT = "def store(booking):\n    return booking\n"
BIG = "public class Big { }\n"

TEXTS = {"sha:feature": FEATURE, "sha:steps": STEPS, "sha:product": PRODUCT, "sha:big": BIG}


def _levels_run(monkeypatch, tmp_path, *, product_files, product_skipped=()):
    """A real level-fitness run over an in-memory pair of repositories, in a throwaway store."""
    path = tmp_path / "t55-run.db"
    real_connect = db.connect
    test_arm = github.Collected(commit="c" * 40, role="test",
                                files={"features/one.feature": ("sha:feature", "feature"),
                                       "steps/Steps.cs": ("sha:steps", "stepdef")})
    product_arm = github.Collected(commit="b" * 40, role="product", files=product_files,
                                   skipped=product_skipped)
    arms = {"test": test_arm, "product": product_arm}

    monkeypatch.setattr(pipeline, "load_env", lambda: {})
    monkeypatch.setattr(pipeline.db, "connect", lambda: real_connect(path))
    monkeypatch.setattr(pipeline.blobs, "text", lambda sha: TEXTS[sha])
    monkeypatch.setattr(pipeline.github, "collect",
                        lambda repo, token, role="product": arms[role])
    monkeypatch.setattr(blobs, "BLOB_DIR", tmp_path / "blobs")

    project = config.Project("specimen", config.Repo("o", "product"),
                             config.Repo("o", "tests"), jira_key="")
    result = pipeline.run_level_fitness(project, "token")
    return result, real_connect(path)


# --------------------------------------------------------------------------- AC2: zeroes are stated

def test_a_run_page_states_a_zero_for_a_kind_the_repository_holds_none_of(monkeypatch, tmp_path):
    """AC2/AC4: a known zero of a known kind appears, in the repository's own sentence."""
    result, conn = _levels_run(monkeypatch, tmp_path,
                               product_files={"src/product.py": ("sha:product", "source")})
    try:
        body = app.run_response(conn, result.run_id)[0]
    finally:
        conn.close()

    page = _text(body)
    product_sentence = _repository_sentence(body, "product")

    assert "1 .py file" in product_sentence, product_sentence
    assert "0 .cs files" in product_sentence, product_sentence
    assert "0 .js files" in product_sentence, product_sentence
    assert "0 .feature files" in product_sentence, product_sentence


def test_every_kind_the_collector_reads_is_listed_for_every_repository(monkeypatch, tmp_path):
    """AC2: the kinds are the analyser's own list, not only the kinds that happened to appear."""
    result, conn = _levels_run(monkeypatch, tmp_path,
                               product_files={"src/product.py": ("sha:product", "source")})
    try:
        body = app.run_response(conn, result.run_id)[0]
    finally:
        conn.close()

    page = _text(body)
    for suffix in (rule.suffix for rule in config.FILE_KINDS):
        assert re.search(r"\b\d+ %s files?\b" % re.escape(suffix), page), \
            f"the run page never states a count for {suffix}"


# --------------------------------------------------------------------------- AC4: partial reads

def test_a_partially_read_kind_states_both_what_was_read_and_what_was_skipped(monkeypatch,
                                                                             tmp_path):
    """AC4: one .cs read and two refused for size - both numbers, in their own sections."""
    skipped = (github.Skipped(github.SIZE_CAP, ".cs", ("src/huge.cs", "src/huger.cs")),)
    result, conn = _levels_run(monkeypatch, tmp_path,
                               product_files={"src/read.cs": ("sha:big", "source")},
                               product_skipped=skipped)
    try:
        body = app.run_response(conn, result.run_id)[0]
    finally:
        conn.close()

    markup = body.decode("utf-8")
    page = _text(body)

    read_part = markup.split("What this run read</h2>", 1)[1].split("<h2", 1)[0]
    skip_part = markup.split("Files this run could not read</h2>", 1)[1]

    assert "1 .cs file" in _text(read_part), read_part
    assert "2 .cs" in _text(skip_part) and "size cap" in _text(skip_part), skip_part
    assert "2 .cs" not in _text(read_part)
    # The existing skipped-by-kind sentence keeps its meaning, and the sections stay distinct.
    assert "did not fetch" in page
    assert "What this run read" in page


def test_the_skipped_section_never_reads_as_a_read_count(monkeypatch, tmp_path):
    """AC3: "read 0" and "skipped 142" cannot be confused - different headings, different words."""
    skipped = (github.Skipped(github.UNSUPPORTED, ".java",
                              tuple(f"src/File{number:03d}.java" for number in range(3))),)
    result, conn = _levels_run(monkeypatch, tmp_path,
                               product_files={"src/product.py": ("sha:product", "source")},
                               product_skipped=skipped)
    try:
        body = app.run_response(conn, result.run_id)[0]
    finally:
        conn.close()

    markup = body.decode("utf-8")
    skip_part = markup.split("Files this run could not read</h2>", 1)[1]

    assert "<strong>3 .java</strong>" in skip_part
    assert "could not read" in _text(skip_part) or "did not fetch" in _text(skip_part)
    assert not re.search(r"\bit read\b", _text(skip_part)), \
        "the skipped section uses the read section's words"


# --------------------------------------------------------------------------- an older snapshot

def test_a_snapshot_that_recorded_no_reads_renders_no_read_counts(tmp_path):
    """Silence, not zeroes: a run that never recorded reads cannot say what it read."""
    conn = db.connect(tmp_path / "t55-legacy.db")
    try:
        run_id = seed_run(conn)
        assert queries.read_counts(conn, "snap-schema", None) is None
        assert queries.read_counts(conn, None, {"product": {"commit": "b" * 40}}) is None
        assert "What this run read" not in _text(app.run_response(conn, run_id)[0])
    finally:
        conn.close()
