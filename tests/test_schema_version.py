"""AC1: the schema version is stored per snapshot, and a claim written under v2 records 2.

Per snapshot, not once for the file: a snapshot is what an analysis was run against, and the claim
shape can change underneath it. Storing the version on the snapshot is what lets a v1 claim and a
v2 claim live in one store and stay tellable apart.
"""
from __future__ import annotations

from support_fixtures import TS, VERSIONS, add_v2_claim, seed_run
from testops.store import db


def test_each_snapshot_records_the_schema_version_it_was_taken_under(tmp_path):
    path = tmp_path / "versions.db"
    writer = db.connect(path)
    try:
        db.upsert_snapshot(writer, "snap-under-v1", "fixture", TS, VERSIONS, schema_version=1)
        db.upsert_snapshot(writer, "snap-under-v2", "fixture", TS, VERSIONS, schema_version=2)
        writer.commit()
    finally:
        writer.close()

    reader = db.connect(path)
    try:
        versions = {row["id"]: row["schema_version"]
                    for row in reader.execute("SELECT id, schema_version FROM snapshot")}
    finally:
        reader.close()

    assert versions == {"snap-under-v1": 1, "snap-under-v2": 2}


def test_a_claim_written_under_v2_records_schema_version_2(tmp_path):
    path = tmp_path / "claim-v2.db"
    writer = db.connect(path)
    try:
        run_id = seed_run(writer, schema_version=2)
        claim_id = add_v2_claim(writer, run_id)
        writer.commit()
    finally:
        writer.close()

    reader = db.connect(path)
    try:
        claim = reader.execute("SELECT * FROM claim WHERE id = ?", (claim_id,)).fetchone()
        snapshot_version = reader.execute("SELECT schema_version FROM snapshot").fetchone()[0]
    finally:
        reader.close()

    assert claim["schema_version"] == 2
    assert snapshot_version == 2
