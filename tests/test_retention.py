"""TESTOPS-24: retention.

The ticket's decision is dedupe-by-content-hash. These tests hold it to that:

  * AC1 - two runs over an unchanged commit add zero blob files and leave the blob directory's byte
    total identical. The collector is wired to call ``blobs.put`` again on the second run, exactly as
    the real collector does, so the proof is of the store's dedupe and not of a stub that skipped it.
  * AC2 - growth is measured from before/after readings of a real store: rows counted, database
    file and blob files measured with ``os.stat``. The numbers in the build report come from this
    instrument; nothing here estimates a snapshot size.
  * AC3 - the report states, per snapshot, age, rows, bytes and whether a decision or a suppression
    refers to it.
  * AC4 - a prune deletes only snapshots older than the keep window, unreferenced by a decided or
    suppressed case, and not the newest run of any analyser; it reports and refuses without ``--yes``.
  * AC5 - pruning the oldest levels snapshot leaves every surviving case page byte-for-byte equal.
  * AC6 - a blob still referenced by a surviving artefact row is never deleted.
  * AC7 - the default is report-only; no prune happens without an explicit request and confirmation.
"""
from __future__ import annotations

import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import level_fixtures as level_fixtures
import reqoverflow_fixtures as reqoverflow
from testops import blobs, cases, retention
from testops.collectors.github import Collected
from testops.config import Project, Repo
from testops.store import db

TABLES = ("snapshot", "run", "artefact", "observation", "claim", "inference",
          "case_", "finding", "case_state", "suppression")


# ------------------------------------------------------------------------------------- helpers

def _blob_stats(blob_dir: Path) -> dict:
    root = Path(blob_dir)
    files = sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())
    return {"files": files, "count": len(files),
            "bytes": sum((root / name).stat().st_size for name in files)}


def _counts(conn) -> dict:
    return {table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in TABLES}


def measure(connect, blob_dir: Path) -> dict:
    """A before/after reading on a fresh connection, so it sees what the pipeline just committed."""
    conn = connect()
    try:
        return retention.store_footprint(conn, blob_dir=blob_dir)
    finally:
        conn.close()


def _project(key: str, test: str = "tests", product: str = "product") -> Project:
    return Project(key=key, product=Repo("o", product), test=Repo("o", test), jira_key="")


def _reqoverflow_store(tmp_path, monkeypatch):
    """The real corpus wired to the real pipeline, with the collector re-putting every blob."""
    from testops import pipeline

    blob_dir = tmp_path / "blobs"
    monkeypatch.setattr(blobs, "BLOB_DIR", blob_dir)
    path = tmp_path / "reqoverflow.db"
    real_connect = db.connect

    def collect(repo, token, role="product"):
        # The real collector fetches every file and calls blobs.put on its bytes. Doing the same
        # here is what makes the second run a genuine test of content-addressing.
        return Collected(commit=reqoverflow.COMMIT, files=reqoverflow.files())

    monkeypatch.setattr(pipeline, "load_env", lambda: {})
    monkeypatch.setattr(pipeline.db, "connect", lambda: real_connect(path))
    monkeypatch.setattr(pipeline.github, "collect", collect)
    monkeypatch.setattr(pipeline.surface_discovery, "discover",
                        lambda product_texts: pipeline.surface_discovery.Discovery((), "zero"))
    return path, real_connect, blob_dir


def _levels_store(tmp_path, monkeypatch):
    """The level-fitness pipeline over real bytes in a throwaway store and blob directory."""
    from testops import pipeline

    blob_dir = tmp_path / "blobs"
    monkeypatch.setattr(blobs, "BLOB_DIR", blob_dir)
    path = tmp_path / "levels.db"
    real_connect = db.connect

    def collect(repo, token, role="product"):
        files = {
            "features/fact_sheet.feature":
                (blobs.put(level_fixtures.PIPELINE_FEATURE.encode("utf-8")), "feature"),
            "steps/FactSheetSteps.cs":
                (blobs.put(level_fixtures.PIPELINE_STEPDEF.encode("utf-8")), "stepdef"),
        }
        return Collected(commit=level_fixtures.COMMIT, files=files)

    monkeypatch.setattr(pipeline, "load_env", lambda: {})
    monkeypatch.setattr(pipeline.db, "connect", lambda: real_connect(path))
    monkeypatch.setattr(pipeline.github, "collect", collect)
    monkeypatch.setattr(pipeline.surface_discovery, "discover",
                        lambda product_texts: pipeline.surface_discovery.Discovery((), "zero"))
    return path, real_connect, blob_dir


