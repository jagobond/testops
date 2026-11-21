"""Scoring against held-out keys. The only door to the answers."""
from __future__ import annotations

import json
from pathlib import Path


def control_expectations(key_path: Path) -> dict:
    data = json.loads(Path(key_path).read_text(encoding="utf-8"))
    return data.get("expected_finding", {})


def duplication_score(claims: list, expected: dict) -> dict:
    """Compare a duplication run against a control key.

    Reports what the key reports: claim groups, surplus copies, and intra-level duplicates. A higher-level
    copy is not "delete me" — the key is explicit that each adds a mechanism — so the metric is whether the
    tool found the *groups*, and separately whether it found repeats within a level.
    """
    cross = [c for c in claims if c.verdict == "duplicate" and not c.detail.get("intra_level")]
    intra = [c for c in claims if c.detail.get("intra_level")]
    groups = {c.detail.get("signature") for c in cross}
    exp_groups = expected.get("claim_groups_tested_at_three_levels", 0)

    return {
        "claim_groups_found": len(groups),
        "claim_groups_expected": exp_groups,
        "group_recall": round(len(groups) / exp_groups, 3) if exp_groups else None,
        "surplus_copies_flagged": len(cross),
        "intra_level_found": len(intra),
        "intra_level_expected": expected.get("intra_level_duplicates", 0),
        "intra_level_recall": (round(len(intra) / expected["intra_level_duplicates"], 3)
                               if expected.get("intra_level_duplicates") else None),
        "by_layer": {l: sum(1 for c in cross if c.detail.get("layer") == l)
                     for l in {c.detail.get("layer") for c in cross}},
    }
