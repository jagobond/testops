"""Support code for the suite: a content snapshot of the repository."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Written by Python's import machinery and by pytest itself, not by a test.
_IGNORED_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "build", "dist"}
_IGNORED_SUFFIXES = (".pyc",)


def _digest(path: Path) -> tuple[int, str]:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return path.stat().st_size, h.hexdigest()


def repository_snapshot(root: Path = ROOT) -> dict[str, tuple[int, str]]:
    """Digest every tracked-by-content file in the repo, ignoring interpreter caches.

    Comparing two snapshots detects an added, removed or modified file anywhere in the working tree,
    which is what AC10 needs: a test may only write under pytest's ``tmp_path``.
    """
    out: dict[str, tuple[int, str]] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _IGNORED_DIRS)
        for name in sorted(filenames):
            if name.endswith(_IGNORED_SUFFIXES):
                continue
            path = Path(dirpath) / name
            out[path.relative_to(root).as_posix()] = _digest(path)
    return out


def snapshot_difference(before: dict[str, tuple[int, str]],
                        after: dict[str, tuple[int, str]]) -> dict[str, list[str]]:
    return {
        "added": sorted(set(after) - set(before)),
        "removed": sorted(set(before) - set(after)),
        "changed": sorted(k for k in set(before) & set(after) if before[k] != after[k]),
    }