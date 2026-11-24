"""TESTOPS-41: a file nothing read is never counted as consulted.

The finding: `collectors/github.py` held a fixed suffix list with no `.java`, so against a Java
product 142 `.java` files were dropped in silence, and the run wrote a source record whose `code`
capability was marked *observed* with 48 items - none of them product code. The page then said
"code and test code were consulted and returned 48 items".

What these tests pin, criterion by criterion:

- AC1: the collector records, per run, every file it refused, with the reason (unsupported kind,
  size cap, ignore pattern) and the kind, and never counts one as read.
- AC2: a capability is read-and-returned-items, read-and-returned-nothing, or not-readable-here.
  The three sentences differ, and `code` cannot read as observed when no product code file was
  fetched.
- AC3: a surface reader that cannot parse the language returns `not_assessable` with the language
  and the file count, and the run's stats distinguish "found none" from "could not look".
- AC4: a Java product's run page names the skipped `.java` files and says no product code file was
  fetched - proven here on an in-memory product, and against the stored restfulbooker run when the
  build store is present.
- AC5: a registry record written before this change reads back with exactly the sentence it had.
- AC6: the kind list is configuration: widening it is a data change, and whatever it holds, the
  files outside it are reported.

No test reads the network. The corpus arms read the build store read-only and skip when it is absent.
"""
from __future__ import annotations

import base64
import json
import sqlite3
from pathlib import Path

import pytest

from testops import config, pipeline, queries, sources
from testops.collectors import github
from testops.surfaces import discover as surface_discovery

ROOT = Path(__file__).resolve().parents[1]
STORED = ROOT / "data" / "testops.db"

PINNED_COTW_RUN = "cotw-levels-20261122T011316"


# --------------------------------------------------------------------------- a repository in memory

def _blob(path: str, size: int = 10, sha: str | None = None) -> dict:
    return {"type": "blob", "path": path, "size": size, "sha": sha or f"sha:{path}"}


def _fake_github(monkeypatch, entries: list[dict], texts: dict[str, str] | None = None) -> None:
    """Point the collector at an in-memory tree. Nothing here touches the network."""
    texts = texts or {}

    def get_json(url, headers=None):
        if "/git/trees/" in url:
            return {"tree": entries}
        return {"content": base64.b64encode(texts.get(url.rsplit("/", 1)[-1], "").encode()).decode()}

    monkeypatch.setattr(github, "get_json", get_json)
    monkeypatch.setattr(github.blobs, "put", lambda raw: f"blob:{raw.decode()}")


def _repo():
    return config.Repo("o", "product")


# --------------------------------------------------------------------------- AC1: what was refused

def test_the_collector_records_every_file_it_refused_with_the_reason_and_kind(monkeypatch):
    _fake_github(monkeypatch, [
        _blob("src/App.kt"),
        _blob("steps/Steps.cs"),
        _blob("features/one.feature"),
        _blob("node_modules/pkg/index.js"),
        _blob("bin/run.cs"),
        _blob("huge/big.cs", size=config.MAX_FILE_BYTES + 1),
        _blob("steps/Thing.feature.cs"),
        _blob("README"),
    ])
    collected = github.collect(_repo(), "token", commit="c" * 40, role="product")

    refused = {(entry.reason, entry.kind): entry.files for entry in collected.skipped}

    # Every way out of the tree but "fetched" is recorded, with its own reason.
    assert refused[(github.UNSUPPORTED, ".kt")] == ("src/App.kt",)
    assert refused[(github.SIZE_CAP, ".cs")] == ("huge/big.cs",)
    assert refused[(github.IGNORE, "/node_modules/")] == ("node_modules/pkg/index.js",)
    assert refused[(github.IGNORE, "/bin/")] == ("bin/run.cs",)
    assert refused[(github.IGNORE, ".feature.cs")] == ("steps/Thing.feature.cs",)
    assert refused[(github.UNSUPPORTED, "(no suffix)")] == ("README",)

    # And a file it did not read is not a file it counted.
    assert "src/App.kt" not in collected.files
    assert sum(collected.counts.values()) == len(collected.files) == 2
    assert collected.counts == {sources.TEST_CODE: 2}

    record = collected.record()
    assert {entry["kind"] for entry in record["skipped"]} >= {".kt", ".cs"}
    assert next(entry for entry in record["skipped"] if entry["kind"] == ".kt")["count"] == 1


# --------------------------------------------------------------------------- AC6: the list is data

