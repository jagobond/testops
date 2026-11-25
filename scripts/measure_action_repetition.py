"""Measure the TESTOPS-28 review's repetition count over the 94 demo-product actions.

  before: the actions as stored in the pinned run (written by level_fitness 0.10.1)
  after:  the actions the working-tree analyser writes for the same scenario set

The measure is the review's own: an action whose two sentences share a content word, read from the
action box as the page renders it. The box refers to the step as "this step" because the step is
quoted above it, so the step's own words are not counted as the action's prose - that substitution
is what makes the review's number 2 rather than 5.

    .venv/Scripts/python.exe scripts/t209_repetition.py
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from testops import rebuild  # noqa: E402
from testops.store import db  # noqa: E402

PINNED_RUN = "demo-product-levels-20261122T011316"

STOPWORDS = frozenset("""
    a an the this that these those it its they them their there here and or but nor so if then
    than as of to in on at for with by from into over under about is are was were be been being
    am do does did has have had no not
""".split())
WORD = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)*")


def content(text: str) -> list[str]:
    return [word for word in WORD.findall(text.lower()) if word not in STOPWORDS]


def sentences(text: str) -> list[str]:
    """The action box's sentences: the stored action split at its semicolons, as the page does."""
    return [part for part in re.split(r"[.!?;]\s+", text.strip()) if part.strip()]


def as_page_writes_it(action: str, step: str) -> str:
    """The action with its quoted copy of the step referred to as "this step" (TESTOPS-26)."""
    for form in (f'the step "{step}"', f'step "{step}"', f'"{step}"'):
        if step and form in action:
            return action.replace(form, "this step", 1)
    return action


def repeats(action: str) -> tuple[str, ...] | None:
    parts = sentences(action)
    if len(parts) < 2:
        return None
    first = set(content(parts[0]))
    shared = first & set(content(" ".join(parts[1:])))
    return tuple(sorted(shared)) or None


def report(label: str, actions: list[str]) -> int:
    hits = [(action, repeats(action)) for action in actions]
    hits = [(action, shared) for action, shared in hits if shared]
    long_actions = [a for a in actions if len(sentences(a)) > 2]
    print(f"{label}: {len(actions)} actions, {len(hits)} repeat a content word, "
          f"{len(long_actions)} carry more than two sentences")
    for action, shared in hits:
        print(f"  repeated {shared}: {action[:140]}")
    return len(hits)


def main() -> int:
    conn = db.connect()
    try:
        before = [as_page_writes_it(row[0], row[1]) for row in conn.execute(
            "SELECT proposed_action, assertion_text FROM claim WHERE run_id = ? ORDER BY id",
            (PINNED_RUN,))]
        snapshot = conn.execute("SELECT snapshot_id FROM run WHERE id = ?",
                                (PINNED_RUN,)).fetchone()[0]
        claims, _stats, _snap = rebuild.rebuild(conn, snapshot)
        after = [as_page_writes_it(claim.detail["proposed_action"],
                                   claim.detail["assertion_text"]) for claim in claims]
        counts: dict[str, int] = {}
        for claim in claims:
            counts[claim.verdict] = counts.get(claim.verdict, 0) + 1

        hit_before = report("BEFORE (stored, level_fitness 0.10.1)", before)
        print()
        hit_after = report("AFTER  (rebuilt, working tree)", after)
        print()
        print(f"after: {len(after)} claims {counts}, snapshot {snapshot}")
        print(f"repetition count {hit_before} of {len(before)} -> {hit_after} of {len(after)}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
