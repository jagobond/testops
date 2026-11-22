"""TESTOPS-45/46: the store's verdict guard has two levels, and they answer different questions.

TESTOPS-45 added the guard. TESTOPS-46 found that it asked a live-run question of a restore: a
retired name (``optimal``) carried by ``INSERT INTO claim SELECT ...`` out of an older store was
refused, so a store could not be rebuilt from its own history. The fix keeps two jobs apart:

* the database accepts any name this product has *ever* emitted on INSERT - current or retired -
  because restoring history is not writing history;
* the code accepts only names *current today*: ``verdicts.validate_verdict`` (called by
  ``db.add_claim``) refuses a retired name, and an UPDATE of a stored verdict is held to the
  current set too, because that is a rewrite of evidence rather than a restore.

These tests write by direct SQL, not through ``db.add_claim``, because a guard only the repository
honours is a guard the next connector skips. The one place the analyser path is exercised is AC3,
where the point is that it is *stricter* than the trigger.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

from support_fixtures import seed_run
from test_verdict_vocabulary import (claim_docstring_verdicts, claim_field_verdicts, disagreement,
                                     emitted_verdicts, schema_verdicts)
from testops import cli
from testops.store import db, verdicts
from testops.web import app

TS = "2026-11-22T00:00:00+00:00"
RETIRED = {"optimal": 36, "overbuilt": 67, "necessary": 25}
UNKNOWN = "total_nonsense"


def _store(tmp_path, name="verdicts.db"):
    path = tmp_path / name
    conn = db.connect(path)
    run_id = seed_run(conn, run_id="run-verdicts", snapshot_id="snap-verdicts")
    conn.commit()
    return path, conn, run_id


def _insert_claim(conn, run_id, verdict, subject="scenario:features/a.feature#a step"):
    """A claim written by direct SQL: no repository, so only the store can refuse it."""
    conn.execute(
        "INSERT INTO claim (run_id, analyser, analyser_version, subject_ref, statement, verdict)"
        " VALUES (?,?,?,?,?,?)",
        (run_id, "level_fitness", "0.6.0", subject, "A claim written by SQL.", verdict),
    )


def _drop_triggers(conn):
    """Make a store look like one whose guard was not installed when its rows were written."""
    for name in ("claim_verdict_insert", "claim_verdict_update"):
        conn.execute(f"DROP TRIGGER IF EXISTS {name}")


def _claim_dump(conn) -> list[tuple]:
    return [tuple(row) for row in conn.execute("SELECT * FROM claim ORDER BY id")]


def _digest(conn) -> str:
    """A stable hash of every claim row and column, ids included: byte-identical or not at all."""
    payload = json.dumps(_claim_dump(conn), default=str, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ AC2: unknown stays refused

@pytest.mark.parametrize("verdict", [
    UNKNOWN,                # the reviewer's value
    "Distinct",             # case matters; a near-miss is still not an emitted name
    " optima l",
    "",
])
def test_an_unknown_verdict_is_refused_on_insert_by_direct_sql(tmp_path, verdict):
    _, conn, run_id = _store(tmp_path)
    try:
        with pytest.raises(sqlite3.IntegrityError) as refused:
            _insert_claim(conn, run_id, verdict)
        message = str(refused.value)
        assert "ever emitted" in message
        # The refusal names the current and the retired sets: the reader learns both what a live
        # run may write and what a restore may carry.
        for name in verdicts.current(conn) | set(verdicts.retired(conn)):
            assert name in message
        assert conn.execute("SELECT COUNT(*) FROM claim").fetchone()[0] == 0
    finally:
        conn.close()


def test_the_refusal_sentence_names_the_value_and_the_set(tmp_path):
    """The one function names both; SQLite's trigger message can only name the set."""
    _, conn, _ = _store(tmp_path)
    try:
        allowed = verdicts.current(conn)
        with pytest.raises(verdicts.UnknownVerdict) as refused:
            verdicts.validate_verdict(UNKNOWN, allowed)
        message = str(refused.value)
        assert f"'{UNKNOWN}'" in message
        for name in allowed:
            assert name in message
        assert verdicts.validate_verdict("gap", allowed) == "gap"
    finally:
        conn.close()


def test_updating_a_verdict_to_an_unknown_value_is_refused(tmp_path):
    _, conn, run_id = _store(tmp_path)
    try:
        claim_id = db.add_claim(conn, run_id, "level_fitness", "0.6.0",
                                "scenario:features/a.feature#a step", "A claim.", "gap", 0.5, [])
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE claim SET verdict=? WHERE id=?", (UNKNOWN, claim_id))
        assert conn.execute("SELECT verdict FROM claim WHERE id=?", (claim_id,)).fetchone()[0] == "gap"
        # The trigger is UPDATE OF verdict: editing any other column still works.
        conn.execute("UPDATE claim SET statement=? WHERE id=?", ("Edited.", claim_id))
        assert conn.execute("SELECT verdict FROM claim WHERE id=?", (claim_id,)).fetchone()[0] == "gap"
    finally:
        conn.close()