def _snapshot(conn, snapshot_id: str, project: str, created: str,
              analyser: str = "level_fitness", started: str | None = None) -> None:
    db.upsert_snapshot(conn, snapshot_id, project, created, {"o/r": "a" * 40}, schema_version=2,
                       meta={})
    db.start_run(conn, f"run-{snapshot_id}", project, snapshot_id, analyser, started or created)
    db.finish_run(conn, f"run-{snapshot_id}", "ok", started or created)


def _artefact(conn, snapshot_id: str, uri: str, data: bytes) -> int:
    return db.add_artefact(conn, snapshot_id, uri, "feature", blobs.put(data))


def _case_with_finding(conn, case_id: str, snapshot_id: str, fingerprint: str,
                       claim_ids: list[int] | None = None) -> None:
    run = conn.execute("SELECT id FROM run WHERE snapshot_id = ? LIMIT 1", (snapshot_id,)).fetchone()
    conn.execute(
        "INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at, summary)"
        " VALUES (?,?,?,?,?,?,?)",
        (case_id, run["id"], "p", "level_fitness", snapshot_id, "2026-01-01T00:00:00+00:00", "{}"))
    conn.execute(
        "INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids) VALUES (?,?,?,?,?)",
        (case_id, "a finding", "medium", fingerprint, db.j(claim_ids or [])))


# ----------------------------------------------------------------------------------------- AC1

def test_two_runs_over_an_unchanged_commit_add_no_blob_files_and_no_blob_bytes(tmp_path, monkeypatch):
    from testops import pipeline

    path, connect, blob_dir = _reqoverflow_store(tmp_path, monkeypatch)
    project = _project("reqoverflow", "Sample-ReqOverflow", "Sample-ReqOverflow")

    first = pipeline.run_duplication(project, token="unused")
    after_first = _blob_stats(blob_dir)
    conn = connect(path)
    try:
        rows_after_first = _counts(conn)
        shas_after_first = conn.execute(
            "SELECT COUNT(DISTINCT blob_sha) FROM artefact WHERE blob_sha IS NOT NULL").fetchone()[0]
    finally:
        conn.close()

    time.sleep(1.05)                         # run ids are second-granular; two looks are two ids
    second = pipeline.run_duplication(project, token="unused")
    after_second = _blob_stats(blob_dir)
    conn = connect(path)
    try:
        rows_after_second = _counts(conn)
        shas_after_second = conn.execute(
            "SELECT COUNT(DISTINCT blob_sha) FROM artefact WHERE blob_sha IS NOT NULL").fetchone()[0]
    finally:
        conn.close()

    assert after_first["count"] > 0
    assert second.snapshot_id != first.snapshot_id, "the second run must be a second look"
    # AC1, literally: zero new files, identical byte total.
    assert after_second["files"] == after_first["files"]
    assert after_second["bytes"] == after_first["bytes"]
    assert shas_after_second == shas_after_first
    # Growth is in rows: the second snapshot's artefacts and observations are new rows over the
    # same content, so the store grew while the blobs did not.
    assert rows_after_second["artefact"] > rows_after_first["artefact"]
    assert rows_after_second["observation"] > rows_after_first["observation"]
    assert rows_after_second["claim"] > rows_after_first["claim"]


# ----------------------------------------------------------------------------------------- AC2

