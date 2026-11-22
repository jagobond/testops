"""Case lifecycle: the human decision that stops a finding coming back.

A case is a group of findings from one run. A person marks it resolved, needing a fix, or a false positive.
Whatever they choose, the *evidence* is remembered - so the next run over the same evidence does not open the
same case again. That is the whole point of the table: an analyser that keeps re-reporting something a human has
already judged is worse than one that says nothing.

Fingerprints are deliberately computed from the evidence (analyser + subject + evidence shape), never from the
verdict. If a later run draws a different conclusion from the same evidence, that is a second look at a known
subject, not a new case.
"""
from __future__ import annotations

import datetime as dt
import hashlib

STATES = ("open", "needs_fix", "resolved", "false_positive")

# A resolved or false-positive case stops re-reporting. A needs_fix case does NOT: the defect is still there
# until someone fixes it, and a tool that goes quiet after being told "we know" stops being useful. Reopening
# (`open`) removes suppression, so an undo exists and works.
TERMINAL = ("resolved", "false_positive")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def fingerprint(analyser: str, subject_ref: str, evidence_key: str = "") -> str:
    raw = f"{analyser}|{subject_ref}|{evidence_key}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def set_state(conn, case_id: str, state: str, actor: str, note: str = "") -> None:
    if state not in STATES:
        raise ValueError(f"unknown state {state!r}; expected one of {STATES}")
    found = conn.execute("SELECT 1 FROM case_ WHERE id = ?", (case_id,)).fetchone()
    if not found:
        raise ValueError(f"no such case: {case_id}")
    conn.execute("INSERT INTO case_state (case_id, state, actor, at, note) VALUES (?,?,?,?,?)",
                 (case_id, state, actor, now(), note))
    if state == "open":
        # Reopening has to actually reopen. Leaving suppression rows behind would make the screen say "open"
        # while the analyser stayed silent - two surfaces disagreeing, permanently and invisibly.
        for row in conn.execute("SELECT fingerprint FROM finding WHERE case_id = ?", (case_id,)).fetchall():
            conn.execute("DELETE FROM suppression WHERE fingerprint = ?", (row["fingerprint"],))
    if state in TERMINAL:
        reason = state if state in ("resolved", "false_positive") else "accepted"
        for row in conn.execute("SELECT fingerprint FROM finding WHERE case_id = ?", (case_id,)).fetchall():
            conn.execute(
                "INSERT OR REPLACE INTO suppression (fingerprint, state, actor, at, note) VALUES (?,?,?,?,?)",
                (row["fingerprint"], reason, actor, now(), note))
    conn.commit()


def state_of(conn, case_id: str) -> str:
    row = conn.execute("SELECT state FROM case_state WHERE case_id = ? ORDER BY id DESC LIMIT 1",
                       (case_id,)).fetchone()
    return row["state"] if row else "open"


def suppressed(conn, fp: str) -> dict | None:
    row = conn.execute("SELECT state, actor, at, note FROM suppression WHERE fingerprint = ?", (fp,)).fetchone()
    return dict(row) if row else None


def list_cases(conn, project: str | None = None, limit: int = 40,
               run_id: str | None = None) -> list[dict]:
    """The cases in the store, newest first - and never a row that raised nothing.

    A case exists to carry a decision about a finding (TESTOPS-34). An empty ``case_`` row is the
    record that a run happened and raised nothing: evidence, not a case, and nothing a reader can
    decide. The rule lives in this query rather than in a template so every caller - the dashboard,
    the CLI, the run page - gets it without having to remember it.

    The rows are not deleted. They keep their findings (none), their run and their snapshot, and a
    reader reaches the run through :func:`testops.queries.run_read` and the run id in the URL.
    """
    sql = """SELECT c.id, c.project, c.analyser, c.created_at,
                    (SELECT COUNT(*) FROM finding f WHERE f.case_id = c.id) AS findings,
                    (SELECT state FROM case_state s WHERE s.case_id = c.id ORDER BY s.id DESC LIMIT 1) AS state
             FROM case_ c
             WHERE EXISTS (SELECT 1 FROM finding f WHERE f.case_id = c.id)"""
    args: tuple = ()
    if project:
        sql += " AND c.project = ?"
        args += (project,)
    if run_id:
        sql += " AND c.run_id = ?"
        args += (run_id,)
    sql += " ORDER BY c.created_at DESC, c.id DESC LIMIT ?"
    rows = conn.execute(sql, args + (limit,)).fetchall()
    return [{"id": r["id"], "project": r["project"], "analyser": r["analyser"], "created_at": r["created_at"],
             "findings": r["findings"], "state": r["state"] or "open"} for r in rows]


def findings_for(conn, case_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT id, title, severity, fingerprint FROM finding WHERE case_id = ? ORDER BY id", (case_id,))]
