"""TESTOPS-45: the store itself refuses a verdict no analyser emits.

TESTOPS-9 fixed the prose and left the store accepting any string. These tests are the store's own
obligations: they write by direct SQL, not through ``db.add_claim``, because a guard only the
repository honours is a guard the next connector skips.

The trigger's refusal message names the allowed set. SQLite's ``RAISE()`` accepts a string literal
only, so the trigger cannot interpolate the offending value; :func:`testops.store.verdicts.validate_verdict`
is the one function that names both, and ``check-store`` names the value it found in a stored row.
"""
from __future__ import annotations

import re
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
    """Make a store look like the legacy store this ticket must not rewrite."""
    for name in ("claim_verdict_insert", "claim_verdict_update"):
        conn.execute(f"DROP TRIGGER IF EXISTS {name}")


# ------------------------------------------------------------------ AC1: INSERT

@pytest.mark.parametrize("verdict", [
    "total_nonsense",       # the reviewer's value
    "optimal",              # retired: history is readable, not writable again
    "overbuilt",
    "necessary",
    "Distinct",             # case matters; a near-miss is still not the emitted name
    "",
])
def test_an_unknown_verdict_is_refused_on_insert_by_direct_sql(tmp_path, verdict):
    _, conn, run_id = _store(tmp_path)
    try:
        with pytest.raises(sqlite3.IntegrityError) as refused:
            _insert_claim(conn, run_id, verdict)
        message = str(refused.value)
        assert "refuses an unknown verdict" in message
        # The refusal names every value the analysers may write.
        for allowed in emitted_verdicts():
            assert allowed in message
        assert conn.execute("SELECT COUNT(*) FROM claim").fetchone()[0] == 0
    finally:
        conn.close()


def test_the_refusal_sentence_names_the_value_and_the_set(tmp_path):
    """The one function names both; SQLite's trigger message can only name the set."""
    _, conn, _ = _store(tmp_path)
    try:
        allowed = verdicts.current(conn)
        with pytest.raises(verdicts.UnknownVerdict) as refused:
            verdicts.validate_verdict("total_nonsense", allowed)
        message = str(refused.value)
        assert "'total_nonsense'" in message
        for name in allowed:
            assert name in message
        assert verdicts.validate_verdict("gap", allowed) == "gap"
    finally:
        conn.close()


# ------------------------------------------------------------------ AC2: UPDATE

def test_updating_a_verdict_to_an_unknown_value_is_refused(tmp_path):
    _, conn, run_id = _store(tmp_path)
    try:
        claim_id = db.add_claim(conn, run_id, "level_fitness", "0.6.0",
                                "scenario:features/a.feature#a step", "A claim.", "gap", 0.5, [])
        conn.commit()
        for bad in ("total_nonsense", "optimal"):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("UPDATE claim SET verdict=? WHERE id=?", (bad, claim_id))
            assert conn.execute("SELECT verdict FROM claim WHERE id=?", (claim_id,)).fetchone()[0] == "gap"
        # The trigger is UPDATE OF verdict: editing any other column still works.
        conn.execute("UPDATE claim SET statement=? WHERE id=?", ("Edited.", claim_id))
        assert conn.execute("SELECT verdict FROM claim WHERE id=?", (claim_id,)).fetchone()[0] == "gap"
    finally:
        conn.close()


# ------------------------------------------------------------------ AC3: history

def test_the_128_retired_rows_stay_readable_and_render_as_today(tmp_path):
    """The migration adds a trigger; it does not touch a stored verdict or how it is read."""
    path, conn, run_id = _store(tmp_path)
    try:
        _drop_triggers(conn)  # a legacy store: the guard did not exist when these were written
        for verdict, count in RETIRED.items():
            for i in range(count):
                _insert_claim(conn, run_id, verdict, subject=f"scenario:features/a.feature#{verdict} {i}")
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM claim").fetchone()[0] == 128
    finally:
        conn.close()

    conn = db.connect(path)  # the upgrade installs the triggers and leaves every row alone
    try:
        rows = conn.execute("SELECT verdict, COUNT(*) FROM claim GROUP BY verdict ORDER BY verdict").fetchall()
        assert {row[0]: row[1] for row in rows} == RETIRED
        assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger'"
                            " AND name IN ('claim_verdict_insert','claim_verdict_update')").fetchone()[0] == 2
        # Rendering is the same function the pages call, with the same historical judgements.
        assert app.list_judgement("optimal") == "Checked"
        assert app.list_judgement("necessary") == "Checked"
        assert app.list_judgement("overbuilt") == "Checked, but over-tested"
        assert app.verdict_label({"verdict": "optimal"}) == "Optimal"
        assert app.verdict_label({"verdict": "overbuilt"}) == "Overbuilt"
        assert app.verdict_label({"verdict": "necessary"}) == "Necessary"
        # A retired name is history, not a value a writer may reuse.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE claim SET verdict='optimal' WHERE verdict='necessary'")
    finally:
        conn.close()


