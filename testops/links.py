"""Turn stored artefact URIs into things a person can click.

The whole trust story rests on this: a claim nobody can check is a claim nobody should act on. If the URI shape
changes, this is the only place that has to change.
"""
from __future__ import annotations

import re

GITHUB = re.compile(r"^github:(?P<owner>[^/]+)/(?P<repo>[^@]+)@(?P<sha>[0-9a-f]+):(?P<path>.+)$", re.I)


def permalink(uri: str, line: int | None = None) -> str | None:
    """A URL a human can open, or None if the artefact is not on a web host we know."""
    m = GITHUB.match(uri or "")
    if not m:
        return None
    return blob_permalink(f"{m['owner']}/{m['repo']}", m["sha"], m["path"], line)


def blob_permalink(repo: str | None, commit: str | None, path: str | None,
                   line: int | None = None) -> str | None:
    """A claim's assertion as a GitHub URL at the commit it was read at.

    The commit is passed in, never inferred from the repository's current state: a link to HEAD
    would show the reader whatever the file says today, which is not what the claim was made from.
    A missing commit or path is a claim without coordinates, and returns None rather than a URL
    that would point at a branch.
    """
    if not (repo and commit and path):
        return None
    url = f"https://github.com/{repo}/blob/{commit}/{path}"
    return f"{url}#L{line}" if line else url


def short_location(uri: str, line: int | None = None) -> str:
    """What to print next to a finding: repo@sha:path:line, abbreviated but unambiguous."""
    m = GITHUB.match(uri or "")
    if not m:
        return uri or ""
    where = f"{m['repo']}@{m['sha'][:8]}:{m['path']}"
    return f"{where}:{line}" if line else where
