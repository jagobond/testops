"""Scoring level-fitness verdicts against the held-out key."""
from __future__ import annotations

import json
from pathlib import Path


def load_key(path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        for k in ("scenarios", "items", "judgements"):
            if k in data and isinstance(data[k], list):
                return data[k]
        return [v for v in data.values() if isinstance(v, list)][0]
    return data


def _norm_feature(path: str) -> str:
    return Path(path).stem


# The key was annotated in the old vocabulary. Harry's rulings map it onto the new one: a test that is at the
# narrowest interaction is "distinct"; one that re-proves a narrower claim through a wide interaction is a
# "review" candidate. Nothing in the old vocabulary maps to deletion.
VERDICT_MAP = {"optimal": "distinct", "necessary": "distinct", "overbuilt": "review",
               "distinct": "distinct", "review": "review", "unplaced": "unplaced",
               # A claim the product already publishes is at the right level - the browser is the
               # waste, and the level verdict itself is `distinct` (TESTOPS-72).
               "repeats_product": "distinct"}


def score(claims: list, key: list[dict]) -> dict:
    # Key identifies scenarios by feature stem + scenario name.
    truth = {(k["feature"], k["scenario"]): k for k in key}
    matched, verdict_ok, surface_ok, abstained, wrong = 0, 0, 0, 0, 0
    rows = []
    seen: set[tuple[str, str]] = set()
    for c in claims:
        ref = c.subject_ref
        path_part, _, sc_name = ref.partition("#")
        feature = _norm_feature(path_part.replace("scenario:", ""))
        truth_row = truth.get((feature, sc_name))
        if not truth_row:
            continue
        # One scenario can now yield two claims (a split assertion). Score the scenario once, on its first
        # claim, so the denominator stays the number of keyed scenarios.
        if (feature, sc_name) in seen:
            continue
        seen.add((feature, sc_name))
        matched += 1
        if c.verdict == "unplaced":
            abstained += 1
        ok = VERDICT_MAP.get(c.verdict, c.verdict) == VERDICT_MAP.get(truth_row["verdict"], truth_row["verdict"])
        verdict_ok += ok
        if not ok and c.verdict != "unplaced":
            wrong += 1
        surface_ok += str(c.detail.get("cheapest", "")).strip().lower() == str(
            truth_row.get("cheapest_surface_sufficient", "")).strip().lower()
        rows.append({"scenario": sc_name,
                     "got": VERDICT_MAP.get(c.verdict, c.verdict),
                     "expected": VERDICT_MAP.get(truth_row["verdict"], truth_row["verdict"]),
                     "raw_expected": truth_row["verdict"],
                     "cheapest_got": c.detail.get("cheapest", ""),
                     "cheapest_expected": truth_row.get("cheapest_surface_sufficient", "")})

    true_overbuilt = {k for k, v in truth.items() if v["verdict"] == "overbuilt"}
    found_overbuilt = set()
    for c in claims:
        path_part, _, sc_name = c.subject_ref.partition("#")
        feature = _norm_feature(path_part.replace("scenario:", ""))
        # Only scenarios the key actually covers can count towards precision. Counting flags on unscored
        # scenarios inflated the denominator and turned a good run into a misleading number.
        if c.verdict == "review" and (feature, sc_name) in truth:
            found_overbuilt.add((feature, sc_name))
    tp = len(true_overbuilt & found_overbuilt)
    return {
        "matched_key_scenarios": matched,
        "key_scenarios": len(truth),
        "verdict_agreement": round(verdict_ok / matched, 3) if matched else None,
        "cheapest_surface_agreement": round(surface_ok / matched, 3) if matched else None,
        "abstained": abstained,
        "confidently_wrong": wrong,
        "overbuilt_precision": round(tp / len(found_overbuilt), 3) if found_overbuilt else None,
        "overbuilt_recall": round(tp / len(true_overbuilt), 3) if true_overbuilt else None,
        "true_overbuilt": len(true_overbuilt),
        "found_overbuilt": len(found_overbuilt),
        "rows": rows,
    }