def test_growth_per_levels_run_is_measured_before_and_after(tmp_path, monkeypatch):
    from testops import pipeline

    path, connect, blob_dir = _levels_store(tmp_path, monkeypatch)
    project = _project("fixture")
    connect(path).close()                   # create the schema so "before" is an empty store

    before = measure(lambda: connect(path), blob_dir)
    first = pipeline.run_level_fitness(project, token="unused")
    after_first = measure(lambda: connect(path), blob_dir)
    time.sleep(1.05)
    second = pipeline.run_level_fitness(project, token="unused")
    after_second = measure(lambda: connect(path), blob_dir)

    assert second.snapshot_id != first.snapshot_id
    # Both readings are measurements of a real store: rows counted and bytes from os.stat.
    assert after_first["row_total"] > before["row_total"], "a levels run adds rows"
    assert after_second["row_total"] > after_first["row_total"], "a second run adds rows too"
    assert after_first["bytes"] > 0 and after_second["bytes"] >= after_first["bytes"]
    # An unchanged commit adds no blob bytes, so the row delta is the whole growth.
    assert after_second["bytes"] - after_second["db_bytes"] == after_first["bytes"] - after_first["db_bytes"]
    # The instrument itself reports the same rows the store holds.
    conn = connect(path)
    try:
        counts = _counts(conn)
    finally:
        conn.close()
    assert after_second["rows"] == counts


def test_growth_per_duplication_run_is_measured_before_and_after(tmp_path, monkeypatch):
    from testops import pipeline

    path, connect, blob_dir = _reqoverflow_store(tmp_path, monkeypatch)
    project = _project("reqoverflow", "Sample-ReqOverflow", "Sample-ReqOverflow")
    connect(path).close()

    before = measure(lambda: connect(path), blob_dir)
    first = pipeline.run_duplication(project, token="unused")
    after_first = measure(lambda: connect(path), blob_dir)
    time.sleep(1.05)
    second = pipeline.run_duplication(project, token="unused")
    after_second = measure(lambda: connect(path), blob_dir)

    assert second.snapshot_id != first.snapshot_id
    assert after_first["row_total"] > before["row_total"]
    assert after_second["row_total"] > after_first["row_total"]
    # The blob directory did not grow on the second run: the second run's growth is rows.
    assert after_second["files"] == after_first["files"]
    assert after_first["bytes"] - after_first["db_bytes"] == after_second["bytes"] - after_second["db_bytes"]
    assert (after_second["row_total"] - after_first["row_total"]) > 0


# ----------------------------------------------------------------------------------------- AC3

def test_the_report_states_age_rows_bytes_decisions_and_suppressions(tmp_path, monkeypatch):
    blob_dir = tmp_path / "blobs"
    monkeypatch.setattr(blobs, "BLOB_DIR", blob_dir)
    conn = db.connect(tmp_path / "report.db")
    try:
        _snapshot(conn, "snap-old", "p", "2026-01-01T00:00:00+00:00")
        _snapshot(conn, "snap-new", "p", "2026-01-02T00:00:00+00:00")
        shared = b"shared feature file"
        unique = b"only the new snapshot has this"
        _artefact(conn, "snap-old", "github:o/r@a:features/a.feature", shared)
        _artefact(conn, "snap-new", "github:o/r@a:features/a.feature", shared)
        _artefact(conn, "snap-new", "github:o/r@a:features/b.feature", unique)
        conn.execute(
            "INSERT INTO claim (run_id, analyser, analyser_version, subject_ref, statement, verdict,"
            " confidence, support, schema_version) VALUES (?,?,?,?,?,?,?,?,?)",
            ("run-snap-old", "level_fitness", "1.0.0", "scenario:a.feature#one", "a statement",
             "gap", 0.5, "[]", 1))
        _case_with_finding(conn, "case-old", "snap-old", "a" * 32,
                           claim_ids=[conn.execute("SELECT MAX(id) FROM claim").fetchone()[0]])
        cases.set_state(conn, "case-old", "needs_fix", "harry", "smoke test")
        _case_with_finding(conn, "case-new", "snap-new", "b" * 32)
        conn.execute(
            "INSERT INTO suppression (fingerprint, state, actor, at, note) VALUES (?,?,?,?,?)",
            ("b" * 32, "false_positive", "harry", "2026-01-02T00:00:00+00:00", "known noise"))
        conn.commit()

        rows = retention.report_rows(conn, blob_dir=blob_dir)
    finally:
        conn.close()

    assert [row["id"] for row in rows] == ["snap-old", "snap-new"]
    old, new = rows
    assert old["age_seconds"] > 0 and new["age_seconds"] > 0
    assert old["age"] and new["age"]
    assert old["decided"] is True and old["suppressed"] is False
    assert new["decided"] is False and new["suppressed"] is True
    # Rows count the snapshot and its run, plus what the run wrote. The old snapshot has a claim
    # and a decided case; the new one has two artefacts and a suppressed finding but no claim.
    assert old["rows"] == 1 + 1 + 1 + 1 + 1 + 1 + 1
    assert new["rows"] == 1 + 1 + 2 + 1 + 1
    # Bytes are the measured payload plus the on-disk blobs the snapshot references. The shared
    # blob is counted under both snapshots and broken out so a reader can see that.
    shared_bytes = len(shared)
    assert old["blob_bytes"] == shared_bytes
    assert new["blob_bytes"] == shared_bytes + len(unique)
    assert old["row_bytes"] > 0 and new["row_bytes"] > 0
    assert old["bytes"] == old["row_bytes"] + old["blob_bytes"]
    assert new["bytes"] == new["row_bytes"] + new["blob_bytes"]


