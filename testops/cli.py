"""Command line: collect, analyse, score, report.

Deliberately thin. Every command is a function call into the same code the service will use.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import cases
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

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
