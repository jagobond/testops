"""AC7: a v2 claim written through db.add_claim and read through a fresh connection is unchanged.

Every field, including the line number and the list of sources that could not be consulted. A claim
that comes back subtly different - an int as a string, a list as its JSON text, a missing line
defaulted to 0 - is a claim whose case cannot be rebuilt from the store, which is the invariant the
whole design rests on.
"""
from __future__ import annotations

from testops import queries
from testops.store import db

SUBJECT = "scenario:features/panel_api.feature#the panel is served"
STATEMENT = "The panel is asserted at the api boundary, where no browser is launched"
ASSERTION_TEXT = "Given the panel is requested over http"
PATH = "features/panel_api.feature"
LINE = 314
COMMIT = "0123456789abcdef0123456789abcdef01234567"
MISSING = ["jira", "ado"]

FIELDS = dict(
    assertion_text=ASSERTION_TEXT,
    assertion_path=PATH,
    assertion_line=LINE,
    assertion_commit=COMMIT,
    interaction_label="needs a browser",
    interaction_code="I4",
    span=["api", "browser"],
    established_by="level_fitness:ACCESSIBILITY/carrier",
    sources_missing=MISSING,
    proposed_action="Assert the rendered panel in the browser suite",
)


def _write(path) -> int:
    conn = db.connect(path)
    try:
        db.upsert_snapshot(conn, "snap-rt", "fixture", "2020-01-01T00:00:00+00:00",
                           {"fixture/test": "0" * 40}, schema_version=2)
        db.start_run(conn, "run-rt", "fixture", "snap-rt", "level_fitness",
                     "2020-01-01T00:00:00+00:00")
        claim_id = db.add_claim(conn, "run-rt", "level_fitness", "0.6.0", SUBJECT, STATEMENT,
                                "gap", 0.42, [], schema_version=2, **FIELDS)
        conn.commit()
    finally:
        conn.close()
    return claim_id


def test_every_v2_field_survives_a_fresh_connection(tmp_path):
    path = tmp_path / "roundtrip.db"
    claim_id = _write(path)

    reader = db.connect(path)
    try:
        row = reader.execute("SELECT * FROM claim WHERE id = ?", (claim_id,)).fetchone()
    finally:
        reader.close()

    assert row["schema_version"] == 2
    assert row["subject_ref"] == SUBJECT
    assert row["statement"] == STATEMENT
    assert row["verdict"] == "gap"
    assert row["confidence"] == 0.42
    for field, expected in FIELDS.items():
        if field in ("span", "sources_missing"):
            continue
        assert row[field] == expected, field

    assert db.uj(row["span"], None) == ["api", "browser"]
    assert db.uj(row["sources_missing"], None) == MISSING


def test_the_read_model_returns_the_same_fields_typed_the_same_way(tmp_path):
    path = tmp_path / "roundtrip-model.db"
    claim_id = _write(path)

    reader = db.connect(path)
    try:
        claim = queries.claim_read(reader, claim_id)
    finally:
        reader.close()

    assert claim["provenance"] == {
        "assertion_text": ASSERTION_TEXT,
        "assertion_path": PATH,
        "assertion_line": LINE,
        "assertion_commit": COMMIT,
    }
    assert isinstance(claim["provenance"]["assertion_line"], int)
    assert claim["sources_missing"] == MISSING
    assert claim["span"] == ["api", "browser"]
    assert claim["interaction_label"] == "needs a browser"
    assert claim["interaction_code"] == "I4"
    assert claim["established_by"] == "level_fitness:ACCESSIBILITY/carrier"
    assert claim["proposed_action"] == "Assert the rendered panel in the browser suite"


def test_small_line_numbers_are_not_mistaken_for_absent_ones(tmp_path):
    """Line 1 is falsy-adjacent: `line or None` style code would erase it."""
    path = tmp_path / "line-one.db"
    conn = db.connect(path)
    try:
        db.upsert_snapshot(conn, "snap-1", "fixture", "2020-01-01T00:00:00+00:00",
                           {"fixture/test": "0" * 40}, schema_version=2)
        db.start_run(conn, "run-1", "fixture", "snap-1", "level_fitness",
                     "2020-01-01T00:00:00+00:00")
        claim_id = db.add_claim(conn, "run-1", "level_fitness", "0.6.0", SUBJECT, STATEMENT,
                                "gap", 0.0, [], schema_version=2,
                                assertion_text="Feature: the panel", assertion_path=PATH,
                                assertion_line=1, assertion_commit=COMMIT)
        conn.commit()
    finally:
        conn.close()

    reader = db.connect(path)
    try:
        claim = queries.claim_read(reader, claim_id)
    finally:
        reader.close()

    assert claim["provenance"]["assertion_line"] == 1