def test_rewriting_a_stored_verdict_to_a_retired_name_is_still_refused(tmp_path):
    """An UPDATE is not a restore: widening INSERT must not license rewriting history."""
    path, conn, run_id = _store(tmp_path)
    try:
        _drop_triggers(conn)
        _insert_claim(conn, run_id, "optimal")
        conn.commit()
    finally:
        conn.close()

    conn = db.connect(path)  # installs the v6 guard, rows untouched
    try:
        with pytest.raises(sqlite3.IntegrityError) as refused:
            conn.execute("UPDATE claim SET verdict='necessary'")
        assert "may not be rewritten" in str(refused.value)
        assert conn.execute("SELECT verdict FROM claim").fetchone()[0] == "optimal"
    finally:
        conn.close()


# ------------------------------------------------------------------ AC1: restore is not a write

def test_a_v5_store_gets_the_widened_trigger_when_it_is_reopened(tmp_path):
    """The body changed, and ``CREATE TRIGGER IF NOT EXISTS`` cannot change a body: v6 replaces it."""
    path, conn, run_id = _store(tmp_path)
    try:
        conn.execute("DROP TRIGGER claim_verdict_insert")
        conn.execute(
            "CREATE TRIGGER claim_verdict_insert BEFORE INSERT ON claim"
            " WHEN NEW.verdict NOT IN (SELECT name FROM verdict_vocabulary WHERE status = 'current')"
            " BEGIN SELECT RAISE(ABORT, 'the v5 refusal'); END")
        conn.execute("UPDATE schema_meta SET value = '5' WHERE key = 'schema_version'")
        conn.commit()
    finally:
        conn.close()

    conn = db.connect(path)
    try:
        insert = _trigger_sql(conn)["claim_verdict_insert"]
        assert "status = 'current'" not in insert
        _insert_claim(conn, run_id, "optimal")  # a restore into a store upgraded from v5
        conn.commit()
        assert conn.execute("SELECT verdict FROM claim").fetchone()[0] == "optimal"
    finally:
        conn.close()


def test_a_store_with_retired_names_is_copied_row_for_row_with_identical_bytes(tmp_path):
    """AC1. The row-level copy TESTOPS-45's trigger refused, now accepted and lossless."""
    src_path, conn, run_id = _store(tmp_path, "old.db")
    try:
        _drop_triggers(conn)  # a store written before the vocabulary settled
        for verdict, count in RETIRED.items():
            for i in range(count):
                _insert_claim(conn, run_id, verdict, subject=f"scenario:features/a.feature#{verdict} {i}")
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM claim").fetchone()[0] == 128
        before = _digest(conn)
    finally:
        conn.close()

    fresh_path = tmp_path / "restored.db"
    dest = db.connect(fresh_path)  # a new store: the v6 guard is installed before the copy
    try:
        dest.execute("ATTACH DATABASE ? AS src", (str(src_path),))
        try:
            dest.execute("INSERT INTO snapshot SELECT * FROM src.snapshot")
            dest.execute("INSERT INTO run SELECT * FROM src.run")
            dest.execute("INSERT INTO claim SELECT * FROM src.claim")  # the ticket's exact path
            dest.commit()
        finally:
            dest.execute("DETACH DATABASE src")
        assert _digest(dest) == before
        rows = dest.execute("SELECT verdict, COUNT(*) FROM claim GROUP BY verdict ORDER BY verdict").fetchall()
        assert {row[0]: row[1] for row in rows} == RETIRED
        # The guard did not have to come down: it is installed in this store and still refuses
        # anything the product has never emitted.
        with pytest.raises(sqlite3.IntegrityError):
            _insert_claim(dest, run_id, UNKNOWN)
    finally:
        dest.close()


# ------------------------------------------------------------------ AC3: code stricter than SQL

