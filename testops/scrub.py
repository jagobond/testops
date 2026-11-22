"""Remove review fixtures from a store, and only fixtures.

TESTOPS-35. A review session wrote a case into the live store with ``analyser = 'x'``, a name no
analyser in this build has. It rendered on the Product Owner's dashboard as if it were a claim
about his code. ``testops scrub-fixtures`` finds every case whose analyser is not registered, says
what it will remove, and removes it only when the caller repeats the command with ``--yes``.

What a fixture costs the store, and what it does not:

  * the case row, its findings and its recorded decisions were written by the harness, so they go;
    a case page is an argument, and an argument nobody can reproduce is noise with an id;
  * the run, the snapshot, the artefacts, the observations and the claims stay. A fixture case is
    usually pinned to a real run (``rev-duplicate`` pointed at a real reqoverflow duplication run),
    and deleting the run would destroy the evidence the other eighteen cases rest on. Deleting the
    claims the fixture pointed at would do the same: claims belong to the run, not to the case that
    borrowed them;
  * a suppression row is a decision keyed by finding fingerprint. It goes only when no *surviving*
    finding carries the same fingerprint, because a decision that still hides a real finding is
    evidence, not apparatus.

The plan is recomputed inside :func:`scrub` rather than trusted from a caller's earlier report, so
what was printed and what was deleted cannot be two different things.
"""
from __future__ import annotations

from .analysers import is_registered, registered_names

TABLES = ("snapshot", "artefact", "observation", "run", "claim", "inference",
          "case_", "finding", "case_state", "suppression")


def fixture_cases(conn) -> list[dict]:
    """Every case whose analyser is not a registered one, with what rests on it.

    Ordered by id so two runs of the report agree; the findings are this case's own rows, not a
    count of the store.
    """
    out: list[dict] = []
    for row in conn.execute(
            "SELECT id, project, analyser, run_id, snapshot_id, created_at"
            " FROM case_ ORDER BY id"):
        if is_registered(row["analyser"]):
            continue
        findings = [dict(f) for f in conn.execute(
            "SELECT id, fingerprint FROM finding WHERE case_id = ? ORDER BY id", (row["id"],))]
        state = conn.execute(
            "SELECT state, actor, at FROM case_state WHERE case_id = ? ORDER BY id DESC LIMIT 1",
            (row["id"],)).fetchone()
        out.append({
            "id": row["id"], "project": row["project"], "analyser": row["analyser"],
            "run_id": row["run_id"], "snapshot_id": row["snapshot_id"],
            "created_at": row["created_at"], "findings": findings,
            "state": dict(state) if state else None,
        })
    registered = registered_names()
    assert all(case["analyser"] not in registered for case in out), \
        "fixture_cases returned a case a registered analyser could have raised"
    return out


def orphaned_fingerprints(conn, cases: list[dict]) -> list[str]:
    """Fingerprints whose last finding is being removed - the only suppressions that go with it.

    A suppression keyed by a fingerprint a surviving finding still carries is a decision about
    evidence that remains. Deleting it would quietly un-decide a case nobody asked about.
    """
    if not cases:
        return []
    doomed = sorted({f["fingerprint"] for case in cases for f in case["findings"]})
    removed_ids = [case["id"] for case in cases]
    placeholders = ",".join("?" * len(removed_ids))
    out: list[str] = []
    for fingerprint in doomed:
        others = conn.execute(
            f"SELECT COUNT(*) FROM finding WHERE fingerprint = ? AND case_id NOT IN ({placeholders})",
            (fingerprint, *removed_ids)).fetchone()[0]
        if not others:
            out.append(fingerprint)
    return out


def totals(conn) -> dict:
    return {table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in TABLES}


def plan(conn) -> dict:
    """What a scrub would remove: the cases, their rows, and the totals a reader checks."""
    cases = fixture_cases(conn)
    # Only fingerprints that actually have a suppression row: an orphaned fingerprint is a
    # candidate, and a count of candidates would report a deletion that will not happen.
    suppressions = [fingerprint for fingerprint in orphaned_fingerprints(conn, cases)
                    if conn.execute("SELECT 1 FROM suppression WHERE fingerprint = ?",
                                    (fingerprint,)).fetchone() is not None]
    return {
        "cases": cases,
        "counts": {
            "case_": len(cases),
            "finding": sum(len(case["findings"]) for case in cases),
            "case_state": sum(
                conn.execute("SELECT COUNT(*) FROM case_state WHERE case_id = ?",
                             (case["id"],)).fetchone()[0] for case in cases),
            "suppression": len(suppressions),
        },
        "suppression_fingerprints": suppressions,
        "before": totals(conn),
    }


def scrub(conn, yes: bool = False) -> dict:
    """Remove the fixture cases in :func:`plan`, and only when ``yes`` is true.

    Returns the plan plus the rows actually removed, counted from SQLite's own row counts. A
    refusal (``yes=False``) touches nothing and reports the same plan.
    """
    found = plan(conn)
    if not yes:
        return {"plan": found, "removed": None, "totals_before": found["before"],
                "totals_after": found["before"]}

    removed = {table: 0 for table in ("suppression", "finding", "case_state", "case_")}
    for fingerprint in found["suppression_fingerprints"]:
        removed["suppression"] += conn.execute(
            "DELETE FROM suppression WHERE fingerprint = ?", (fingerprint,)).rowcount
    for case in found["cases"]:
        removed["finding"] += conn.execute(
            "DELETE FROM finding WHERE case_id = ?", (case["id"],)).rowcount
        removed["case_state"] += conn.execute(
            "DELETE FROM case_state WHERE case_id = ?", (case["id"],)).rowcount
        removed["case_"] += conn.execute(
            "DELETE FROM case_ WHERE id = ?", (case["id"],)).rowcount
    conn.commit()
    after = plan(conn)
    return {"plan": found, "removed": removed, "after": after,
            "totals_before": found["before"], "totals_after": totals(conn)}
