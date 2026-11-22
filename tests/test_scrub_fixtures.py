"""TESTOPS-35 AC1: fixtures leave the store by a documented, re-runnable command.

The store in these tests is built the way the live one was corrupted: one case a registered
analyser raised, and one case a review harness wrote under an analyser name no build has. What is
asserted is the asymmetry - the command reports everything and removes only the fixture, only with
``--yes``, and leaves the evidence the fixture borrowed (run, snapshot, claims) exactly where it
was.
"""
from __future__ import annotations

from testops import analysers, cli, scrub
from testops.store import db

TS = "2026-11-22T09:04:39+00:00"
SNAP = "snap-scrub"
RUN = "run-scrub"
REAL_CASE = "case-real-01"
FIXTURE_CASE = "rev-duplicate"
REAL_FP = "a" * 32
FIXTURE_FP = "b" * 32


def _store(tmp_path):
    conn = db.connect(tmp_path / "scrub.db")
    db.upsert_snapshot(conn, SNAP, "fixture", TS, {"o/test": "c" * 40}, schema_version=2)
    db.start_run(conn, RUN, "fixture", SNAP, "level_fitness", TS)
    claim = db.add_claim(conn, RUN, "level_fitness", "0.10.2", "scenario:f.feature#a step",
                         "The test asserts a step.", "gap", 0.5, [], schema_version=1)
    for case_id, analyser, fingerprint in ((REAL_CASE, "level_fitness", REAL_FP),
                                           (FIXTURE_CASE, "x", FIXTURE_FP)):
        conn.execute("INSERT INTO case_ (id, run_id, project, analyser, snapshot_id, created_at,"
                     " summary) VALUES (?,?,?,?,?,?,?)",
                     (case_id, RUN, "fixture", analyser, SNAP, TS, "{}"))
        conn.execute("INSERT INTO finding (case_id, title, severity, fingerprint, claim_ids)"
                     " VALUES (?,?,?,?,?)", (case_id, "t", "high", fingerprint, db.j([claim])))
    conn.execute("INSERT INTO case_state (case_id, state, actor, at, note) VALUES (?,?,?,?,?)",
                 (FIXTURE_CASE, "resolved", "reviewer", TS, "fixture decision"))
    for fingerprint in (REAL_FP, FIXTURE_FP):
        conn.execute("INSERT INTO suppression (fingerprint, state, actor, at, note)"
                     " VALUES (?,?,?,?,?)", (fingerprint, "resolved", "harry", TS, ""))
    conn.commit()
    return conn, claim


def _rows(conn, table, where="1=1", args=()):
    return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", args).fetchone()[0]


def test_plan_finds_only_the_unregistered_case(tmp_path):
    conn, _ = _store(tmp_path)
    try:
        found = scrub.plan(conn)
        assert [case["id"] for case in found["cases"]] == [FIXTURE_CASE]
        assert found["cases"][0]["analyser"] == "x"
        assert found["counts"] == {"case_": 1, "finding": 1, "case_state": 1, "suppression": 1}
        # Only the fixture's own suppression goes: the real finding's decision is untouched.
        assert found["suppression_fingerprints"] == [FIXTURE_FP]
    finally:
        conn.close()


def test_dry_run_removes_nothing(tmp_path):
    conn, _ = _store(tmp_path)
    try:
        result = scrub.scrub(conn, yes=False)
        assert result["removed"] is None
        assert _rows(conn, "case_") == 2
        assert _rows(conn, "finding") == 2
        assert _rows(conn, "case_state") == 1
        assert _rows(conn, "suppression") == 2
    finally:
        conn.close()


def test_yes_removes_the_case_and_keeps_the_evidence(tmp_path):
    conn, claim = _store(tmp_path)
    try:
        before = scrub.totals(conn)
        result = scrub.scrub(conn, yes=True)
        assert result["removed"] == {"suppression": 1, "finding": 1, "case_state": 1, "case_": 1}
        # The fixture and its rows are gone; nothing else is.
        assert conn.execute("SELECT 1 FROM case_ WHERE id = ?", (FIXTURE_CASE,)).fetchone() is None
        assert conn.execute("SELECT 1 FROM case_ WHERE id = ?", (REAL_CASE,)).fetchone() is not None
        assert _rows(conn, "finding") == 1
        assert _rows(conn, "case_state") == 0
        assert _rows(conn, "suppression", "fingerprint = ?", (REAL_FP,)) == 1
        assert _rows(conn, "suppression") == 1
        # The run, snapshot and claim it borrowed are untouched - deleting them would destroy the
        # evidence the real case rests on.
        after = result["totals_after"]
        for table in ("snapshot", "artefact", "observation", "run", "claim", "inference"):
            assert after[table] == before[table], table
        assert conn.execute("SELECT 1 FROM claim WHERE id = ?", (claim,)).fetchone() is not None
        # Re-runnable: a second run finds nothing and removes nothing.
        again = scrub.scrub(conn, yes=True)
        assert again["plan"]["cases"] == []
        assert again["removed"] == {"suppression": 0, "finding": 0, "case_state": 0, "case_": 0}
    finally:
        conn.close()


def test_cli_prints_ids_and_counts_before_any_removal(tmp_path, monkeypatch, capsys):
    conn, _ = _store(tmp_path)
    db_file = tmp_path / "scrub.db"
    conn.close()
    monkeypatch.setattr(cli, "DB_PATH", db_file)
    # A fresh connection per call: the command opens and closes its own, as it does in production.
    monkeypatch.setattr(cli.db, "connect", lambda: _reopen(db_file))
    assert cli.main(["scrub-fixtures", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert FIXTURE_CASE in out
    assert "analyser='x'" in out
    assert "finding 2 fingerprint " + FIXTURE_FP in out
    assert "case_ 1" in out and "finding 1" in out and "case_state 1" in out
    assert "suppression 1" in out
    assert "Dry run" in out
    assert _rows(_reopen(db_file), "case_") == 2

    assert cli.main(["scrub-fixtures", "--yes"]) == 0
    out = capsys.readouterr().out
    assert "removed suppression 1 · finding 1 · case_state 1 · case_ 1" in out
    assert "fixture cases remaining: 0" in out
    after = _reopen(db_file)
    assert _rows(after, "case_") == 1
    assert _rows(after, "finding") == 1
    after.close()


def _reopen(path):
    """A fresh connection to the same file, because ``cmd_scrub_fixtures`` closes its own."""
    import sqlite3

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def test_cli_refuses_contradictory_flags(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "DB_PATH", tmp_path / "missing.db")
    assert cli.main(["scrub-fixtures", "--dry-run", "--yes"]) == 2
    assert "contradictory" in capsys.readouterr().out


def test_cli_does_not_create_a_missing_store(tmp_path, monkeypatch, capsys):
    """A scrub against a store that is not there must not conjure one and call it clean."""
    missing = tmp_path / "absent" / "testops.db"
    monkeypatch.setattr(cli, "DB_PATH", missing)
    assert cli.main(["scrub-fixtures", "--yes"]) == 1
    assert "no store at" in capsys.readouterr().out
    assert not missing.exists()


def test_registered_analysers_are_the_runs_own_names():
    assert analysers.registered_names() == {"duplication", "level_fitness"}
    assert not analysers.is_registered("x")
    assert not analysers.is_registered(None)