def test_the_analyser_path_is_stricter_than_the_trigger(tmp_path):
    """AC3. `optimal` passes SQL and is refused by the code path a live run uses."""
    path, conn, run_id = _store(tmp_path)
    try:
        # 1. The database accepts it on INSERT: that is the restore path.
        _insert_claim(conn, run_id, "optimal")
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM claim").fetchone()[0] == 1
        # 2. The code refuses it, naming the value and the current set.
        with pytest.raises(verdicts.UnknownVerdict) as refused:
            verdicts.validate_verdict("optimal", verdicts.current(conn))
        assert "'optimal'" in str(refused.value)
        # 3. The analyser emission boundary (db.add_claim) refuses it too, without SQL being reached.
        before = conn.execute("SELECT COUNT(*) FROM claim").fetchone()[0]
        with pytest.raises(verdicts.UnknownVerdict):
            db.add_claim(conn, run_id, "level_fitness", "0.6.0",
                         "scenario:features/a.feature#live", "A live claim.", "optimal", 0.1, [])
        assert conn.execute("SELECT COUNT(*) FROM claim").fetchone()[0] == before
        # 4. The two sets are genuinely different, which is what makes the two levels meaningful.
        assert "optimal" in verdicts.ever_emitted(conn)
        assert "optimal" not in verdicts.current(conn)
    finally:
        conn.close()


# ------------------------------------------------------------------ the two levels, and the docs

