"""Command line: collect, analyse, score, report.

Deliberately thin. Every command is a function call into the same code the service will use.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import cases, retention
from .config import KEYS_DIR, load_env, project
from .store import db
from .web.app import serve
from .pipeline import run_duplication, run_level_fitness
from .score import level as level_score
from .score.metrics import control_expectations, duplication_score


def cmd_duplicate(args) -> int:
    env = load_env()
    p = project(args.project)
    res = run_duplication(p, env["GITHUB_PAT"])
    print(f"run      {res.run_id}")
    print(f"snapshot {res.snapshot_id}")
    print(f"cases    {len(res.case_ids)} ({res.case_id or 'none'})")
    print(f"stats    {json.dumps(res.stats)}")
    print(f"claims   {len(res.claims)}")
    by = {}
    for c in res.claims:
        by[c.detail.get("layer", "?")] = by.get(c.detail.get("layer", "?"), 0) + 1
    print(f"by layer {json.dumps(by)}")
    if args.key:
        exp = control_expectations(Path(args.key))
        print("score    " + json.dumps(duplication_score(res.claims, exp), indent=1))
    return 0


def cmd_levels(args) -> int:
    env = load_env()
    p = project(args.project)
    res = run_level_fitness(p, env["GITHUB_PAT"])
    print(f"run      {res.run_id}")
    print(f"case     {res.case_id}")
    print(f"stats    {json.dumps(res.stats)}")
    counts = {}
    for c in res.claims:
        counts[c.verdict] = counts.get(c.verdict, 0) + 1
    print(f"verdicts {json.dumps(counts)}")
    if args.key:
        key = level_score.load_key(Path(args.key))
        scored = level_score.score(res.claims, key)
        for row in scored.pop("rows", []):
            if row["got"] != row["expected"]:
                print(f"  MISMATCH {row['scenario'][:50]:50} got={row['got']:10} expected={row['expected']}")
        print("score    " + json.dumps(scored, indent=1))
    return 0


def cmd_cases(args) -> int:
    conn = db.connect()
    rows = cases.list_cases(conn, args.project, args.limit)
    if not rows:
        print("no cases")
        return 0
    for r in rows:
        print(f"{r['id']:44} {r['state']:14} findings={r['findings']:<3} {r['analyser']}")
    return 0


def cmd_case_set(args) -> int:
    conn = db.connect()
    cases.set_state(conn, args.case, args.state, args.actor, args.note or "")
    state = cases.state_of(conn, args.case)
    print(f"{args.case} -> {state}")
    for f in cases.findings_for(conn, args.case):
        fp = cases.fingerprint if False else f["fingerprint"]
        sup = cases.suppressed(conn, fp)
        print(f"  {'suppressed' if sup else 'active    '} {fp}  {f['title'][:60]}")
    return 0


def cmd_serve(args) -> int:
    serve(args.port, args.host)
    return 0


def _size(value: int) -> str:
    """Bytes as a reader-sized figure, with enough precision to compare two close measurements."""
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value / (1024 * 1024):.2f} MB"


def _print_report(conn) -> dict:
    footprint = retention.store_footprint(conn)
    print(f"store      {footprint['row_total']} rows · {_size(footprint['db_bytes'])} in the database "
          f"· {_size(footprint['bytes'] - footprint['db_bytes'])} in {footprint['files']} blob files")
    print()
    print(f"{'snapshot':42} {'project':12} {'age':9} {'rows':>7} {'bytes':>10}  "
          f"{'decision':8} {'suppression':11}")
    for row in retention.report_rows(conn):
        print(f"{row['id']:42} {row['project']:12} {row['age']:9} {row['rows']:>7} "
              f"{_size(row['bytes']):>10}  {'yes' if row['decided'] else 'no':8} "
              f"{'yes' if row['suppressed'] else 'no':11}")
    return footprint


def _print_plan(plan: dict) -> None:
    keep = plan["keep"]
    deleting = [row for row in plan["snapshots"] if row["action"] == "delete"]
    kept = [row for row in plan["snapshots"] if row["action"] == "keep"]
    print()
    # N is per project, not for the store as a whole (TESTOPS-30). Saying so here is the difference
    # between a reader who expects two rows left and a reader who can see three.
    print(f"prune plan — keep {keep} per project "
          f"(the {keep} most recent snapshot{'s' if keep != 1 else ''} in each project)")
    # The counts, so the reader can check what N meant on their own store rather than trust the
    # sentence above.
    held: dict[str, int] = {}
    surviving: dict[str, int] = {}
    for row in plan["snapshots"]:
        held[row["project"]] = held.get(row["project"], 0) + 1
        if row["action"] == "keep":
            surviving[row["project"]] = surviving.get(row["project"], 0) + 1
    if held:
        print("  per project (kept / held):")
        width = max(len(name) for name in held)
        for name in sorted(held):
            print(f"    {name:{width}}  {surviving.get(name, 0)} / {held[name]}")
    if not deleting:
        print("  nothing to delete: every snapshot is protected or within the keep window")
    for row in deleting:
        print(f"  delete {row['id']} ({row['project']}, age {row['age']}, {row['rows']} rows, "
              f"{_size(row['bytes'])})")
    if plan["blobs"]:
        print(f"  delete {len(plan['blobs'])} unreferenced blob files, {_size(plan['blob_bytes'])}")
    else:
        print("  delete 0 blob files: every blob is still referenced by a surviving artefact")
    # One line per protection rule, not per snapshot: the point is which rule bound, and a reader
    # counting fifteen identical lines learns nothing.
    tally: dict[str, int] = {}
    for row in kept:
        for reason in row["reasons"]:
            tally[reason] = tally.get(reason, 0) + 1
    if tally:
        print("  kept:")
        for reason in sorted(tally):
            print(f"    {tally[reason]:3}  {reason}")


def cmd_retention(args) -> int:
    conn = db.connect()
    try:
        before = _print_report(conn)
        if not args.prune:
            if args.keep is not None or args.yes:
                print("\n--keep/--yes only apply with --prune; this run was report-only.")
            return 0
        if args.keep is None:
            print("\nretention --prune needs --keep N (N per project). Nothing was deleted.")
            return 2
        # Print the plan before acting: a reader must see what is about to go while it is still
        # there. ``prune`` re-derives it rather than trusting this one, so the printed list and the
        # deleted list cannot be two different things chosen by the caller.
        _print_plan(retention.plan(conn, args.keep))
        if not args.yes:
            print("\nRefusing to prune without --yes. Nothing was deleted.")
            return 2
        result = retention.prune(conn, args.keep, yes=True)
        deleted = result["deleted"]
        rows = sum(deleted["rows"].values())
        print(f"\npruned {len(deleted['snapshots'])} snapshots, {rows} rows, "
              f"{len(result['blobs'])} blob files "
              f"({_size(sum(item['bytes'] for item in result['blobs']))})")
        # SQLite reuses freed pages; it does not return them to the file system. Saying so is the
        # difference between a measured deletion and an implied saving.
        after = retention.store_footprint(conn)
        print(f"database   {_size(before['db_bytes'])} -> {_size(after['db_bytes'])}; freed pages are "
              f"reused by later runs, not shrunk here")
        return 0
    finally:
        conn.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="testops")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("duplicate", help="run deterministic duplication analysis")
    d.add_argument("--project", required=True)
    d.add_argument("--key", default=None, help="control key json to score against")
    d.set_defaults(func=cmd_duplicate)

    lv = sub.add_parser("levels", help="run level-fitness analysis")
    lv.add_argument("--project", required=True)
    lv.add_argument("--key", default=None, help="held-out key json to score against")
    lv.set_defaults(func=cmd_levels)

    cs = sub.add_parser("cases", help="list cases")
    cs.add_argument("--project", default=None)
    cs.add_argument("--limit", type=int, default=40)
    cs.set_defaults(func=cmd_cases)

    st = sub.add_parser("case-set", help="record a human decision on a case")
    st.add_argument("case")
    st.add_argument("--state", required=True, choices=list(cases.STATES))
    st.add_argument("--actor", default="harry")
    st.add_argument("--note", default="")
    st.set_defaults(func=cmd_case_set)

    sv = sub.add_parser("serve", help="run the local UI")
    sv.add_argument("--port", type=int, default=8787)
    sv.add_argument("--host", default="127.0.0.1")
    sv.set_defaults(func=cmd_serve)

    rt = sub.add_parser("retention", help="report store size per snapshot; prune only on request")
    rt.add_argument("--prune", action="store_true",
                    help="delete snapshots outside the --keep window (N per project); "
                         "does nothing without --yes")
    rt.add_argument("--keep", type=int, default=None,
                    help="keep N per project: the N most recent snapshots in each project survive, "
                         "and older ones are candidates for deletion")
    rt.add_argument("--yes", action="store_true", help="confirm the deletion")
    rt.set_defaults(func=cmd_retention)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