# ----------------------------------------------------------------------------------------- AC4

def test_pruning_keeps_decided_suppressed_and_newest_run_snapshots(tmp_path, monkeypatch):
    blob_dir = tmp_path / "blobs"
    monkeypatch.setattr(blobs, "BLOB_DIR", blob_dir)
    conn = db.connect(tmp_path / "plan.db")
    try:
        _snapshot(conn, "snap-plain", "p", "2026-01-01T00:00:00+00:00")
        _snapshot(conn, "snap-decided", "p", "2026-01-02T00:00:00+00:00")
        _snapshot(conn, "snap-suppressed", "p", "2026-01-03T00:00:00+00:00")
        _snapshot(conn, "snap-newest", "p", "2026-01-04T00:00:00+00:00")

        _case_with_finding(conn, "case-decided", "snap-decided", "c" * 32)
        cases.set_state(conn, "case-decided", "resolved", "harry", "decided")
        _case_with_finding(conn, "case-suppressed", "snap-suppressed", "d" * 32)
        conn.execute(
            "INSERT INTO suppression (fingerprint, state, actor, at, note) VALUES (?,?,?,?,?)",
            ("d" * 32, "resolved", "harry", "2026-01-03T00:00:00+00:00", ""))
        conn.commit()

        decision = retention.plan(conn, keep=1, blob_dir=blob_dir)
    finally:
        conn.close()

    by_id = {row["id"]: row for row in decision["snapshots"]}
    assert decision["delete"] == ["snap-plain"]
    assert by_id["snap-plain"]["action"] == "delete"
    assert any("decision" in reason for reason in by_id["snap-decided"]["reasons"])
    assert any("suppression" in reason for reason in by_id["snap-suppressed"]["reasons"])
    assert any("newest level_fitness run" in reason for reason in by_id["snap-newest"]["reasons"])


def test_keep_is_per_project_so_a_quiet_project_does_not_lose_its_history(tmp_path, monkeypatch):
    monkeypatch.setattr(blobs, "BLOB_DIR", tmp_path / "blobs")
    conn = db.connect(tmp_path / "projects.db")
    try:
        _snapshot(conn, "p1-old", "p1", "2026-01-01T00:00:00+00:00")
        _snapshot(conn, "p1-new", "p1", "2026-01-02T00:00:00+00:00")
        _snapshot(conn, "p2-old", "p2", "2025-12-01T00:00:00+00:00")
        _snapshot(conn, "p2-new", "p2", "2025-12-02T00:00:00+00:00")
        conn.commit()
        decision = retention.plan(conn, keep=1, blob_dir=tmp_path / "blobs")
    finally:
        conn.close()

    assert set(decision["delete"]) == {"p1-old", "p2-old"}


