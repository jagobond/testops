"""Read models for the UI.

Deliberately separate from the analysers: a view may not need every column, and a UI that reaches into the store
for raw joins ends up encoding analysis logic in templates. Each function here answers one screen's question and
returns plain dicts.
"""
from __future__ import annotations

import json

from . import cases
from .links import permalink, short_location


def _json(s, default=None):
    try:
        return json.loads(s) if s else (default if default is not None else {})
    except json.JSONDecodeError:
        return default if default is not None else {}


def case_row(conn, case_id: str) -> dict | None:
    r = conn.execute("""SELECT c.*, r.status AS run_status, r.finished_at, s.artefact_versions
                        FROM case_ c LEFT JOIN run r ON r.id = c.run_id
                        LEFT JOIN snapshot s ON s.id = c.snapshot_id
                        WHERE c.id = ?""", (case_id,)).fetchone()
    if not r:
        return None
    return {"id": r["id"], "project": r["project"], "analyser": r["analyser"],
            "created_at": r["created_at"], "snapshot": r["snapshot_id"],
            "summary": _json(r["summary"]), "state": cases.state_of(conn, case_id),
            "versions": _json(r["artefact_versions"])}


def finding_rows(conn, case_id: str) -> list[dict]:
    out = []
    for f in conn.execute("SELECT * FROM finding WHERE case_id = ? ORDER BY id", (case_id,)):
        claim_ids = _json(f["claim_ids"], [])
        claims = []
        for cid in claim_ids:
            c = conn.execute("SELECT * FROM claim WHERE id = ?", (cid,)).fetchone()
            if not c:
                continue
            inf = conn.execute("SELECT * FROM inference WHERE claim_id = ? ORDER BY id DESC LIMIT 1",
                               (cid,)).fetchone()
            detail = _json(inf["output"]) if inf else {}
            evidence = evidence_for_subject(conn, c["subject_ref"])
            feature, _, scenario = c["subject_ref"].partition("#")
            claims.append({"id": c["id"], "verdict": c["verdict"], "statement": c["statement"],
                           "confidence": c["confidence"], "scenario": scenario,
                           "subject": c["subject_ref"],
                           "used_model": bool(detail.get("model") and detail.get("model") != "none"),
                           "detail": detail, "evidence": evidence})
        out.append({"id": f["id"], "title": f["title"], "severity": f["severity"],
                    "fingerprint": f["fingerprint"], "claims": claims,
                    "suppressed": cases.suppressed(conn, f["fingerprint"]) is not None})
    return out


def evidence_for_subject(conn, subject_ref: str) -> list[dict]:
    """Resolve a claim's subject back to the artefacts that contain it."""
    feature = subject_ref.split("#")[0].replace("scenario:", "")
    rows = conn.execute("""SELECT a.uri, a.kind, o.key, o.value FROM observation o
                           JOIN artefact a ON a.id = o.artefact_id
                           WHERE a.uri LIKE ?""", (f"%{feature}%",)).fetchall()
    out = []
    for r in rows:
        value = _json(r["value"])
        line = value.get("line")
        out.append({"uri": r["uri"], "kind": r["kind"], "key": r["key"], "line": line,
                    "link": permalink(r["uri"], line), "where": short_location(r["uri"], line)})
    return out


def recent(conn, project: str | None = None, limit: int = 25) -> list[dict]:
    return cases.list_cases(conn, project, limit)


def freshness(conn, project: str | None = None) -> dict:
    """What the UI must say instead of "all clear": when did we last actually look, and at what commit.

    An empty case list is ambiguous - it can mean "nothing wrong" or "nothing has run since Tuesday". Those are
    the same pixels and different facts, and the second one is how a monitoring tool lies to you.
    """
    sql = """SELECT r.id, r.project, r.analyser, r.status, r.finished_at, s.artefact_versions
             FROM run r LEFT JOIN snapshot s ON s.id = r.snapshot_id
             WHERE r.status IN ('ok','partial')"""
    args: tuple = ()
    if project:
        sql += " AND r.project = ?"
        args = (project,)
    sql += " ORDER BY r.finished_at DESC LIMIT 1"
    row = conn.execute(sql, args).fetchone()
    if not row:
        return {"ever_run": False, "finished_at": None, "project": project, "versions": {}}
    return {"ever_run": True, "finished_at": row["finished_at"], "project": row["project"],
            "analyser": row["analyser"], "run": row["id"], "versions": _json(row["artefact_versions"])}


def latest_per_analyser(conn, project: str | None = None) -> tuple[list[dict], int]:
    """The newest case per (project, analyser) - what a person actually wants to see.

    Older runs are history, not a work queue. Showing every run ever made turns the home screen into a log, and
    a log with 40 rows is a screen nobody opens.
    """
    rows = cases.list_cases(conn, project, 200)
    seen: set[tuple[str, str]] = set()
    latest, older = [], 0
    for r in rows:
        key = (r["project"], r["analyser"])
        if key in seen:
            older += 1
            continue
        seen.add(key)
        latest.append(r)
    return latest, older
