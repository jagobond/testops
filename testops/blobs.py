"""Content-addressed blob store: sha256 -> bytes.

Files are fetched once and parsed from disk afterwards, so a re-run over the same snapshot does no network
I/O and costs nothing.
TESTOPS-38 AC6: the root is the deployment's single ``Settings`` object, read at call time, so the
store and the blobs move together when ``TESTOPS_DATA`` points at a mounted volume. ``BLOB_DIR``
remains as an explicit override for callers (the suite) that need a throwaway directory.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from . import config

# ``None`` means "ask the settings"; a path here is an explicit override.
BLOB_DIR: Path | None = None


def blob_dir() -> Path:
    return Path(BLOB_DIR) if BLOB_DIR is not None else config.settings().blob_dir


def _path(sha: str) -> Path:
    return blob_dir() / sha[:2] / sha[2:]


def put(data: bytes) -> str:
    sha = hashlib.sha256(data).hexdigest()
    p = _path(sha)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return sha


def get(sha: str) -> bytes:
    p = _path(sha)
    if not p.exists():
        raise FileNotFoundError(f"blob {sha} missing")
    return p.read_bytes()


def text(sha: str) -> str:
    return get(sha).decode("utf-8-sig", errors="replace")
