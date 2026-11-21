"""Re-run the level-fitness analyser over a stored snapshot, without touching a live source.

Why this exists: the ticket asks for the real run's numbers "measured by re-running the analyser
over the same snapshot". The pipeline itself collects from GitHub, which makes a "before/after"
comparison impossible to repeat. Everything the analyser reads is in the store - artefacts for
the product arm, and content-addressed blobs - so this script rebuilds the same inputs from those
rows and calls the same `level_fitness.analyse`.

    .venv/Scripts/python.exe scripts/replay_levels.py --snapshot cotw-levels-20261121-a3f19853

The test repository's files are not recorded as artefacts of a level snapshot (that is a product
gap, reported with TESTOPS-10), so the test arm is read from the artefact rows of the duplication
snapshot taken at the same commit - `--tests-snapshot`, defaulting to `cotw-20261120-a3f19853`.
The commits are checked to agree, so a mismatch is an error rather than a quiet substitution.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from testops import blobs  # noqa: E402
from testops.analysers import level_fitness  # noqa: E402
from testops.extract import csproj, gherkin, stepbindings  # noqa: E402
from testops.store import db  # noqa: E402
from testops.surfaces import discover as surface_discovery  # noqa: E402

TEST_SLUG = "jagobond/cotw-bdd"
PRODUCT_SLUG = "jagobond/cotw-continuity"


def _uri_parts(uri: str) -> tuple[str, str, str] | None:
    """`github:slug@commit:path` -> (slug, commit, path). Anything else is not a repo file."""
    if not uri.startswith("github:"):
        return None
    body = uri[len("github:"):]
    if "@" not in body or ":" not in body.split("@", 1)[1]:
        return None
    slug, rest = body.split("@", 1)
    commit, path = rest.split(":", 1)
    return slug, commit, path


def load_snapshot(conn, snapshot_id: str):
    row = conn.execute("SELECT * FROM snapshot WHERE id = ?", (snapshot_id,)).fetchone()
    if row is None:
        raise SystemExit(f"no such snapshot: {snapshot_id}")
    versions = json.loads(row["artefact_versions"])
    artefacts = []
    for art in conn.execute("SELECT uri, kind, blob_sha FROM artefact WHERE snapshot_id = ?", (snapshot_id,)):
        parts = _uri_parts(art["uri"])
        if parts:
            artefacts.append((*parts, art["kind"], art["blob_sha"]))
    return versions, artefacts


def inputs_for(conn, snapshot_id: str, tests_snapshot: str):
    versions, artefacts = load_snapshot(conn, snapshot_id)
    test_commit = versions[TEST_SLUG]
    test_files = {path: (sha, kind) for slug, commit, path, kind, sha in artefacts
                  if slug == TEST_SLUG and commit == test_commit}
    if test_files:
        raise SystemExit("this snapshot records its own test artefacts; no substitution is needed")
    product_texts = {path: blobs.text(sha)
                     for slug, commit, path, kind, sha in artefacts if slug == PRODUCT_SLUG}

    test_versions, test_artefacts = load_snapshot(conn, tests_snapshot)
    if test_versions.get(TEST_SLUG) != test_commit:
        raise SystemExit(f"{tests_snapshot} is at {test_versions.get(TEST_SLUG)}, "
                         f"not the level snapshot's {test_commit}")
    texts = {path: blobs.text(sha) for slug, commit, path, kind, sha in test_artefacts
             if slug == TEST_SLUG and commit == test_commit}
    kinds = {path: kind for slug, commit, path, kind, sha in test_artefacts
             if slug == TEST_SLUG and commit == test_commit}
    return test_commit, texts, kinds, product_texts


def analyse(conn, snapshot_id: str, tests_snapshot: str):
    commit, texts, kinds, product_texts = inputs_for(conn, snapshot_id, tests_snapshot)

    excludes: list[str] = []
    for path, text in texts.items():
        if kinds[path] == "build":
            excludes.extend(csproj.excluded_patterns(text))

    driver_map = stepbindings.build_driver_map(texts)
    features, bindings, dormant = [], [], []
    for path, text in sorted(texts.items()):
        kind = kinds[path]
        if kind == "feature":
            if not csproj.is_active(path, excludes):
                dormant.append(path)
                continue
            f = gherkin.parse(path, text)
            if f:
                features.append(f)
        elif kind == "stepdef":
            bindings.extend(stepbindings.parse_file(path, text, driver_map))

    surfaces = surface_discovery.discover(product_texts)
    claims = level_fitness.analyse(
        features, bindings, surfaces,
        lambda p: f"github:{TEST_SLUG}@{commit}:{p}",
        {"calls": 0, "tokens_in": 0, "tokens_out": 0},
        sources_missing=[], commit=commit,
    )
    return claims, {"features": len(features), "bindings": len(bindings),
                    "scenarios": sum(len(f.scenarios) for f in features),
                    "dormant": len(dormant), "surfaces": len(surfaces)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default="cotw-levels-20261121-a3f19853")
    ap.add_argument("--tests-snapshot", default="cotw-20261120-a3f19853")
    ap.add_argument("--json", default="", help="write every claim, as JSON, to this path")
    ap.add_argument("--baseline-run", default="", help="compare verdicts with this stored run")
    args = ap.parse_args(argv)

    conn = db.connect()
    claims, stats = analyse(conn, args.snapshot, args.tests_snapshot)

    counts: dict[str, int] = {}
    for c in claims:
        counts[c.verdict] = counts.get(c.verdict, 0) + 1
    print(json.dumps({"stats": stats, "claims": len(claims), "verdicts": counts}, indent=1))

    if args.baseline_run:
        before = {row["assertion_text"]: row["verdict"] for row in conn.execute(
            "SELECT assertion_text, verdict FROM claim WHERE run_id = ?", (args.baseline_run,))}
        after = {c.detail["assertion_text"]: c.verdict for c in claims}
        moved = {text: (before[text], after[text]) for text in before
                 if text in after and before[text] != after[text]}
        print(f"baseline {args.baseline_run}: {len(before)} claims, now {len(after)}")
        print(f"moved {len(moved)}")
        for text, (b, a) in moved.items():
            print(f"  {b:9} -> {a:9}  {text}")

    if args.json:
        Path(args.json).write_text(json.dumps([
            {"subject_ref": c.subject_ref, "statement": c.statement, "verdict": c.verdict,
             "detail": c.detail} for c in claims], indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {args.json}")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