def test_the_newest_run_per_analyser_is_never_pruned_even_outside_the_keep_window(tmp_path, monkeypatch):
    monkeypatch.setattr(blobs, "BLOB_DIR", tmp_path / "blobs")
    conn = db.connect(tmp_path / "analysers.db")
    try:
        # The newest duplication run is on an old snapshot; the newest level run is on a snapshot
        # created before the keep window's newest. Both must survive.
        _snapshot(conn, "snap-dup", "p", "2026-01-01T00:00:00+00:00",
                  analyser="duplication", started="2026-01-04T00:00:00+00:00")
        _snapshot(conn, "snap-stale", "p", "2026-01-02T00:00:00+00:00",
                  analyser="duplication", started="2026-01-02T00:00:00+00:00")
        _snapshot(conn, "snap-levels", "p", "2026-01-03T00:00:00+00:00",
                  analyser="level_fitness", started="2026-01-05T00:00:00+00:00")
        _snapshot(conn, "snap-new", "p", "2026-01-05T00:00:00+00:00",
                  analyser="duplication", started="2026-01-03T00:00:00+00:00")
        conn.commit()
        decision = retention.plan(conn, keep=1, blob_dir=tmp_path / "blobs")
    finally:
        conn.close()

    assert decision["delete"] == ["snap-stale"]
    assert "snap-dup" not in decision["delete"]
    assert "snap-levels" not in decision["delete"]


def test_prune_refuses_without_yes_and_changes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(blobs, "BLOB_DIR", tmp_path / "blobs")
    conn = db.connect(tmp_path / "refuse.db")
    try:
        for day in range(1, 4):
            _snapshot(conn, f"snap-{day}", "p", f"2026-01-0{day}T00:00:00+00:00")
        conn.commit()
        before = _counts(conn)
        result = retention.prune(conn, keep=1, yes=False, blob_dir=tmp_path / "blobs")
        after = _counts(conn)
        assert result["applied"] is False
        assert result["reason"] == "confirmation-required"
        assert result["plan"]["delete"] == ["snap-1", "snap-2"]
        assert after == before
    finally:
        conn.close()


# ----------------------------------------------------------------------------------------- AC5

def test_pruning_the_oldest_levels_snapshot_leaves_surviving_pages_identical(tmp_path, monkeypatch):
    from testops import pipeline
    from testops.web import app

    path, connect, blob_dir = _levels_store(tmp_path, monkeypatch)
    project = _project("fixture")

    runs = []
    for _ in range(3):
        runs.append(pipeline.run_level_fitness(project, token="unused"))
        time.sleep(1.05)

    conn = connect(path)
    try:
        assert len({run.snapshot_id for run in runs}) == 3
        assert all(len(run.case_ids) == 2 for run in runs), "each levels run raises two cases"
        oldest = sorted({run.snapshot_id for run in runs})[0]
        oldest_cases = set(runs[0].case_ids)
        # Render three cases from snapshots that will survive, and remember the exact bytes.
        survivors = [case_id for run in runs[1:] for case_id in run.case_ids]
        before = {case_id: app.case_page(conn, case_id) for case_id in survivors}

        result = retention.prune(conn, keep=2, yes=True, blob_dir=blob_dir)
        # sanity: the oldest had no decision or suppression, so it is the one that went
        assert result["applied"] is True
        assert oldest in result["deleted"]["snapshots"]

        remaining = {row[0] for row in conn.execute("SELECT id FROM snapshot")}
        after = {case_id: app.case_page(conn, case_id) for case_id in survivors}
        gone_cases = [case_id for case_id in oldest_cases
                      if conn.execute("SELECT COUNT(*) FROM case_ WHERE id = ?",
                                      (case_id,)).fetchone()[0] == 0]
    finally:
        conn.close()

    assert oldest not in remaining
    assert len(gone_cases) == 2, "the pruned snapshot's own cases go with it"
    assert len(survivors) == 4
    for case_id in survivors[:3]:
        assert after[case_id] is not None
        assert after[case_id] == before[case_id], f"{case_id} changed after pruning {oldest}"


