"""Shared fixtures beyond the repository guard.

Two things every store test needs: a snapshot and a run for a claim's foreign keys, and a way to
state a claim with its provenance without repeating nineteen arguments per test.
"""
from __future__ import annotations

from typing import Any

TS = "2020-01-01T00:00:00+00:00"
PROJECT = "fixture"
VERSIONS = {"fixture/test": "0" * 40}

# A complete, plausible v2 provenance block. Tests vary one part of it at a time.
PROVENANCE: dict[str, Any] = dict(
    assertion_text="Given the panel is requested over http",
    assertion_path="features/panel_api.feature",
    assertion_line=17,
    assertion_commit="a" * 40,
)


def seed_run(conn, run_id: str = "run-schema", snapshot_id: str = "snap-schema",
             schema_version: int = 2) -> str:
    """Snapshot + run, so a claim has something to reference."""
    from testops.store import db

    db.upsert_snapshot(conn, snapshot_id, PROJECT, TS, VERSIONS, schema_version=schema_version)
    db.start_run(conn, run_id, PROJECT, snapshot_id, "level_fitness", TS)
    return run_id


def add_v2_claim(conn, run_id: str = "run-schema", **overrides):
    """Write a claim with complete v2 provenance, overridable field by field."""
    from testops.store import db

    fields = dict(PROVENANCE)
    fields.update(overrides)
    return db.add_claim(
        conn, run_id, "level_fitness", "0.6.0",
        "scenario:features/panel_api.feature#the panel is served",
        "The panel is asserted at the api boundary, where a browser is never launched",
        "gap", 0.42, [], schema_version=2, **fields,
    )
