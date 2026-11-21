"""Content-addressed blob store: sha256 -> bytes.

Files are fetched once and parsed from disk afterwards, so a re-run over the same snapshot does no network
I/O and costs nothing.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .config import BLOB_DIR


def _path(sha: str) -> Path:
    return BLOB_DIR / sha[:2] / sha[2:]


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
