"""TESTOPS-44 AC4: a store that upgrades itself says so, once, in words that name the change.

``db.connect()`` migrates whatever store it opens. That is right - a forward-only refusal protects an
older *build*, and nothing protected the person who did not intend to migrate the file they were
about to read. So an open that changes the store prints exactly one line naming both versions, and an
open that changes nothing prints nothing: a line in the output means this open upgraded the file.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import v1_store
from testops.store import db, migrate

FIXTURES = Path(__file__).parent / "fixtures" / "projects_services"


def _v3_copy(tmp_path) -> Path:
    target = tmp_path / "v3.db"
    shutil.copyfile(FIXTURES / "before_v3.db", target)
    return target


def test_migrating_a_v3_store_prints_one_line_naming_the_change(tmp_path, capsys):
    path = _v3_copy(tmp_path)
    db.connect(path).close()

    captured = capsys.readouterr()
    assert captured.err.strip() == f"migrated store v3 -> v{migrate.CURRENT_VERSION}"
    assert captured.err.count("\n") == 1, "one line, not a paragraph"
    assert captured.out == "", "a notice must not land in the CLI's data channel"


def test_a_store_opened_for_reading_prints_nothing(tmp_path, capsys):
    """The distinction AC4 asks for: a migrated store is not every store."""
    path = _v3_copy(tmp_path)
    db.connect(path).close()
    capsys.readouterr()

    db.connect(path).close()

    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ""


def test_a_v1_store_names_the_version_it_came_from(tmp_path, capsys):
    path = tmp_path / "v1.db"
    v1_store.build(path)

    db.connect(path).close()

    assert capsys.readouterr().err.strip() == f"migrated store v1 -> v{migrate.CURRENT_VERSION}"


def test_a_new_store_is_created_without_a_migration_notice(tmp_path, capsys):
    """Nothing was migrated: there was nothing there. Saying otherwise would be a small lie."""
    path = tmp_path / "fresh.db"
    db.connect(path).close()

    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ""


def test_a_store_from_a_newer_build_is_refused_naming_both_versions(tmp_path, capsys):
    path = tmp_path / "future.db"
    db.connect(path).close()
    capsys.readouterr()

    import sqlite3
    raw = sqlite3.connect(path)
    try:
        raw.execute("UPDATE schema_meta SET value = ? WHERE key = 'schema_version'",
                    (str(migrate.CURRENT_VERSION + 1),))
        raw.commit()
    finally:
        raw.close()

    with pytest.raises(db.SchemaTooNewError) as refused:
        db.connect(path)

    message = str(refused.value)
    assert str(migrate.CURRENT_VERSION + 1) in message
    assert str(migrate.CURRENT_VERSION) in message
    assert capsys.readouterr().err == "", "a refused open must not claim it migrated anything"
