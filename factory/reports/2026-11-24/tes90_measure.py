"""TESTOPS-90 AC4: run the agent over ten real cases, against the real model, and measure it.

The record for each case is read from the product store (opened read-only); the agent's ledger and
cache are written to a throwaway store, so measuring never touches the product's memory. The model
is whatever the deployment resolves at call time - here the local ``az`` token and ``deepseek-flash``.

    env -u PYTHONPATH -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
      C:/Users/Chester/Projects/testops/.venv/Scripts/python.exe \
      factory/reports/2026-11-24/tes90_measure.py

Writes ``factory/reports/2026-11-24/tes90-measurement.json`` and prints one line per case.
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
OUT = Path(__file__).with_name("tes90-measurement.json")

# Ten cases from the stored run of 2026-11-24: five from each of the two level-fitness runs, and
# including 123451-05, the case whose rejected reply is the ticket's evidence.
CASES = (
    "case-restfulbooker-levels-20261124T123451-01",
    "case-restfulbooker-levels-20261124T123451-02",
    "case-restfulbooker-levels-20261124T123451-03",
    "case-restfulbooker-levels-20261124T123451-04",
    "case-restfulbooker-levels-20261124T123451-05",
    "case-restfulbooker-levels-20261124T114627-01",
    "case-restfulbooker-levels-20261124T114627-02",
    "case-restfulbooker-levels-20261124T114627-03",
    "case-restfulbooker-levels-20261124T114627-04",
    "case-restfulbooker-levels-20261124T114627-05",
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

    scratch = Path(tempfile.mkdtemp(prefix="tes90-"))
    ledger = db.connect(scratch / "ledger.db")
    pause = float(os.environ.get("TES90_PAUSE", "8"))
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
        row = {
            "case": case_id,
            "state": outcome.state,
            "accepted": outcome.served,
            "repairs": outcome.repairs,
            "tokens_in": outcome.tokens_in,
            "tokens_out": outcome.tokens_out,
            "wall_ms": wall_ms,
            "call_wall_ms": int(call["wall_ms"]) if call else 0,
            "violations": list(outcome.violations),
            "text": outcome.text,
            "raw_replies": [text[:2000] for text in raw],
            "detail": outcome.detail,
            "cause": outcome.cause,
        }
        rows.append(row)
        print(f"{case_id[-22:]:24} {outcome.state:9} repairs={outcome.repairs} "
              f"in={outcome.tokens_in:5} out={outcome.tokens_out:4} {wall_ms:6}ms "
              f"{'' if outcome.served else (' ! ' + '; '.join(outcome.violations))}")

    accepted = [r for r in rows if r["accepted"]]
    summary = {
        "cases": len(rows),
        "accepted": len(accepted),
        "accept_rate": round(len(accepted) / len(rows), 3) if rows else None,
        "repaired_to_acceptance": len([r for r in accepted if r["repairs"]]),
        "mean_tokens_in": round(sum(r["tokens_in"] for r in rows) / len(rows), 1) if rows else None,
        "mean_tokens_out": round(sum(r["tokens_out"] for r in rows) / len(rows), 1) if rows else None,
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
