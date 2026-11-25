#!/usr/bin/env python3
"""TESTOPS-103. Every file under ``tests/contracts/seed/blobs`` is named by its SHA-256.

The contract seed is content-addressed: ``seed.json`` names each blob by the digest of its bytes, so
a blob whose text is rewritten is a *different* blob and its filename has to move with it. A
leftover filename that does not equal the hash of its contents is a broken store - the harness would
copy the file to a path nothing references, and the page it renders would quote nothing - so this
check recomputes every digest and compares it with the name.

    python scripts/check_seed_hashes.py     # exit 0: every name is its content's hash

It also proves the other direction: every blob the seed *refers to* exists, so a repointed reference
cannot point at a file that was deleted in the rename.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "tests" / "contracts" / "seed"


def main() -> int:
    blob_dir = SEED / "blobs"
    files = sorted(path for path in blob_dir.iterdir() if path.is_file())
    problems: list[str] = []
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != path.name:
            problems.append(f"{path.name}: contents hash to {digest}")

    seed = json.loads((SEED / "seed.json").read_text(encoding="utf-8"))
    referenced = set(seed.get("blobs") or [])
    names = {path.name for path in files}
    for missing in sorted(referenced - names):
        problems.append(f"seed.json refers to {missing}, which is not in blobs/")

    # Every `blob_sha` on an artefact row has to be one of the files, or a page would quote nothing.
    for row in seed.get("artefact") or []:
        sha = row.get("blob_sha")
        if sha and sha not in names:
            problems.append(f"artefact {row.get('id')} refers to blob {sha}, which is not in blobs/")

    for problem in problems:
        print(problem)
    print(f"{len(files)} blobs, {len(referenced)} referenced by seed.json, "
          f"{len([p for p in problems if 'hash to' in p])} filename/hash mismatches, "
          f"{len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())