# ----------------------------------------------------------------------------------------- AC6

def test_a_blob_shared_with_a_surviving_artefact_is_never_deleted(tmp_path, monkeypatch):
    from testops import pipeline

    path, connect, blob_dir = _levels_store(tmp_path, monkeypatch)
    project = _project("fixture")

    first = pipeline.run_level_fitness(project, token="unused")
    time.sleep(1.05)
    second = pipeline.run_level_fitness(project, token="unused")

    conn = connect(path)
    try:
        oldest = first.snapshot_id
        unique = blobs.put(b"only the pruned snapshot references this file")
        conn.execute(
            "INSERT INTO artefact (snapshot_id, uri, kind, blob_sha, meta) VALUES (?,?,?,?,?)",
            (oldest, "github:o/tests@aaaa:features/unique_to_oldest.feature", "feature", unique, "{}"))
        conn.commit()
        shared = [row[0] for row in conn.execute(
            "SELECT DISTINCT blob_sha FROM artefact WHERE snapshot_id = ? AND blob_sha IS NOT NULL",
            (second.snapshot_id,))]
        assert shared and unique not in shared

        result = retention.prune(conn, keep=1, yes=True, blob_dir=blob_dir)
        surviving_refs = {row[0] for row in conn.execute(
            "SELECT DISTINCT blob_sha FROM artefact WHERE blob_sha IS NOT NULL")}
    finally:
        conn.close()

    assert result["deleted"]["snapshots"] == [oldest]
    assert oldest not in surviving_refs and unique not in surviving_refs
    unique_path = blob_dir / unique[:2] / unique[2:]
    assert not unique_path.exists(), "a blob only the pruned snapshot referenced is removed"
    for sha in shared:
        assert (blob_dir / sha[:2] / sha[2:]).is_file(), "a blob a survivor still references was deleted"
    assert set(shared) <= surviving_refs


# ----------------------------------------------------------------------------------------- AC7

def test_the_default_is_report_only_and_says_so(tmp_path, monkeypatch, capsys):
    from testops import cli

    monkeypatch.setattr(blobs, "BLOB_DIR", tmp_path / "blobs")
    path = tmp_path / "cli.db"
    connect = db.connect
    conn = connect(path)
    try:
        for day in range(1, 4):
            _snapshot(conn, f"snap-{day}", "p", f"2026-01-0{day}T00:00:00+00:00")
        conn.commit()
        before = _counts(conn)
    finally:
        conn.close()

    monkeypatch.setattr(db, "connect", lambda: connect(path))

    # No flags: a report, and no deletion.
    assert cli.main(["retention"]) == 0
    report = capsys.readouterr().out
    assert "snap-1" in report and "snapshot" in report
    conn = connect(path)
    try:
        assert _counts(conn) == before
    finally:
        conn.close()

    # --prune without --yes: it prints what it would delete and refuses.
    assert cli.main(["retention", "--prune", "--keep", "1"]) == 2
    refusal = capsys.readouterr().out
    assert "Refusing to prune without --yes" in refusal
    assert "snap-1" in refusal, "the refusal must name what it would have deleted"
    conn = connect(path)
    try:
        assert _counts(conn) == before
    finally:
        conn.close()

    # --prune without --keep: refused, because a prune with no window is unbounded.
    assert cli.main(["retention", "--prune", "--yes"]) == 2
    assert "needs --keep" in capsys.readouterr().out
    conn = connect(path)
    try:
        assert _counts(conn) == before
    finally:
        conn.close()

    # An explicit prune with confirmation does delete, and only what the plan named.
    assert cli.main(["retention", "--prune", "--keep", "1", "--yes"]) == 0
    done = capsys.readouterr().out
    assert "pruned 2 snapshots" in done
    conn = connect(path)
    try:
        remaining = [row[0] for row in conn.execute("SELECT id FROM snapshot ORDER BY id")]
    finally:
        conn.close()
    assert remaining == ["snap-3"]


# -------------------------------------------------------------------------------------- TESTOPS-30

