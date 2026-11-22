"""Retention: keep every run explainable, without keeping every byte four times.

The store is append-only evidence. Two facts about it decide this module:

1. **Blobs are already deduplicated.** ``blobs.put`` keys on the sha256 of the content, so
   re-recording an unchanged test arm adds no file: 1132 artefact rows shared 269 blobs when this
   ticket was written. Growth is therefore in *rows*, not in copied bytes.
2. **A snapshot is evidence for the cases that were raised from it.** A case a person has decided,
   or a finding a person has suppressed, must remain explainable afterwards - the case says
   "resolved because <note>", and the note is only honest while the rows behind it exist. That is
   why pruning refuses any snapshot a decided or suppressed case references.

Nothing here runs on a schedule and nothing deletes without being asked. ``retention`` reports;
``retention --prune --keep N --yes`` (N per project) is the only path that removes a row, and it
refuses without ``--yes``. There is no default prune and no timer: silent deletion of evidence is
the failure this module exists to avoid.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from . import blobs

# Every table whose rows carry a snapshot. A snapshot's "rows" figure counts the rows it added,
# including its own snapshot and run rows, so two runs over one commit differ by exactly the rows
# the second run wrote.
TABLES = ("snapshot", "run", "artefact", "observation", "claim", "inference",
          "case_", "finding", "case_state")

# A row's stored byte payload is the sum of the byte lengths of its text columns. This is a
# measurement, not an estimate: SQLite's own ``length(CAST(x AS BLOB))`` reports the stored byte
# count of each value. It deliberately excludes page overhead and index bytes, which SQLite does
# not attribute to a row; the store-level footprint below includes the file on disk.
_TEXT_COLUMNS = {
    "snapshot": ("id", "project", "created_at", "artefact_versions", "meta"),
    "run": ("id", "project", "snapshot_id", "analyser", "status", "started_at",
            "finished_at", "budget", "error"),
    "artefact": ("uri", "kind", "blob_sha", "meta"),
    "observation": ("extractor", "extractor_version", "key", "value"),
    "claim": ("subject_ref", "statement", "verdict", "support", "assertion_text",
              "assertion_path", "assertion_commit", "interaction_label", "interaction_code",
              "span", "established_by", "sources_missing", "proposed_action"),
    "inference": ("model", "model_version", "prompt_hash", "input_refs", "output"),
    "case_": ("id", "project", "analyser", "snapshot_id", "created_at", "summary"),
    "finding": ("title", "severity", "fingerprint", "claim_ids"),
    "case_state": ("state", "actor", "at", "note"),
}


def _bytes_expr(table: str) -> str:
    return " + ".join(f"COALESCE(length(CAST({column} AS BLOB)), 0)"
                      for column in _TEXT_COLUMNS[table])


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def age_seconds(created_at: str, at: dt.datetime | None = None) -> int | None:
    """Seconds between a snapshot and now, or ``None`` when the timestamp cannot be read.

    ``None`` is "cannot say", never zero: a snapshot with an unreadable timestamp is not brand new.
    """
    try:
        then = dt.datetime.fromisoformat(created_at)
    except (TypeError, ValueError):
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=dt.timezone.utc)
    return int(((at or now()) - then).total_seconds())


def age_text(seconds: int | None) -> str:
    if seconds is None:
        return "unknown"
    if seconds < 0:
        return "in the future"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{days}d {hours:02d}h"
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def _blob_files(blob_dir: Path | None = None) -> list[Path]:
    root = Path(blob_dir or blobs.blob_dir())
    if not root.exists():
        return []
    return [path for path in root.rglob("*") if path.is_file()]


def blob_usage(blob_dir: Path | None = None) -> dict:
    files = _blob_files(blob_dir)
    return {"files": len(files), "bytes": sum(path.stat().st_size for path in files)}


def store_footprint(conn, db_path: Path | None = None, blob_dir: Path | None = None) -> dict:
    """What the store occupies right now: rows per table, the database file and the blobs on disk.

    This is the before/after instrument for growth. It reads the file system and counts rows, so a
    "growth per run" number produced with it is measured, never estimated. The database path is
    read from the connection unless one is passed, so a caller cannot report on a different file
    from the one it just wrote.
    """
    conn.commit()
    path = Path(db_path) if db_path else _database_file(conn)
    counts = {table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
              for table in TABLES + ("suppression",)}
    usage = blob_usage(blob_dir)
    db_bytes = path.stat().st_size if path is not None and path.exists() else 0
    return {"rows": counts, "row_total": sum(counts.values()),
            "db_bytes": db_bytes, **usage, "bytes": db_bytes + usage["bytes"]}


def _database_file(conn) -> Path | None:
    """The file behind this connection, or ``None`` for an in-memory store."""
    for _seq, name, file in conn.execute("PRAGMA database_list"):
        if name == "main" and file:
            return Path(file)
    return None


# -------------------------------------------------------------------------------- per snapshot

_SQL = """
SELECT s.id, s.project, s.created_at,
       (SELECT COUNT(*) FROM run r WHERE r.snapshot_id = s.id) AS runs,
       (SELECT COUNT(*) FROM artefact a WHERE a.snapshot_id = s.id) AS artefacts,
       (SELECT COUNT(*) FROM observation o JOIN artefact a ON a.id = o.artefact_id
         WHERE a.snapshot_id = s.id) AS observations,
       (SELECT COUNT(*) FROM claim c JOIN run r ON r.id = c.run_id
         WHERE r.snapshot_id = s.id) AS claims,
       (SELECT COUNT(*) FROM inference i JOIN claim c ON c.id = i.claim_id
         JOIN run r ON r.id = c.run_id WHERE r.snapshot_id = s.id) AS inferences,
       (SELECT COUNT(*) FROM case_ c WHERE c.snapshot_id = s.id) AS cases,
       (SELECT COUNT(*) FROM finding f JOIN case_ c ON c.id = f.case_id
         WHERE c.snapshot_id = s.id) AS findings,
       (SELECT COUNT(*) FROM case_state cs JOIN case_ c ON c.id = cs.case_id
         WHERE c.snapshot_id = s.id) AS decisions,
       (SELECT COUNT(*) FROM suppression sp JOIN finding f ON f.fingerprint = sp.fingerprint
         JOIN case_ c ON c.id = f.case_id WHERE c.snapshot_id = s.id) AS suppressions,
       COALESCE(length(CAST(s.id AS BLOB)), 0) + COALESCE(length(CAST(s.project AS BLOB)), 0)
         + COALESCE(length(CAST(s.created_at AS BLOB)), 0)
         + COALESCE(length(CAST(s.artefact_versions AS BLOB)), 0)
         + COALESCE(length(CAST(s.meta AS BLOB)), 0)
       + COALESCE((SELECT SUM(%(run_bytes)s) FROM run r WHERE r.snapshot_id = s.id), 0)
       + COALESCE((SELECT SUM(%(artefact_bytes)s) FROM artefact a
                    WHERE a.snapshot_id = s.id), 0)
       + COALESCE((SELECT SUM(%(observation_bytes)s) FROM observation o
                    JOIN artefact a ON a.id = o.artefact_id WHERE a.snapshot_id = s.id), 0)
       + COALESCE((SELECT SUM(%(claim_bytes)s) FROM claim c JOIN run r ON r.id = c.run_id
                    WHERE r.snapshot_id = s.id), 0)
       + COALESCE((SELECT SUM(%(inference_bytes)s) FROM inference i
                    JOIN claim c ON c.id = i.claim_id JOIN run r ON r.id = c.run_id
                    WHERE r.snapshot_id = s.id), 0)
       + COALESCE((SELECT SUM(%(case_bytes)s) FROM case_ c WHERE c.snapshot_id = s.id), 0)
       + COALESCE((SELECT SUM(%(finding_bytes)s) FROM finding f JOIN case_ c ON c.id = f.case_id
                    WHERE c.snapshot_id = s.id), 0)
       + COALESCE((SELECT SUM(%(state_bytes)s) FROM case_state cs JOIN case_ c ON c.id = cs.case_id
                    WHERE c.snapshot_id = s.id), 0)
       AS row_bytes