def _trigger_sql(conn) -> dict[str, str]:
    return {row[0]: row[1] for row in conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='trigger' AND name LIKE 'claim_verdict_%'")}


def test_the_insert_trigger_accepts_every_name_and_the_update_trigger_only_current(tmp_path):
    """The distinction, in the installed SQL rather than in this file's intentions."""
    _, conn, _ = _store(tmp_path)
    try:
        triggers = _trigger_sql(conn)
        assert set(triggers) == {"claim_verdict_insert", "claim_verdict_update"}
        for text in triggers.values():
            assert "verdict_vocabulary" in text, "a trigger does not read the one definition"
        # INSERT: the whole table, with no status filter - every name the product has ever emitted.
        insert = triggers["claim_verdict_insert"]
        assert "FROM verdict_vocabulary)" in insert
        assert "status = 'current'" not in insert
        # UPDATE: still the v5 question. A rewrite is not a restore.
        assert "status = 'current'" in triggers["claim_verdict_update"]
        # INSERT's message names both sets; UPDATE's names the current one.
        insert_message = insert.split("RAISE(ABORT,", 1)[1]
        for name in verdicts.ever_emitted(conn):
            assert name in insert_message
        assert "restore" in insert_message
        update_message = triggers["claim_verdict_update"].split("RAISE(ABORT,", 1)[1]
        for name in verdicts.current(conn):
            assert name in update_message
        # The code's set is the analysers' set, and is strictly smaller than the trigger's.
        assert verdicts.current(conn) == emitted_verdicts()
        assert verdicts.ever_emitted(conn) == verdicts.current(conn) | set(verdicts.retired(conn))
        assert verdicts.current(conn) < verdicts.ever_emitted(conn)
        assert set(verdicts.retired(conn)) == set(app.LEGACY_JUDGEMENT)
        assert not (verdicts.current(conn) & set(app.LEGACY_JUDGEMENT))
        # The prose still describes what an analyser may emit, not what a restore may carry.
        for place, read in (("schema.sql verdict column", schema_verdicts),
                            ("Claim docstring", claim_docstring_verdicts),
                            ("Claim.verdict field comment", claim_field_verdicts)):
            documented = read()
            stale, undocumented = disagreement(documented, set(verdicts.current(conn)))
            assert not stale, f"{place} names verdicts the analysers do not emit: {stale}"
            assert not undocumented, f"{place} does not document emitted verdicts: {undocumented}"
    finally:
        conn.close()


# ------------------------------------------------------------------ AC4/AC5: check-store, restore

def _three_state_store(tmp_path):
    """A store holding every state check-store distinguishes: current, retired and unknown."""
    path, conn, run_id = _store(tmp_path, "three-states.db")
    try:
        for verdict in ("gap", "gap", "review"):
            _insert_claim(conn, run_id, verdict, subject=f"scenario:features/a.feature#{verdict}-current")
        conn.commit()
        _drop_triggers(conn)
        for verdict, count in (("optimal", 2), ("overbuilt", 1)):  # history
            for i in range(count):
                _insert_claim(conn, run_id, verdict, subject=f"scenario:features/a.feature#{verdict} {i}")
        _insert_claim(conn, run_id, UNKNOWN, subject="scenario:features/a.feature#unknown")
        conn.commit()
    finally:
        conn.close()
    return path


def _check_store(path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "DB_PATH", path)
    connect = db.connect
    monkeypatch.setattr(cli.db, "connect", lambda: connect(path))
    code = cli.main(["check-store"])
    return code, capsys.readouterr().out


def test_check_store_distinguishes_three_states_with_counts(tmp_path, monkeypatch, capsys):
    """AC4. Current, historical and unknown are three statements, each with a count of its rows."""
    path = _three_state_store(tmp_path)
    code, out = _check_store(path, monkeypatch, capsys)
    assert code == 1  # the unknown row is a defect, and it is named
    assert "current       3 (gap 2, review 1)" in out
    assert "historical    3 (optimal 2, overbuilt 1)" in out
    assert "unknown       1" in out
    assert UNKNOWN in out


def test_restore_copies_all_three_states_and_check_store_still_sees_them(tmp_path, monkeypatch, capsys):
    """AC5. A byte-identical copy of a store holding all three states, and the report after it.

    Restoring a store that holds an *unknown* verdict is the one case INSERT cannot carry: the
    guard's whole purpose is that a value the product never emitted does not become new evidence
    (AC2). A verbatim restore therefore drops the destination's triggers for the copy and reopens
    the store, which reinstalls them from schema.sql; ``check-store`` then reports the rows the
    guard cannot vouch for. Both halftruths would be worse: silently accepting garbage (AC2 fails)
    or refusing to restore a store with one bad row (AC1/AC5 fail).
    """
    src_path = _three_state_store(tmp_path)
    src = sqlite3.connect(src_path)
    try:
        before = _digest(src)
        src_counts = (src.execute("SELECT COUNT(*) FROM claim").fetchone()[0],
                      src.execute("SELECT COUNT(*) FROM run").fetchone()[0])
    finally:
        src.close()

    dest_path = tmp_path / "all-states-restored.db"
    dest = db.connect(dest_path)
    try:
        # A row-level copy carrying a name the product never emitted is refused, even with the
        # destination's guard in place: that is AC2, not a gap in the restore path.
        dest.execute("ATTACH DATABASE ? AS src", (str(src_path),))
        try:
            dest.execute("INSERT INTO snapshot SELECT * FROM src.snapshot")
            dest.execute("INSERT INTO run SELECT * FROM src.run")
            with pytest.raises(sqlite3.IntegrityError):
                dest.execute("INSERT INTO claim SELECT * FROM src.claim")
            dest.rollback()
            # Verbatim restore: the destination's guard comes down for the copy only.
            _drop_triggers(dest)
            dest.execute("INSERT INTO snapshot SELECT * FROM src.snapshot")
            dest.execute("INSERT INTO run SELECT * FROM src.run")
            dest.execute("INSERT INTO claim SELECT * FROM src.claim")
            dest.commit()
        finally:
            dest.execute("DETACH DATABASE src")
        assert _digest(dest) == before, "the restore changed a row"
        assert dest.execute("SELECT COUNT(*) FROM claim").fetchone()[0] == src_counts[0]
    finally:
        dest.close()

    # Reopening installs the guard again, because schema.sql creates a missing trigger.
    reopened = db.connect(dest_path)
    try:
        assert _trigger_sql(reopened).keys() == {"claim_verdict_insert", "claim_verdict_update"}
        with pytest.raises(sqlite3.IntegrityError):
            _insert_claim(reopened, "run-verdicts", UNKNOWN)
    finally:
        reopened.close()

    code, out = _check_store(dest_path, monkeypatch, capsys)
    assert code == 1
    assert "current       3 (gap 2, review 1)" in out
    assert "historical    3 (optimal 2, overbuilt 1)" in out
    assert "unknown       1" in out


# ------------------------------------------------------------------ check-store basics

def test_check_store_reports_an_unknown_verdict(tmp_path, monkeypatch, capsys):
    path, conn, run_id = _store(tmp_path)
    try:
        _drop_triggers(conn)
        _insert_claim(conn, run_id, UNKNOWN)
        conn.commit()
    finally:
        conn.close()

    code, out = _check_store(path, monkeypatch, capsys)
    assert code == 1
    assert "unknown       1" in out
    assert "current       0" in out
    assert UNKNOWN in out
    for name in emitted_verdicts():
        assert name in out


def test_check_store_reports_retired_rows_as_history_not_corruption(tmp_path, monkeypatch, capsys):
    path, conn, run_id = _store(tmp_path)
    try:
        _drop_triggers(conn)
        for verdict, count in RETIRED.items():
            for _ in range(count):
                _insert_claim(conn, run_id, verdict)
        conn.commit()
    finally:
        conn.close()

    code, out = _check_store(path, monkeypatch, capsys)
    assert code == 0
    assert "historical    128 (" in out
    for verdict, count in RETIRED.items():
        assert f"{verdict} {count}" in out
    assert "unknown       0" in out
    assert "current       0" in out


def test_check_store_does_not_create_a_missing_store(tmp_path, monkeypatch, capsys):
    missing = tmp_path / "absent" / "testops.db"
    monkeypatch.setattr(cli, "DB_PATH", missing)
    assert cli.main(["check-store"]) == 1
    assert "no store at" in capsys.readouterr().out
    assert not missing.exists()