# ------------------------------------------------------------------ AC4: one set

def _trigger_sql(conn) -> dict[str, str]:
    return {row[0]: row[1] for row in conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='trigger' AND name LIKE 'claim_verdict_%'")}


def _message_verdicts(trigger_sql: str) -> set[str]:
    match = re.search(r"RAISE\(ABORT,\s*'([^']*)'", trigger_sql)
    assert match, f"the trigger no longer raises a literal refusal: {trigger_sql!r}"
    names = re.search(r"one of (.+?): the store", match.group(1))
    assert names, f"the refusal does not name the allowed set: {match.group(1)!r}"
    return {part.strip() for part in names.group(1).split("|") if part.strip()}


def test_the_trigger_the_analysers_and_the_documents_name_the_same_set(tmp_path):
    """AC4, both directions, anchored in an actual store rather than in prose alone."""
    _, conn, _ = _store(tmp_path)
    try:
        triggers = _trigger_sql(conn)
        assert set(triggers) == {"claim_verdict_insert", "claim_verdict_update"}
        for text in triggers.values():
            assert "verdict_vocabulary" in text, "the trigger does not read the one definition"
            assert "status = 'current'" in text
        trigger_set = verdicts.current(conn)
        emitted = emitted_verdicts()
        assert trigger_set == emitted
        assert trigger_set, "the store's allowed set is empty; every comparison below would be vacuous"
        for text in triggers.values():
            assert _message_verdicts(text) == trigger_set
        for place, read in (("schema.sql verdict column", schema_verdicts),
                            ("Claim docstring", claim_docstring_verdicts),
                            ("Claim.verdict field comment", claim_field_verdicts)):
            documented = read()
            stale, undocumented = disagreement(documented, set(trigger_set))
            assert not stale, f"{place} names verdicts the store does not accept: {stale}"
            assert not undocumented, f"{place} does not document verdicts the store accepts: {undocumented}"
        # The retired names are documented where the pages read them, and nowhere writable.
        assert set(verdicts.retired(conn)) == set(app.LEGACY_JUDGEMENT)
        assert not (trigger_set & set(app.LEGACY_JUDGEMENT))
    finally:
        conn.close()


# ------------------------------------------------------------------ AC5: check-store

def test_check_store_reports_an_unknown_verdict(tmp_path, monkeypatch, capsys):
    path, conn, run_id = _store(tmp_path)
    try:
        _drop_triggers(conn)
        _insert_claim(conn, run_id, "total_nonsense")
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(cli, "DB_PATH", path)
    connect = db.connect
    monkeypatch.setattr(cli.db, "connect", lambda: connect(path))
    assert cli.main(["check-store"]) == 1
    out = capsys.readouterr().out
    assert "unknown       1" in out
    assert "total_nonsense" in out
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

    monkeypatch.setattr(cli, "DB_PATH", path)
    connect = db.connect
    monkeypatch.setattr(cli.db, "connect", lambda: connect(path))
    assert cli.main(["check-store"]) == 0
    out = capsys.readouterr().out
    assert "historical    128 (" in out
    for verdict, count in RETIRED.items():
        assert f"{verdict} {count}" in out
    assert "unknown       0" in out


def test_check_store_does_not_create_a_missing_store(tmp_path, monkeypatch, capsys):
    missing = tmp_path / "absent" / "testops.db"
    monkeypatch.setattr(cli, "DB_PATH", missing)
    assert cli.main(["check-store"]) == 1
    assert "no store at" in capsys.readouterr().out
    assert not missing.exists()
