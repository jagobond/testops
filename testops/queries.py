"""Read models for the UI.

Deliberately separate from the analysers: a view may not need every column, and a UI that reaches into the store
for raw joins ends up encoding analysis logic in templates. Each function here answers one screen's question and
returns plain dicts.
"""
from __future__ import annotations

import json

from . import cases
from .links import GITHUB, blob_permalink, permalink, short_location


def _json(s, default=None):
    try:
        return json.loads(s) if s else (default if default is not None else {})
    except json.JSONDecodeError:
        return default if default is not None else {}


# The four fields that answer "where is this asserted?". A claim is unverifiable without them, so
# every read model carries them together and a v1 claim carries them as None - not as "" and not as 0.
PROVENANCE_FIELDS = ("assertion_text", "assertion_path", "assertion_line", "assertion_commit")


def _list_or_none(text: str | None, field: str):
    """Decode a JSON list, keeping NULL and [] distinct.

    NULL means "nothing was recorded"; [] means "nothing was missing". Coercing either into the other
    turns absence into a result, which is the one thing this store may never do.
    """
    if text is None:
        return None
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"claim.{field} holds unparseable JSON: {text!r}") from exc
    if not isinstance(value, list):
        raise ValueError(f"claim.{field} should hold a JSON list, found {value!r}")
    return value


def claim_view(row, repo: str | None = None) -> dict:
    """One claim as a screen sees it: statement, provenance and blind spots, always together.

    The only constructor of a claim read model - callers never assemble these keys themselves, so no
    page can render a claim that is missing the coordinates its reader needs to check it.

    ``permalink`` is built from the claim's *own* commit, never from the snapshot's current tip and
    never from HEAD: a reader following it must land on the file as it was when the claim was read.
    ``repo`` is the repository the assertion's path lives in, which the claim does not store.
    """
    _, _, scenario = row["subject_ref"].partition("#")
    provenance = {field: row[field] for field in PROVENANCE_FIELDS}
    return {
        "id": row["id"],
        "run_id": row["run_id"],
        "schema_version": row["schema_version"],
        "verdict": row["verdict"],
        "statement": row["statement"],
        "confidence": row["confidence"],
        "subject": row["subject_ref"],
        "scenario": scenario,
        "provenance": provenance,
        "permalink": blob_permalink(repo, provenance["assertion_commit"],
                                    provenance["assertion_path"], provenance["assertion_line"]),
        "sources_missing": _list_or_none(row["sources_missing"], "sources_missing"),
        "span": _list_or_none(row["span"], "span"),
        "interaction_label": row["interaction_label"],
        "interaction_code": row["interaction_code"],
        "established_by": row["established_by"],
        "proposed_action": row["proposed_action"],
    }


