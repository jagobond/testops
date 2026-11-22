"""AC5: a claim written through store.db.add_claim reads back unchanged through a fresh connection.

This is the evidence invariant in miniature: the claim row is the immutable evidence, and every
conclusion drawn from it elsewhere is derived.
"""
from __future__ import annotations

import json

from testops.store import db

SUBJECT = "scenario:features/panel_api.feature#the panel is served"
STATEMENT = "KP claim established at the api boundary - asserts the page-as-served"
VERDICT = "gap"
CONFIDENCE = 0.42


def _seed_run(conn, run_id: str = "run-roundtrip") -> None:
    db.upsert_snapshot(conn, "snap-roundtrip", "fixture",
                       "2020-01-01T00:00:00+00:00", {"fixture/test": "0" * 40})
    db.start_run(conn, run_id, "fixture", "snap-roundtrip", "level_fitness",
                 "2020-01-01T00:00:00+00:00")


def test_claim_survives_a_fresh_connection(tmp_path):
    path = tmp_path / "claims.db"

    writer = db.connect(path)
    try:
        _seed_run(writer)
        claim_id = db.add_claim(writer, "run-roundtrip", "level_fitness", "0.5.0",
                                SUBJECT, STATEMENT, VERDICT, CONFIDENCE, [])
        writer.commit()
    finally:
        writer.close()

    reader = db.connect(path)
    try:
        row = reader.execute("SELECT * FROM claim WHERE id = ?", (claim_id,)).fetchone()
    finally:
        reader.close()

    assert row is not None, "the claim was not persisted"
    assert row["subject_ref"] == SUBJECT
    assert row["statement"] == STATEMENT
    assert row["verdict"] == VERDICT
    assert row["confidence"] == CONFIDENCE
    assert json.loads(row["support"]) == []