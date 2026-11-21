"""GitHub collector: a repo pinned at a commit.

Reads the tree once, then fetches only files that matter: features, step definitions, source and tests.
Everything lands in the blob store, so downstream work needs no network at all.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass

from .. import blobs
from ..config import Repo
from .http import FetchError, get_json

API = "https://api.github.com"
MAX_BYTES = 512 * 1024

# path suffix -> artefact kind
KINDS = (
    (".csproj", "build"),
    (".feature", "feature"),
    (".feature.cs", "feature"),      # Reqnroll code-behind, not wanted; filtered below
    (".py", "source"),
    (".cs", "stepdef"),
    (".ts", "stepdef"),
    (".js", "stepdef"),
)
IGNORE_PARTS = ("/bin/", "/obj/", "/.git/", "/node_modules/", "/.venv/", "__pycache__")


@dataclass
class Collected:
    commit: str
    files: dict[str, tuple[str, str]]   # path -> (blob_sha, kind)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
            "User-Agent": "testops-collector"}


def _kind(path: str, role: str) -> str | None:
    if path.endswith(".feature.cs"):
        return None
    for suffix, kind in KINDS:
        if path.endswith(suffix):
            if kind == "source" and role == "test":
                return "test"
            return kind
    return None


def head_commit(repo: Repo, token: str) -> str:
    d = get_json(f"{API}/repos/{repo.slug}/commits?per_page=1", _headers(token))
    if not d:
        raise FetchError(f"{repo.slug}: no commits")
    return d[0]["sha"]


def collect(repo: Repo, token: str, commit: str | None = None, role: str = "product") -> Collected:
    sha = commit or head_commit(repo, token)
    tree = get_json(f"{API}/repos/{repo.slug}/git/trees/{sha}?recursive=1", _headers(token))
    if tree.get("truncated"):
        raise FetchError(f"{repo.slug}: tree truncated at {sha}; too large for one pass")

    files: dict[str, tuple[str, str]] = {}
    for node in tree.get("tree", []):
        if node.get("type") != "blob":
            continue
        path = node["path"]
        if any(part in f"/{path}" for part in IGNORE_PARTS):
            continue
        if node.get("size", 0) > MAX_BYTES:
            continue
        kind = _kind(path, role)
        if not kind:
            continue
        files[path] = (node["sha"], kind)

    # The tree gives a *git* blob sha; the blob store keys on the *content* sha256. They are different
    # hashes, and confusing them makes every downstream lookup miss.
    for path, (git_sha, kindname) in list(files.items()):
        blob = get_json(f"{API}/repos/{repo.slug}/git/blobs/{git_sha}", _headers(token))
        content_sha = blobs.put(base64.b64decode(blob["content"]))
        files[path] = (content_sha, kindname)

    return Collected(commit=sha, files=files)