FROM snapshot s
ORDER BY s.created_at, s.id
""" % {
    "run_bytes": _bytes_expr("run"),
    "artefact_bytes": _bytes_expr("artefact"),
    "observation_bytes": _bytes_expr("observation"),
    "claim_bytes": _bytes_expr("claim"),
    "inference_bytes": _bytes_expr("inference"),
    "case_bytes": _bytes_expr("case_"),
    "finding_bytes": _bytes_expr("finding"),
    "state_bytes": _bytes_expr("case_state"),
}


def report_rows(conn, blob_dir: Path | None = None, at: dt.datetime | None = None) -> list[dict]:
    """One row per snapshot: age, rows, bytes, and whether a decision or suppression refers to it.

    ``bytes`` is the snapshot's measured payload - the stored byte length of every row it added,
    plus the on-disk size of the distinct blobs its artefacts reference. A blob shared by several
    snapshots is counted under each of them; ``blob_bytes`` is broken out so a reader can see that
    without reading the source.
    """
    sizes: dict[str, int] = {}
    root = Path(blob_dir or blobs.blob_dir())
    rows: list[dict] = []
    for row in conn.execute(_SQL):
        shas = [r[0] for r in conn.execute(
            "SELECT DISTINCT blob_sha FROM artefact WHERE snapshot_id = ? AND blob_sha IS NOT NULL",
            (row["id"],))]
        blob_bytes = 0
        for sha in shas:
            if sha not in sizes:
                path = root / sha[:2] / sha[2:]
                sizes[sha] = path.stat().st_size if path.exists() else 0
            blob_bytes += sizes[sha]
        counts = {name: int(row[name]) for name in
                  ("runs", "artefacts", "observations", "claims", "inferences", "cases",
                   "findings", "decisions", "suppressions")}
        seconds = age_seconds(row["created_at"], at)
        rows.append({
            "id": row["id"],
            "project": row["project"],
            "created_at": row["created_at"],
            "age_seconds": seconds,
            "age": age_text(seconds),
            # The snapshot row itself plus the rows it added. Two runs over one commit therefore
            # differ by exactly the rows the second run wrote.
            "rows": 1 + counts["runs"] + counts["artefacts"] + counts["observations"]
                    + counts["claims"] + counts["inferences"] + counts["cases"]
                    + counts["findings"] + counts["decisions"],
            "row_bytes": int(row["row_bytes"]),
            "blob_count": len(shas),
            "blob_bytes": blob_bytes,
            "bytes": int(row["row_bytes"]) + blob_bytes,
            "decided": counts["decisions"] > 0,
            "suppressed": counts["suppressions"] > 0,
            "counts": counts,
        })
    return rows


# ------------------------------------------------------------------------------------ planning

def _newest_run_snapshots(conn) -> dict[str, list[str]]:
    """snapshot id -> the analysers whose newest run lives there.

    The newest run per (project, analyser) is the one a person is looking at; pruning its snapshot
    would delete the current answer, so it is never a candidate. Ties are broken deterministically
    by started_at and then run id.
    """
    latest: dict[tuple[str, str], tuple[tuple, str]] = {}
    for row in conn.execute(
            "SELECT id, project, analyser, snapshot_id, started_at, finished_at FROM run"):
        # ``COALESCE(finished, started)``: a run still in flight is the newest look, not an old one.
        stamp = (row["finished_at"] or row["started_at"] or "", row["started_at"] or "", row["id"])
        key = (row["project"], row["analyser"])
        if key not in latest or stamp > latest[key][0]:
            latest[key] = (stamp, row["snapshot_id"])
    out: dict[str, list[str]] = {}
    for (_project, analyser), (_stamp, snapshot_id) in latest.items():
        out.setdefault(snapshot_id, []).append(analyser)
    return out


def _claims_referenced_by_surviving_findings(conn, candidates: set[str]) -> set[str]:
    """Snapshot ids whose claims a finding outside the candidate set still points at.

    Findings carry their claim ids as JSON, not as a foreign key, so the store cannot enforce this.
    A page renders a claim through its finding; deleting a claim a surviving finding names would
    break that page, and the ticket's rule is that every surviving page renders exactly as before.
    Such a snapshot is protected rather than pruned.
    """
    out: set[str] = set()
    for row in conn.execute(
            "SELECT f.claim_ids, c.snapshot_id FROM finding f JOIN case_ c ON c.id = f.case_id"):
        if row["snapshot_id"] in candidates:
            continue
        try:
            ids = json.loads(row["claim_ids"] or "[]")
        except json.JSONDecodeError:
            ids = []
        if not isinstance(ids, list) or not ids:
            continue
        placeholders = ",".join("?" for _ in ids)
        hit = conn.execute(
            f"SELECT r.snapshot_id FROM claim c JOIN run r ON r.id = c.run_id"
            f" WHERE c.id IN ({placeholders}) LIMIT 1", ids).fetchone()
        if hit is not None:
            out.add(hit["snapshot_id"])
    return out


def plan(conn, keep: int, blob_dir: Path | None = None) -> dict:
    """Decide what ``--keep N`` would delete, and what must survive, with its reason.

    ``keep`` is applied per project (``--keep N`` has always meant N per project; TESTOPS-30 is
    the wording catching up): a project's N most recent snapshots are kept whatever the
    other projects hold. A global count would let a busy project starve a quiet one and delete the
    quiet one's whole history, which is not a retention policy anybody asked for.

    Three rules on top of age; a snapshot is kept when any applies:

    * a case referencing it has a decision (``case_state``) or a suppression;
    * it hosts the newest run of an analyser (per project);
    * a surviving finding still names one of its claims.
    """
    if keep < 0:
        raise ValueError("keep must not be negative")
    rows = report_rows(conn, blob_dir)
    newest = _newest_run_snapshots(conn)

    per_project: dict[str, list[dict]] = {}
    for row in rows:
        per_project.setdefault(row["project"], []).append(row)
    recent: set[str] = set()
    for project_rows in per_project.values():
        ordered = sorted(project_rows, key=lambda r: (r["created_at"], r["id"]), reverse=True)
        recent.update(row["id"] for row in ordered[:keep])

    kept: dict[str, list[str]] = {}
    for row in rows:
        reasons = kept.setdefault(row["id"], [])
        if row["id"] in recent:
            reasons.append(f"one of the {keep} most recent in {row['project']}")
        if row["decided"]:
            reasons.append("a case referencing it has a decision")
        if row["suppressed"]:
            reasons.append("a case referencing it has a suppression")
        if row["id"] in newest:
            for analyser in sorted(newest[row["id"]]):
                reasons.append(f"the newest {analyser} run")

    candidates = {row["id"] for row in rows if not kept[row["id"]]}
    # Removing a candidate can never create a new candidate, so one pass over the protected set is
    # enough; it is a loop only because the reason text grows with each round.
    while True:
        extra = _claims_referenced_by_surviving_findings(conn, candidates)
        new = extra & candidates
        if not new:
            break
        for snapshot_id in sorted(new):
            candidates.discard(snapshot_id)
            kept[snapshot_id].append("a surviving finding still names one of its claims")

    surviving_shas = {row[0] for row in conn.execute(
        "SELECT DISTINCT blob_sha FROM artefact WHERE blob_sha IS NOT NULL"
        f" AND snapshot_id NOT IN ({','.join('?' for _ in candidates) or 'NULL'})", tuple(candidates))}
    orphan_shas = {row[0] for row in conn.execute(
        "SELECT DISTINCT blob_sha FROM artefact WHERE blob_sha IS NOT NULL"
        f" AND snapshot_id IN ({','.join('?' for _ in candidates) or 'NULL'})", tuple(candidates))}

    root = Path(blob_dir or blobs.blob_dir())
    removable = []
    for sha in sorted(orphan_shas - surviving_shas):
        path = root / sha[:2] / sha[2:]
        if path.is_file():
            removable.append({"sha": sha, "bytes": path.stat().st_size})

    snapshots = []
    for row in rows:
        action = "delete" if row["id"] in candidates else "keep"
        snapshots.append({**row, "action": action, "reasons": kept[row["id"]]})
    return {
        "keep": keep,
        "snapshots": snapshots,
        "delete": [row["id"] for row in snapshots if row["action"] == "delete"],
        "blobs": removable,
        "blob_bytes": sum(item["bytes"] for item in removable),
    }


# ------------------------------------------------------------------------------------ pruning

def prune(conn, keep: int, yes: bool = False, blob_dir: Path | None = None) -> dict:
    """Delete the snapshots ``plan`` names, and only those. Without ``yes`` nothing is deleted.

    The caller decides what to print; this function decides what is true. It re-derives the plan
    itself, so calling it cannot bypass a rule by passing a hand-built list.
    """
    decision = plan(conn, keep, blob_dir)
    if not yes:
        return {"applied": False, "reason": "confirmation-required", "plan": decision}
    if not decision["delete"]:
        return {"applied": True, "deleted": {"snapshots": [], "rows": {}}, "blobs": [],
                "plan": decision}

    ids = tuple(decision["delete"])
    placeholders = ",".join("?" for _ in ids)
    deleted_rows: dict[str, int] = {}
    try:
        for table, sql in (
            ("inference",
             "DELETE FROM inference WHERE claim_id IN (SELECT id FROM claim WHERE run_id IN"
             f" (SELECT id FROM run WHERE snapshot_id IN ({placeholders})))"),
            ("claim",
             "DELETE FROM claim WHERE run_id IN"
             f" (SELECT id FROM run WHERE snapshot_id IN ({placeholders}))"),
            ("case_state",
             "DELETE FROM case_state WHERE case_id IN"
             f" (SELECT id FROM case_ WHERE snapshot_id IN ({placeholders}))"),
            ("finding",
             "DELETE FROM finding WHERE case_id IN"
             f" (SELECT id FROM case_ WHERE snapshot_id IN ({placeholders}))"),
            ("case_", f"DELETE FROM case_ WHERE snapshot_id IN ({placeholders})"),
            ("observation",
             "DELETE FROM observation WHERE artefact_id IN"
             f" (SELECT id FROM artefact WHERE snapshot_id IN ({placeholders}))"),
            ("artefact", f"DELETE FROM artefact WHERE snapshot_id IN ({placeholders})"),
            ("run", f"DELETE FROM run WHERE snapshot_id IN ({placeholders})"),
            ("snapshot", f"DELETE FROM snapshot WHERE id IN ({placeholders})"),
        ):
            cur = conn.execute(sql, ids)
            deleted_rows[table] = cur.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    removed = []
    root = Path(blob_dir or blobs.blob_dir())
    for item in decision["blobs"]:
        path = root / item["sha"][:2] / item["sha"][2:]
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        removed.append(item)
        shard = path.parent
        try:
            shard.rmdir()                     # only succeeds when the shard is now empty
        except OSError:
            pass
    return {"applied": True, "deleted": {"snapshots": list(ids), "rows": deleted_rows},
            "blobs": removed, "plan": decision}
