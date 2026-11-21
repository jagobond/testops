"""Rebuild the level-fitness claim set from a stored snapshot, and check the corpus numbers.

    .venv/Scripts/python.exe scripts/replay_levels.py --snapshot cotw-levels-20261121-a3f19853-r2

The rebuild reads one snapshot and nothing else: the test arm's features and step definitions, the
product arm's source the surfaces were read from, the run's blind spots, and the observations behind
every claim. It never touches a live source and never borrows a second snapshot.

That last sentence is TESTOPS-14's change. This script used to read the test arm out of a
duplication snapshot taken at the same commit, and its only guard was that the two commits agreed.
A snapshot that records both arms makes the substitution unnecessary; a snapshot that does not is
now refused with its reason, rather than quietly completed from somewhere else.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from testops import rebuild  # noqa: E402
from testops.store import db  # noqa: E402

# TESTOPS-11's corpus-level criteria, asserted here rather than in a fixture because the point of
# the ticket is what the analyser does to the real 94 claims. The meta claim is the one TESTOPS-10
# promoted on the single word "store"; it must go back to `unplaced`, and restraint must not become
# a blanket - no more than three claims may end up unplaced, and no real finding may move.
META_CLAIM = "that count is correct for the store it was run against"
CORPUS_CLAIMS = 94
MAX_UNPLACED = 3
FINDINGS = {"gap": 1, "review": 2}


def accept(claims) -> list[str]:
    """Return the corpus-level problems with this run, in the ticket's terms."""
    problems: list[str] = []
    if len(claims) != CORPUS_CLAIMS:
        problems.append(f"the snapshot holds {len(claims)} claims, not {CORPUS_CLAIMS}; "
                        f"the numbers below are not the ticket's numbers")

    unplaced = [c for c in claims if c.verdict == "unplaced"]
    if len(unplaced) > MAX_UNPLACED:
        problems.append(f"{len(unplaced)} claims are unplaced, above the {MAX_UNPLACED} "
                        f"the ticket allows: restraint became a blanket")

    by_text = {c.detail["assertion_text"].strip(): c for c in claims}
    meta = by_text.get(META_CLAIM)
    if meta is None:
        problems.append(f"the corpus no longer contains {META_CLAIM!r}")
    elif meta.verdict != "unplaced":
        problems.append(f"{META_CLAIM!r} is {meta.verdict}, not unplaced - it asserts a meta "
                        f"property and says nothing about what the count is compared with")

    for verdict, want in FINDINGS.items():
        got = sum(1 for c in claims if c.verdict == verdict)
        if got != want:
            problems.append(f"{got} {verdict} verdicts, not {want}: restraint moved a real finding")
    return problems


def newest_levels_snapshot(conn, project: str = "cotw") -> str:
    row = conn.execute(
        "SELECT id FROM snapshot WHERE project = ? AND id LIKE '%-levels-%'"
        " ORDER BY created_at DESC, rowid DESC LIMIT 1", (project,)).fetchone()
    if row is None:
        raise SystemExit(f"no levels snapshot for {project!r}; run `testops levels --project "
                         f"{project}` first")
    return row["id"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=None,
                    help="snapshot to rebuild (default: the newest levels snapshot for cotw)")
    ap.add_argument("--json", default="", help="write every claim, as JSON, to this path")
    ap.add_argument("--baseline-run", default="", help="compare verdicts with this stored run")
    ap.add_argument("--acceptance", action="store_true",
                    help="assert TESTOPS-11's corpus-level criteria and fail if any is broken")
    args = ap.parse_args(argv)

    conn = db.connect()
    try:
        snapshot = args.snapshot or newest_levels_snapshot(conn)
        try:
            claims, stats, snap = rebuild.rebuild(conn, snapshot)
        except rebuild.SnapshotNotSelfContained as exc:
            print(f"cannot rebuild {snapshot}: {exc}")
            return 1

        counts: dict[str, int] = {}
        for c in claims:
            counts[c.verdict] = counts.get(c.verdict, 0) + 1
        print(json.dumps({"snapshot": snapshot,
                          "arms": {"test": f"{snap.test_slug}@{snap.test_commit[:8]}",
                                   "product": f"{snap.product_slug}@{snap.product_commit[:8]}"},
                          "stats": stats, "claims": len(claims),
                          "verdicts": counts}, indent=1))

        failed = 0
        if args.acceptance:
            problems = accept(claims)
            for problem in problems:
                print(f"ACCEPTANCE FAILED: {problem}")
            if problems:
                failed = 1
            else:
                print(f"acceptance: {len(claims)} claims, "
                      f"{counts.get('unplaced', 0)} unplaced (max {MAX_UNPLACED}), "
                      f"{counts.get('gap', 0)} gap / {counts.get('review', 0)} review, "
                      f"{META_CLAIM!r} unplaced - PASS")

        if args.baseline_run:
            before = {(row["subject_ref"], row["assertion_line"]):
                      (row["assertion_text"], row["verdict"], json.loads(row["support"]))
                      for row in conn.execute(
                          "SELECT subject_ref, assertion_line, assertion_text, verdict, support"
                          " FROM claim WHERE run_id = ?", (args.baseline_run,))}
            after = {(c.subject_ref, c.detail["assertion_line"]):
                     (c.detail["assertion_text"], c.verdict, list(c.detail["support"]))
                     for c in claims}
            moved = {key: (before[key][1], after[key][1]) for key in before
                     if key in after and before[key][1] != after[key][1]}
            support_changed = {key: (before[key][2], after[key][2]) for key in before
                               if key in after and before[key][2] != after[key][2]}
            print(f"baseline {args.baseline_run}: {len(before)} claims, now {len(after)}")
            print(f"moved {len(moved)}")
            for key, (old, new) in moved.items():
                print(f"  {old:9} -> {new:9}  {before[key][0]}")
            print(f"support differs in {len(support_changed)} of {len(after)} claims")
            different = sorted(set(before) ^ set(after))
            if different:
                print(f"claims present in one run only: {len(different)}")
                for key in different[:10]:
                    print(f"  {key}")

        if args.json:
            Path(args.json).write_text(json.dumps([
                {"subject_ref": c.subject_ref, "statement": c.statement, "verdict": c.verdict,
                 "detail": c.detail} for c in claims], indent=1, ensure_ascii=False),
                encoding="utf-8")
            print(f"wrote {args.json}")
    finally:
        conn.close()
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