def test_the_kind_list_is_configuration_and_whatever_it_holds_the_rest_is_reported(monkeypatch):
    entries = [_blob("src/App.kt"), _blob("src/App.scala"), _blob("steps/Steps.cs")]
    monkeypatch.setattr(github, "config", config)
    _fake_github(monkeypatch, entries)

    before = github.collect(_repo(), "token", commit="c" * 40, role="product")
    assert "src/App.kt" not in before.files
    assert {entry.kind for entry in before.skipped if entry.reason == github.UNSUPPORTED} == \
        {".kt", ".scala"}

    # Widening the list is a change to data. No collector code moves.
    widened = config.FILE_KINDS + (config.FileKind(".kt", "source"),)
    monkeypatch.setattr(config, "FILE_KINDS", widened)
    after = github.collect(_repo(), "token", commit="c" * 40, role="product")

    assert "src/App.kt" in after.files
    # The product arm's `.kt` is now product code; nothing about `.scala` stopped being reported.
    assert after.counts[sources.CODE] == 1
    assert [entry.files for entry in after.skipped if entry.kind == ".scala"] == \
        [("src/App.scala",)]


# --------------------------------------------------------------------------- AC2: three states

def _registry(code: sources.Reading, test_code: sources.Reading) -> sources.Registry:
    kind = sources.SourceKind(
        sources.GITHUB, "GitHub", (sources.CODE, sources.TEST_CODE),
        sources.SourceState(sources.AVAILABLE, readings=(code, test_code)))
    return sources.Registry([kind])


UNREAD = ("142 .java files in the product repository were skipped because .java is not a kind this "
          "collector reads (unsupported kind), so no product code file was fetched")


def test_a_capability_with_no_product_code_is_not_read_and_the_sentence_says_so():
    registry = _registry(
        sources.Reading(sources.CODE, unreadable=UNREAD),
        sources.Reading(sources.TEST_CODE, observed=48, arms={"test": 21, "product": 27}))

    assessment = registry.assess({sources.CODE, sources.TEST_CODE})

    assert assessment.state == sources.NOT_ASSESSABLE
    assert assessment.observed is None, "an unread capability must not contribute a count"
    sentence = assessment.sentence()
    assert "code was not read" in sentence
    assert "142 .java files" in sentence
    assert "no product code file was fetched" in sentence
    assert "test code was consulted and returned 48 items" in sentence
    # The source record itself distinguishes the two capabilities.
    stored = registry.record()["github"]["readings"]
    assert {entry["capability"]: entry["observed"] for entry in stored} == \
        {"code": None, "test_code": 48}
    assert registry.record()["github"]["observed"] == 48


def test_read_and_returned_nothing_is_not_the_same_finding_as_could_not_read():
    nothing = _registry(sources.Reading(sources.CODE, observed=0),
                        sources.Reading(sources.TEST_CODE, observed=4))
    zero = nothing.assess({sources.CODE})
    assert zero.state == sources.ZERO
    assert zero.sentence() == ("Assessed: code was consulted and returned nothing. That is a real "
                               "zero \u2014 there is nothing there, not that nobody looked.")

    unreadable = _registry(sources.Reading(sources.CODE, unreadable=UNREAD),
                           sources.Reading(sources.TEST_CODE, observed=4))
    cannot = unreadable.assess({sources.CODE})
    assert cannot.state == sources.NOT_ASSESSABLE
    assert cannot.sentence() != zero.sentence()
    assert "returned nothing" not in cannot.sentence()


def test_a_capability_that_could_not_be_read_never_carries_a_count():
    with pytest.raises(ValueError, match="cannot report"):
        sources.Reading(sources.CODE, observed=27, unreadable=UNREAD)


# --------------------------------------------------------------------------- AC3: surfaces

def test_a_boundary_in_a_language_the_reader_cannot_parse_is_not_assessable():
    discovery = surface_discovery.discover({
        "auth/src/main/kotlin/AuthController.kt": "class A",
        "booking/src/main/kotlin/BookingController.kt": "class B",
        "assets/src/app/page.tsx": "export default 1",
    })

    assert discovery.state == surface_discovery.NOT_ASSESSABLE
    assert discovery.surfaces == ()
    assert "Python" in discovery.reason and ".py" in discovery.reason
    assert "Java" in discovery.reason and ".java" in discovery.reason
    assert "2 .kt" in discovery.reason, discovery.reason
    record = discovery.record()
    assert record["state"] == "not_assessable" and record["surfaces"] == 0
    assert {"suffix": ".kt", "count": 2} in record["languages"]


def test_python_the_reader_did_read_and_that_holds_no_surface_is_a_real_zero():
    discovery = surface_discovery.discover({"lib/constants.py": "VALUE = 1\n"})
    assert discovery.state == surface_discovery.ZERO
    assert discovery.surfaces == ()
    assert discovery.reason == ""


# --------------------------------------------------------------------------- AC4: the run names it

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