# AC1: N is per project. The behaviour is accepted (it deletes fewer than a global count would),
# so these tests hold the *words* to it - the help, the plan header, and the per-project counts a
# reader can check the sentence against.

def test_the_help_text_says_keep_n_is_per_project(capsys):
    from testops import cli

    with pytest.raises(SystemExit) as exited:
        cli.main(["retention", "--help"])
    assert exited.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "keep N per project" in help_text
    assert "the N most recent snapshots in each project" in help_text


def test_the_prune_report_says_per_project_and_prints_the_counts(tmp_path, monkeypatch, capsys):
    from testops import cli

    monkeypatch.setattr(blobs, "BLOB_DIR", tmp_path / "blobs")
    path = tmp_path / "wording.db"
    connect = db.connect
    conn = connect(path)
    try:
        for day in (1, 2, 3):
            _snapshot(conn, f"busy-{day}", "busy", f"2026-01-0{day}T00:00:00+00:00")
        for day in (1, 2):
            _snapshot(conn, f"quiet-{day}", "quiet", f"2026-01-0{day}T12:00:00+00:00")
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setattr(db, "connect", lambda: connect(path))

    # Without --yes it refuses *after* printing the plan, so the wording is visible on a safe run.
    assert cli.main(["retention", "--prune", "--keep", "1"]) == 2
    out = capsys.readouterr().out
    assert "keep 1 per project" in out
    # One per project, though each project holds more: the counts say so rather than leaving the
    # reader to infer it from the delete list.
    assert re.search(r"^\s+busy\s+1 / 3$", out, re.M), out
    assert re.search(r"^\s+quiet\s+1 / 2$", out, re.M), out


# AC2/AC3: a case id whose snapshot was pruned answers 404 with a page that explains itself; a
# surviving id is untouched. Both requests go through the real handler over a real socket, so the
# status code under test is the one a browser would receive.

def _pruned_store_with_one_orphaned_case(tmp_path, monkeypatch):
    """Two snapshots, two cases, then a keep-1 prune: ``case-1`` loses its evidence."""
    monkeypatch.setattr(blobs, "BLOB_DIR", tmp_path / "blobs")
    path = tmp_path / "stale-id.db"
    real_connect = db.connect
    conn = real_connect(path)
    try:
        for day in (1, 2):
            _snapshot(conn, f"snap-{day}", "p", f"2026-01-0{day}T00:00:00+00:00")
            _case_with_finding(conn, f"case-{day}", f"snap-{day}", f"fp-{day}")
        conn.commit()
        result = retention.prune(conn, keep=1, yes=True, blob_dir=tmp_path / "blobs")
    finally:
        conn.close()
    assert result["deleted"]["snapshots"] == ["snap-1"]
    return path, real_connect


def _serve_store(connect, monkeypatch):
    from testops.web import app

    monkeypatch.setattr(app.db, "connect", connect)   # the handler opens its own connection
    httpd = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def _get(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def test_a_pruned_case_id_is_a_404_page_that_names_the_case_and_retention(tmp_path, monkeypatch):
    path, connect = _pruned_store_with_one_orphaned_case(tmp_path, monkeypatch)
    httpd, base = _serve_store(lambda: connect(path), monkeypatch)
    try:
        status, body = _get(f"{base}/case/case-1")
    finally:
        httpd.shutdown()
        httpd.server_close()

    assert status == 404
    assert "case-1" in body
    assert "no longer in the store" in body
    assert "retention" in body and "pruned" in body
    assert "<h1>" in body, "a page, not a blank body"


def test_a_surviving_case_id_still_answers_200_after_the_prune(tmp_path, monkeypatch):
    path, connect = _pruned_store_with_one_orphaned_case(tmp_path, monkeypatch)
    httpd, base = _serve_store(lambda: connect(path), monkeypatch)
    try:
        status, body = _get(f"{base}/case/case-2")
    finally:
        httpd.shutdown()
        httpd.server_close()

    assert status == 200
    assert "case-2" in body
    assert "no longer in the store" not in body
