"""GitHub collector: a repo pinned at a commit.

Reads the tree once, then fetches only files that matter: features, step definitions, source and tests.
Everything lands in the blob store, so downstream work needs no network at all.

TESTOPS-41. What this module used to do with a file it did not recognise was ``continue``: the file
was invisible, and the run then reported a count of what it *had* fetched as if that were the
repository. Against a Java product that meant 142 ``.java`` files were dropped in silence and the page
said the product's code had been consulted.

So a file now leaves the tree in one of four ways, and every way but the first is recorded with the
reason and the kind:

  * **fetched** - its suffix is one of :data:`testops.config.FILE_KINDS`;
  * **ignored** - it sits under a pattern in :data:`testops.config.IGNORE_PATTERNS`, or its suffix is
    in :data:`testops.config.DROPPED_SUFFIXES` (generated code-behind);
  * **too large** - over the size cap;
  * **unsupported** - no declared kind reads it.

The kind list is configuration. A longer list is not the fix: the fix is that this module reports
what fell outside whatever list it was given, so a repository the tool cannot read says so instead of
returning a small number that looks like a reading.
"""
from __future__ import annotations

import base64
from collections import Counter
from dataclasses import dataclass, field

from .. import blobs, config
from ..config import Repo
from .http import FetchError, get_json

API = "https://api.github.com"

# The three reasons a file in the tree was not fetched. They are the reader's words, not a status
# code: a run page prints them beside the count.
UNSUPPORTED = "unsupported kind"
SIZE_CAP = "size cap"
IGNORE = "ignore pattern"


@dataclass(frozen=True)
class Skipped:
    """Every file this run refused, why, and what kind of file it was.

    ``kind`` is the suffix for an unsupported or oversized file and the pattern that matched for an
    ignored one, so "142 .java files were skipped" is a fact the record can print without re-reading
    the tree.
    """
    reason: str
    kind: str
    files: tuple[str, ...]

    @property
    def count(self) -> int:
        return len(self.files)

    def record(self) -> dict:
        return {"reason": self.reason, "kind": self.kind, "count": self.count,
                "files": list(self.files)}


@dataclass
class Collected:
    commit: str
    files: dict[str, tuple[str, str]]   # path -> (blob_sha, kind)
    role: str = ""
    skipped: tuple[Skipped, ...] = ()
    counts: dict[str, int] = field(default_factory=dict)   # capability -> files fetched for it

    def __post_init__(self) -> None:
        # A caller that hands in files and no counts gets them derived from the same configuration
        # the collector uses, so a test's in-memory repository is read the same way a fetched one is.
        if not self.counts:
            derived: Counter[str] = Counter()
            for path in self.files:
                rule = config.kind_for(path)
                derived[(rule.capability or config.arm_capability(self.role)) if rule
                        else config.arm_capability(self.role)] += 1
            self.counts = dict(derived)

    @property
    def unread(self) -> tuple[Skipped, ...]:
        """The skips that could have been read: unsupported and oversized files, not ignored ones."""
        return tuple(entry for entry in self.skipped if entry.reason != IGNORE)

    def record(self) -> dict:
        """The arm as written into a snapshot: what it read, per capability, and what it did not."""
        return {"commit": self.commit, "role": self.role, "files": len(self.files),
                "counts": dict(sorted(self.counts.items())),
                "skipped": [entry.record() for entry in self.skipped]}


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
            "User-Agent": "testops-collector"}


def _suffix(path: str) -> str:
    """The file's suffix, or ``(no suffix)`` - a kind a reader can recognise in a count."""
    name = path.rsplit("/", 1)[-1]
    if "." not in name.lstrip("."):
        return "(no suffix)"
    return "." + name.rsplit(".", 1)[1]


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

    arm = config.arm_capability(role)
    files: dict[str, tuple[str, str]] = {}
    counts: Counter[str] = Counter()
    refused: dict[tuple[str, str], list[str]] = {}

    def refuse(reason: str, kind: str, path: str) -> None:
        refused.setdefault((reason, kind), []).append(path)

    for node in tree.get("tree", []):
        if node.get("type") != "blob":
            continue
        path = node["path"]
        pattern = next((part for part in config.IGNORE_PATTERNS if part in f"/{path}"), "")
        if pattern:
            refuse(IGNORE, pattern, path)
            continue
        dropped = next((suffix for suffix in config.DROPPED_SUFFIXES if path.endswith(suffix)), "")
        if dropped:
            refuse(IGNORE, dropped, path)
            continue
        rule = config.kind_for(path)
        if rule is None:
            refuse(UNSUPPORTED, _suffix(path), path)
            continue
        if node.get("size", 0) > config.MAX_FILE_BYTES:
            refuse(SIZE_CAP, rule.suffix, path)
            continue
        kind = "test" if rule.kind == "source" and role == "test" else rule.kind
        files[path] = (node["sha"], kind)
        counts[rule.capability or arm] += 1

    # The tree gives a *git* blob sha; the blob store keys on the *content* sha256. They are different
    # hashes, and confusing them makes every downstream lookup miss.
    for path, (git_sha, kindname) in list(files.items()):
        blob = get_json(f"{API}/repos/{repo.slug}/git/blobs/{git_sha}", _headers(token))
        content_sha = blobs.put(base64.b64decode(blob["content"]))
        files[path] = (content_sha, kindname)

    skipped = tuple(Skipped(reason, kind, tuple(sorted(paths)))
                    for (reason, kind), paths in sorted(refused.items()))
    return Collected(commit=sha, files=files, role=role, skipped=skipped, counts=dict(counts))