def _levels_run(monkeypatch, tmp_path, *, product_files, product_skipped):
    """A real levels run over an in-memory pair of repositories, written to a throwaway store."""
    from testops.collectors.github import Collected
    from testops.store import db

    path = tmp_path / "t41.db"
    real_connect = db.connect
    test_arm = Collected(commit="c" * 40, role="test",
                         files={"features/one.feature": ("sha:feature", "feature"),
                                "steps/Steps.cs": ("sha:steps", "stepdef")})
    product_arm = Collected(commit="p" * 40, role="product", files=product_files,
                            skipped=product_skipped)
    arms = {"test": test_arm, "product": product_arm}

    monkeypatch.setattr(pipeline, "load_env", lambda: {})
    monkeypatch.setattr(pipeline.db, "connect", lambda: real_connect(path))
    monkeypatch.setattr(pipeline.blobs, "text", lambda sha: TEXTS[sha])
    monkeypatch.setattr(pipeline.github, "collect",
                        lambda repo, token, role="product": arms[role])

    project = config.Project("specimen", config.Repo("o", "product"),
                             config.Repo("o", "tests"), jira_key="")
    result = pipeline.run_level_fitness(project, "token")
    return result, real_connect(path)


def test_a_kotlin_product_run_says_which_files_it_skipped_and_whose_code_it_did_not_read(
        monkeypatch, tmp_path):
    skipped = (github.Skipped(github.UNSUPPORTED, ".kt",
                              tuple(f"auth/src/main/kotlin/C{number}.kt" for number in range(142))),)
    result, conn = _levels_run(monkeypatch, tmp_path, product_files={}, product_skipped=skipped)
    try:
        run = queries.run_read(conn, result.run_id)
        meta = json.loads(conn.execute("SELECT meta FROM snapshot WHERE id = ?",
                                       (result.snapshot_id,)).fetchone()["meta"])
        claims = conn.execute("SELECT COUNT(*) FROM claim WHERE run_id = ?",
                              (result.run_id,)).fetchone()[0]
    finally:
        conn.close()

    sentence = run["assessment"]["sentence"]
    assert run["assessment"]["state"] == sources.NOT_ASSESSABLE
    assert "142 .kt files" in sentence
    assert "no product code file was fetched" in sentence
    assert "test code was consulted and returned 2 files" in sentence

    # The skipped files are named in the record, not just counted.
    code = next(entry for entry in meta["sources"]["github"]["readings"]
                if entry["capability"] == "code")
    kotlin = next(entry for entry in code["skipped"] if entry["kind"] == ".kt")
    assert kotlin["count"] == 142
    assert kotlin["files"][0] == "auth/src/main/kotlin/C0.kt"

    # AC3's stats: zero surfaces, and the reason it is zero.
    assert result.stats["surfaces"] == 0
    assert result.stats["surfaces_state"] == "not_assessable"
    assert result.stats["surfaces_reason"]

    # The verdicts are a separate fact from the sources, and this ticket does not move them.
    assert claims == len(result.claims)


# --------------------------------------------------------------------------- AC5: old records

def test_a_registry_record_written_before_this_change_reads_exactly_as_it_did():
    stored = {"github": {"id": "github", "title": "GitHub",
                         "capabilities": ["code", "test_code"], "state": "available",
                         "reason": "", "blocked_by": "", "observed": 95,
                         "route": "github-api", "note": "", "order": 0}}
    registry = sources.Registry.from_record(stored)

    both = registry.assess({sources.CODE, sources.TEST_CODE})
    assert both.state == sources.FOUND
    assert both.sentence() == "Assessed: code and test code were consulted and returned 95 items."

    stored["github"].update({"observed": 158, "capabilities": ["code", "test_code"]})
    single = sources.Registry.from_record(stored).assess({sources.TEST_CODE})
    assert single.sentence() == "Assessed: test code was consulted and returned 158 items."

    assert "readings" not in sources.Registry.from_record(stored).record()["github"]


# --------------------------------------------------------------------------- AC4/AC5 on the store

# The run this probe describes. Pinned, not "the latest": TESTOPS-70 made the Java reader part of the
# surface reader, so the run after this one reads `.java` and the sentence below is history. A probe
# that silently follows the newest run stops describing the snapshot it was written for.
PINNED_RESTFULBOOKER_RUN = "restfulbooker-levels-20261123T132456"

@pytest.mark.skipif(not STORED.exists(), reason="the product store is a build artefact")
def test_the_cotw_run_still_says_ninety_five_items():
    conn = sqlite3.connect(f"file:{STORED.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        run = queries.run_read(conn, PINNED_COTW_RUN)
    finally:
        conn.close()
    assert run is not None, f"the pinned run {PINNED_COTW_RUN} is not in the store"
    assert run["assessment"]["sentence"] == \
        "Assessed: code and test code were consulted and returned 95 items."


@pytest.mark.skipif(not STORED.exists(), reason="the product store is a build artefact")
def test_the_restfulbooker_run_names_the_java_it_could_not_read():
    conn = sqlite3.connect(f"file:{STORED.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        run = queries.run_read(conn, PINNED_RESTFULBOOKER_RUN)
    finally:
        conn.close()
    assert run is not None, f"the pinned run {PINNED_RESTFULBOOKER_RUN} is not in the store"
    sentence = run["assessment"]["sentence"]
    assert "code was not read" in sentence, sentence
    assert "142 .java files" in sentence, sentence
    assert "no product code file was fetched" in sentence, sentence