def claim_read(conn, claim_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM claim WHERE id = ?", (claim_id,)).fetchone()
    if not row:
        return None
    project = _project_of_run(conn, row["run_id"])
    claim = claim_view(row, repo=_repo_for_coordinates(conn, project, row["assertion_commit"],
                                                       row["assertion_path"]))
    claim["evidence"] = evidence_for_claim(conn, claim)
    return claim


def _project_of_run(conn, run_id: str) -> str | None:
    row = conn.execute("SELECT project FROM run WHERE id = ?", (run_id,)).fetchone()
    return row["project"] if row else None


def _repo_for_coordinates(conn, project: str | None, commit: str | None,
                          path: str | None) -> str | None:
    """Which repository a claim's assertion path lives in, found by exact coordinates.

    The claim stores a path and a commit, not an owner/name, and a GitHub URL needs the name. The
    lookup is an identity question, not an evidence one: it is answered by an artefact row whose
    commit and path are *equal* to the claim's (the ``LIKE`` only pre-filters the suffix; the match
    is completed in Python), so a file at a different commit cannot name the repository. Evidence
    itself is never taken from here - see :func:`evidence_for_claim`.
    """
    if not (project and commit and path):
        return None
    rows = conn.execute(
        """SELECT a.uri FROM artefact a JOIN snapshot s ON s.id = a.snapshot_id
           WHERE s.project = ? AND a.uri LIKE ?""",
        (project, f"%@{commit}:{path}")).fetchall()
    for row in rows:
        m = GITHUB.match(row["uri"])
        if m and m["sha"] == commit and m["path"] == path:
            return f"{m['owner']}/{m['repo']}"
    return None


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
    ctx = conn.execute("SELECT project FROM case_ WHERE id = ?", (case_id,)).fetchone()
    project = ctx["project"] if ctx else None
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
            claim = claim_view(c, repo=_repo_for_coordinates(conn, project, c["assertion_commit"],
                                                             c["assertion_path"]))
            claim.update({"used_model": bool(detail.get("model") and detail.get("model") != "none"),
                          "detail": detail, "evidence": evidence_for_claim(conn, claim)})
            claims.append(claim)
        out.append({"id": f["id"], "title": f["title"], "severity": f["severity"],
                    "fingerprint": f["fingerprint"], "claims": claims,
                    "suppressed": cases.suppressed(conn, f["fingerprint"]) is not None})
    return out


def evidence_for_claim(conn, claim: dict) -> list[dict] | None:
    """The observations recorded at a claim's own coordinates, and nothing else.

    A v2 claim names a commit and a path; evidence is the artefacts of the claim's *own run* whose
    uri carries that commit and that path, character for character. There is deliberately no
    ``LIKE %feature%`` here: that lookup resolved a scenario name to any file whose path contained
    it, which is how a claim in ``a/x.feature`` acquired links to ``b/x.y.feature`` and to
    same-named files from other snapshots. Two claims about the same words in different files are
    two different pieces of evidence, and a reader who follows the wrong one has been misled.

    Returns ``None`` when the claim has no coordinates to resolve (a v1 claim): "nothing was
    recorded" and "nothing was found" are different facts, and the page renders them differently.
    An empty list means the coordinates are known and this run recorded no observations at them.
    """
    prov = claim["provenance"]
    if claim["schema_version"] != 2 or not prov["assertion_path"] or not prov["assertion_commit"]:
        return None
    run = conn.execute("SELECT snapshot_id FROM run WHERE id = ?", (claim["run_id"],)).fetchone()
    if not run:
        return None
    wanted_commit, wanted_path = prov["assertion_commit"], prov["assertion_path"]
    out: list[dict] = []
    artefacts = conn.execute("SELECT id, uri, kind FROM artefact WHERE snapshot_id = ? ORDER BY id",
                             (run["snapshot_id"],)).fetchall()
    for a in artefacts:
        m = GITHUB.match(a["uri"])
        if not m or m["sha"] != wanted_commit or m["path"] != wanted_path:
            continue
        for o in conn.execute("SELECT key, value FROM observation WHERE artefact_id = ? ORDER BY id",
                              (a["id"],)):
            value = _json(o["value"])
            line = value.get("line")
            out.append({"uri": a["uri"], "kind": a["kind"], "key": o["key"], "line": line,
                        "link": permalink(a["uri"], line), "where": short_location(a["uri"], line),
                        "shows": _shows(o["key"], value)})
    return out


def _shows(key: str, value: dict) -> str:
    """One line saying what an observation shows - the sentence a bare link cannot give."""
    line = value.get("line")
    if key.startswith("scenario:"):
        name = key[len("scenario:"):]
        where = f"line {line}" if line else "an unrecorded line"
        steps = value.get("steps")
        count = f", {steps} step{'s' if steps != 1 else ''}" if isinstance(steps, int) else ""
        return f"the scenario \u201c{name}\u201d begins at {where}{count}"
    return f"an observation of {key}" + (f" at line {line}" if line else "")



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

    Each row carries ``statement``: the claim's own words, so the list says what is alleged. The
    stored ``finding.title`` is a truncated copy of that statement (160 characters, cut mid-sentence)
    and never belongs on a screen.
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
        r["statement"] = case_statement(conn, r["id"])
        latest.append(r)
    return latest, older


def case_statement(conn, case_id: str) -> str | None:
    """The first claim's statement in a case, or None when the case has no finding."""
    row = conn.execute("SELECT claim_ids FROM finding WHERE case_id = ? ORDER BY id LIMIT 1",
                       (case_id,)).fetchone()
    for cid in (_json(row["claim_ids"], []) if row else []):
        claim = conn.execute("SELECT statement FROM claim WHERE id = ?", (cid,)).fetchone()
        if claim:
            return claim["statement"]
    return None
