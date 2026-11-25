"""TESTOPS-91 AC3: measure the repair round live, before and after, on the same ten real cases.

"Before" is what the feature served without the citation repair: a first reply that parsed and
passed the check. "After" is what it serves with it. Both are read off the same run, so the two
numbers describe the same calls in the same conditions - the only difference is whether a reply that
was one field short was asked for again.

The product store is opened read-only; the ledger is a throwaway store. The model is whatever the
deployment resolves at call time - here the local ``az`` token and ``deepseek-flash``.

    env -u PYTHONPATH -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
      C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe \
      factory/reports/2026-11-24/tes91_measure.py

Writes ``tes91-measurement.json`` and prints one line per case.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from testops.judgement import agent, client  # noqa: E402
from testops.store import db  # noqa: E402

STORE = ROOT / "data" / "testops.db"
OUT = Path(__file__).with_name("tes91-measurement.json")

# The same ten cases TESTOPS-90 measured, so before/after is a comparison and not a new sample.
CASES = (
    "case-demo-booking-levels-20261124T123451-01",
    "case-demo-booking-levels-20261124T123451-02",
    "case-demo-booking-levels-20261124T123451-03",
    "case-demo-booking-levels-20261124T123451-04",
    "case-demo-booking-levels-20261124T123451-05",
    "case-demo-booking-levels-20261124T114627-01",
    "case-demo-booking-levels-20261124T114627-02",
    "case-demo-booking-levels-20261124T114627-03",
    "case-demo-booking-levels-20261124T114627-04",
    "case-demo-booking-levels-20261124T114627-05",
)


def _read_only(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def main() -> int:
    read = _read_only(STORE)
    cfg = agent.config()
    print(f"model={cfg.model} configured={cfg.configured} endpoint={cfg.endpoint}")
    if not cfg.configured:
        print(cfg.why_not)
        return 2

    scratch = Path(tempfile.mkdtemp(prefix="tes91-"))
    ledger = db.connect(scratch / "ledger.db")
    pause = float(os.environ.get("TES91_PAUSE", "8"))
    rows = []
    for index, case_id in enumerate(CASES):
        if index and pause:
            time.sleep(pause)          # the endpoint throttles a burst; space the calls as a reader would
        record = agent.case_record(read, case_id)
        if record is None:
            print(f"{case_id}: not in the store")
            continue
        started = time.monotonic()
        raw: list[str] = []

        def ask(system, user, model, **kwargs):
            completion = client.complete(system, user, model, **kwargs)
            raw.append(completion.text)
            return completion

        outcome = agent.explain_case(ledger, record, cfg=cfg, completer=ask)
        wall_ms = int((time.monotonic() - started) * 1000)
        call = ledger.execute("SELECT wall_ms FROM agent_call WHERE id=?",
                              (outcome.call_id,)).fetchone()
        # What the first reply was, in the ticket's own words: a usable answer, one field short, or
        # unusable. The first raw reply is all that is needed to say which.
        first = agent.read_reply(raw[0]) if raw else agent.read_reply("")
        row = {
            "case": case_id,
            "state": outcome.state,
            "accepted_after": outcome.served,
            "accepted_before": outcome.served and outcome.repairs == 0,
            "repairs": outcome.repairs,
            "first_reply_cause": first.cause or "usable",
            "repair_kind": ("citations" if first.cause == agent.REPAIRABLE
                            else "violations" if outcome.repairs else ""),
            "tokens_in": outcome.tokens_in,
            "tokens_out": outcome.tokens_out,
            "wall_ms": wall_ms,
            "call_wall_ms": int(call["wall_ms"]) if call else 0,
            "violations": list(outcome.violations),
            "text": outcome.text,
            "raw_replies": [text[:4000] for text in raw],
            "detail": outcome.detail,
            "cause": outcome.cause,
        }
        rows.append(row)
        print(f"{case_id[-22:]:24} {outcome.state:15} repairs={outcome.repairs} "
              f"before={'Y' if row['accepted_before'] else 'n'} "
              f"after={'Y' if row['accepted_after'] else 'n'} "
              f"in={outcome.tokens_in:5} out={outcome.tokens_out:4} {wall_ms:6}ms "
              f"{row['repair_kind'] or ''}")

    def rate(picked):
        return round(len(picked) / len(rows), 3) if rows else None

    before = [r for r in rows if r["accepted_before"]]
    after = [r for r in rows if r["accepted_after"]]
    needed = [r for r in rows if r["repairs"]]
    repaired = [r for r in rows if r["state"] == agent.STATE_FRESH_REPAIRED]
    citation = [r for r in needed if r["repair_kind"] == "citations"]
    single = [r for r in rows if not r["repairs"]]
    summary = {
        "cases": len(rows),
        "accepted_before": len(before),
        "accepted_after": len(after),
        "accept_rate_before": rate(before),
        "accept_rate_after": rate(after),
        "needed_repair": len(needed),
        "needed_citation_repair": len(citation),
        "needed_violation_repair": len([r for r in needed if r["repair_kind"] == "violations"]),
        "repairs_succeeded": len(repaired),
        "repairs_failed": len(needed) - len(repaired),
        "mean_tokens_in_single_call": (round(sum(r["tokens_in"] for r in single) / len(single), 1)
                                       if single else None),
        "mean_tokens_out_single_call": (round(sum(r["tokens_out"] for r in single) / len(single), 1)
                                        if single else None),
        "mean_tokens_in_repaired": (round(sum(r["tokens_in"] for r in needed) / len(needed), 1)
                                    if needed else None),
        "mean_tokens_out_repaired": (round(sum(r["tokens_out"] for r in needed) / len(needed), 1)
                                     if needed else None),
        "total_tokens_in": sum(r["tokens_in"] for r in rows),
        "total_tokens_out": sum(r["tokens_out"] for r in rows),
        "total_wall_ms": sum(r["wall_ms"] for r in rows),
        "model": cfg.model,
    }
    OUT.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    print(f"written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
