"""Support code for the suite: a content snapshot of the repository, the write guard, and the store guard.

The write guard (``repository_snapshot`` + ``attribute_differences``) compares a digest of the whole
working tree before the first test with one taken after the last. TESTOPS-64: a difference is only
evidence of a test writing if *no commit made during the run* accounts for it, so the guard also
records ``HEAD`` and the index at baseline and reads the two commits' trees at comparison.

What the guard can attribute:

* A path whose blob differs between the baseline commit and the commit at comparison was changed by
  a commit made during the run. That is reported, counted, and does not fail the suite.
* A path that appears in the new commit's tree but not the old one was added by that commit; a path
  that disappears from it was deleted by that commit (reported, not failed, per TESTOPS-64 AC3).
* Everything else fails: a modified, added or removed path with no commit whose tree differs for it,
  including every untracked addition. The message names the paths and says no commit accounts for
  them.

What it cannot attribute:

* *Which* person or process made a commit, or whether a commit and a test write both touched the same
  path in the same run: if a commit changes path P and a test also writes P, the write is attributed
  to the commit. The guard proves "the working tree now matches something a commit did", not "no
  test wrote here".
* Content restored to its exact baseline bytes by the end of the run (a write reverted by the same
  run), which no digest can see - that is why the store guard below refuses the open instead.
* Anything at all when git is unavailable, the checkout has no commit, or the walk finds no files:
  with no commit to consult, every difference is unexplained, which is the loud direction.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

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


# ---------------------------------------------------------------- attributing a change (TESTOPS-64)
#
# The digest above catches a change; on its own it cannot say who made it. A ticket file committed to
# ``main`` from another shell during the run is a change to the working tree that no test caused, and
# reporting it as "the suite wrote outside tmp_path" sends someone hunting a leak that does not exist.
# So the baseline also records HEAD and the index, and the comparison consults the two commits: a path
# whose blob differs between them was changed by a commit made during the run.


@dataclass(frozen=True)
class RepoState:
    """``HEAD`` and the index at one moment - what the guard needs to attribute a change.

    ``index`` maps a path to the blob sha the index records for it (``git ls-files -s``), so a path
    that was tracked at baseline can be told from one that never was. ``head`` is ``None`` when the
    checkout is not a repository, has no commit, or git cannot be run: then nothing is attributable
    and every difference stays unexplained.
    """

    head: str | None
    index: Mapping[str, str]


@dataclass(frozen=True)
class AttributionReport:
    """A difference between two snapshots, split by what accounts for it.

    ``changed_by_commit`` / ``added_by_commit`` / ``deleted_by_commit`` are explained by a commit made
    during the run and do not fail. ``unexplained`` (modified or removed with no commit accounting
    for it) and ``untracked`` (an addition no commit contains) are failures.
    """

    changed_by_commit: tuple[str, ...] = ()
    added_by_commit: tuple[str, ...] = ()
    deleted_by_commit: tuple[str, ...] = ()
    unexplained: tuple[str, ...] = ()
    untracked: tuple[str, ...] = ()
    head_before: str | None = None
    head_after: str | None = None

    @property
    def failures(self) -> tuple[str, ...]:
        return tuple(sorted(self.unexplained + self.untracked))

    @property
    def explained_count(self) -> int:
        return len(self.changed_by_commit) + len(self.added_by_commit)

    def summary(self) -> list[str]:
        """One line per class, with counts, so a reader never has to infer the outcome from a pass."""
        lines = [
            f"write guard: {_count(self.explained_count, 'file')} changed by a commit during the run, "
            f"{_count(len(self.unexplained), 'file')} unexplained"
        ]
        if self.deleted_by_commit:
            lines.append(
                f"write guard: {_count(len(self.deleted_by_commit), 'file')} deleted by a commit "
                "during the run")
        if self.untracked:
            lines.append(
                f"write guard: {_count(len(self.untracked), 'untracked addition')} no commit accounts "
                "for")
        return lines

    def failure_message(self) -> str:
        assert self.failures
        lines = [
            "the suite wrote outside tmp_path: no commit made during the run accounts for "
            f"{', '.join(self.failures)}",
            f"(HEAD {_short(self.head_before)} -> {_short(self.head_after)})",
            *self.summary(),
        ]
        return "\n".join(lines)


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _short(sha: str | None) -> str:
    return sha[:12] if sha else "(none)"


def attribute_differences(before: Mapping[str, tuple[int, str]],
                          after: Mapping[str, tuple[int, str]],
                          *,
                          before_state: RepoState,
                          after_state: RepoState,
                          commit_blobs: Callable[[str | None], Mapping[str, str]]) -> AttributionReport:
    """Split the difference between two snapshots into commit-explained and unexplained paths.

    ``commit_blobs(commit)`` returns the path-to-blob-sha map of that commit's tree, so the guard can
    ask whether a changed path's blob differs between the baseline commit and the commit at
    comparison. When ``HEAD`` did not move - or either side has no commit - nothing is explained and
    every difference is a failure, which is the loud direction.
    """
    difference = snapshot_difference(dict(before), dict(after))
    moved = bool(before_state.head and after_state.head and before_state.head != after_state.head)
    before_tree: Mapping[str, str] = commit_blobs(before_state.head) if moved else {}
    after_tree: Mapping[str, str] = commit_blobs(after_state.head) if moved else {}

    def committed(path: str) -> bool:
        """True when a commit made during the run changed this path's blob (or added/removed it)."""
        return moved and before_tree.get(path) != after_tree.get(path)

    added_by_commit, untracked, deleted_by_commit = [], [], []
    for path in difference["added"]:
        # AC3: an addition is attributed only when the new commit's tree actually contains it.
        # Nothing else excuses a new file, however much HEAD moved.
        (added_by_commit if committed(path) else untracked).append(path)
    for path in difference["removed"]:
        if committed(path):
            deleted_by_commit.append(path)
    unanswered_removed = [p for p in difference["removed"] if not committed(p)]
    changed_by_commit = [p for p in difference["changed"] if committed(p)]
    unexplained = [p for p in difference["changed"] if not committed(p)] + unanswered_removed

    return AttributionReport(
        changed_by_commit=tuple(changed_by_commit),
        added_by_commit=tuple(added_by_commit),
        deleted_by_commit=tuple(deleted_by_commit),
        unexplained=tuple(sorted(unexplained)),
        untracked=tuple(untracked),
        head_before=before_state.head,
        head_after=after_state.head,
    )


class GitRepository:
    """``HEAD``, the index and commit trees of one checkout, with commit trees read once each."""

    def __init__(self, root: Path = ROOT):
        self.root = Path(root)
        self._trees: dict[str, dict[str, str]] = {}
        self._prefix: str | None = None

    def _git(self, *args: str) -> str | None:
        try:
            done = subprocess.run(["git", "-C", str(self.root), *args],
                                  capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return None
        if done.returncode != 0:
            return None
        return done.stdout

    def _relative_prefix(self) -> str:
        """The path from the repository's top level to ``root`` (``""`` when they are the same)."""
        if self._prefix is None:
            top = self._git("rev-parse", "--show-toplevel")
            prefix = ""
            if top and top.strip():
                try:
                    prefix = self.root.resolve().relative_to(Path(top.strip()).resolve()).as_posix()
                except ValueError:
                    prefix = ""
            self._prefix = "" if prefix in ("", ".") else prefix
        return self._prefix

    def head(self) -> str | None:
        out = self._git("rev-parse", "--verify", "HEAD")
        return out.strip() if out and out.strip() else None

    def state(self) -> RepoState:
        """``HEAD`` and the index now; empty and ``None`` when git is not available."""
        index: dict[str, str] = {}
        listing = self._git("ls-files", "-s", "-z")
        prefix = self._relative_prefix()
        stem = f"{prefix}/" if prefix else ""
        for record in (listing or "").split("\0"):
            if not record:
                continue
            meta, _, path = record.partition("\t")
            parts = meta.split()
            if len(parts) < 2 or not path.startswith(stem):
                continue
            index[path[len(stem):]] = parts[1]
        return RepoState(head=self.head(), index=index)

    def commit_blobs(self, commit: str | None) -> Mapping[str, str]:
        """The path-to-blob-sha map of ``commit``'s tree, relative to ``root``."""
        if not commit:
            return {}
        if commit in self._trees:
            return self._trees[commit]
        prefix = self._relative_prefix()
        stem = f"{prefix}/" if prefix else ""
        tree: dict[str, str] = {}
        listing = self._git("ls-tree", "-r", "-z", "--full-tree", commit)
        for record in (listing or "").split("\0"):
            if not record:
                continue
            meta, _, path = record.partition("\t")
            parts = meta.split()
            if len(parts) < 3 or parts[1] != "blob" or not path.startswith(stem):
                continue
            tree[path[len(stem):]] = parts[2]
        self._trees[commit] = tree
        return tree


@dataclass(frozen=True)
class GuardBaseline:
    """What the write guard records before the first test: the digest, ``HEAD`` and the index."""

    snapshot: Mapping[str, tuple[int, str]]
    state: RepoState
    root: Path = ROOT


def guard_baseline(root: Path = ROOT) -> GuardBaseline:
    return GuardBaseline(snapshot=repository_snapshot(root), state=GitRepository(root).state(),
                         root=Path(root))


def guard_report(baseline: GuardBaseline) -> AttributionReport:
    """Compare ``baseline`` with the tree as it is now, attributing what a commit can account for."""
    repository = GitRepository(baseline.root)
    return attribute_differences(baseline.snapshot, repository_snapshot(baseline.root),
                                 before_state=baseline.state, after_state=repository.state(),
                                 commit_blobs=repository.commit_blobs)


# ---------------------------------------------------------------- the store guard
#
# TESTOPS-35. The suite has always been *meant* to write nothing but ``tmp_path``; before this
# guard, nothing enforced it at the connection. A review session's fixture reached the live store
# because a script could open ``data/testops.db`` and find a writable database. The repository
# digest below catches a file that changed by the end of the run, which is too late and too coarse:
# a test that opens the real store and only reads from it, or one whose write happens to be
# reverted, is invisible to a digest.
#
# So the guard refuses the open itself. The real store may be consulted read-only - two corpus
# tests do exactly that against a pinned snapshot - and a read-only open is declared by its URI
# (``file:...?mode=ro``), which SQLite enforces rather than this module. Anything else that
# resolves under a checkout's ``data/`` raises before SQLite sees the path.

class StoreWriteRefused(RuntimeError):
    """Raised when a test tries to open a product store outside a declared read-only mode."""


def protected_store_dirs() -> tuple[Path, ...]:
    """The ``data/`` directories a test must not open for writing.

    Two, because the suite is often run from a worktree: this checkout's (``TESTOPS_HOME``/data)
    and the main checkout's beside it. A worktree's own ``data/`` does not exist, which is exactly
    why protecting only it would have let this defect through.
    """
    from testops import config

    candidates = [ROOT / "data", ROOT.parent / "testops" / "data"]
    out: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in out:
            out.append(resolved)
    return tuple(out)


def real_store_path() -> Path:
    """The live store this checkout would write to, whether or not the file exists."""
    from testops import config

    return Path(config.settings().db_path).resolve()


def _is_protected(path: Path) -> bool:
    resolved = path.resolve()
    return any(resolved == root or root in resolved.parents for root in protected_store_dirs())


def _uri_target(database: str) -> tuple[Path, bool]:
    """The file a ``file:`` URI names, and whether the URI declares a read-only open."""
    text = database[len("file:"):] if database.startswith("file:") else database
    target, _, query = text.partition("?")
    read_only = any(part in ("mode=ro", "immutable=1") for part in query.split("&"))
    return Path(target), read_only


def guarded_connect(database, *args, **kwargs):
    """``sqlite3.connect`` that refuses a writable open of a product store.

    ``:memory:`` is allowed - it is not a file and cannot outlive the test. A ``file:`` URI with
    ``mode=ro`` or ``immutable=1`` is the declared read-only path, and SQLite enforces it.
    """
    if isinstance(database, bytes):
        database = database.decode("utf-8", "replace")
    if isinstance(database, (str, Path)):
        text = os.fspath(database)
        if text != ":memory:":
            target, read_only = _uri_target(text)
            if _is_protected(target) and not read_only:
                raise StoreWriteRefused(
                    f"a test tried to open the product store for writing: {target}\n"
                    "Copy it into pytest's tmp_path (shutil.copyfile) and write to the copy, or "
                    "open the original read-only with 'file:<path>?mode=ro', uri=True. A fixture "
                    "belongs in a copy; the live store is the Product Owner's evidence.")
    return _original_sqlite_connect(database, *args, **kwargs)


_original_sqlite_connect = sqlite3.connect


_original_db_connect = None


def guarded_db_connect(path=None):
    """``db.connect`` that refuses the real store before it creates its directory.

    ``db.connect`` calls ``p.parent.mkdir(parents=True, exist_ok=True)`` before SQLite is asked to
    open anything, so the sqlite-level guard alone would still let a test create ``data/``.
    """
    from testops import config

    target = Path(path) if path is not None else Path(config.settings().db_path)
    if _is_protected(target):
        raise StoreWriteRefused(
            f"a test tried to open the product store for writing: {target}\n"
            "Use db.connect(tmp_path / 'test.db') instead; the suite runs against a temporary "
            "store.")
    return _original_db_connect(path)  # type: ignore[misc]  # set by install_store_guard


def install_store_guard():
    """Patch both sqlite3 and ``testops.store.db`` for the session; returns the undo callable."""
    global _original_db_connect
    import pytest

    from testops.store import db as store_db

    if _original_db_connect is None:
        _original_db_connect = store_db.connect
    mp = pytest.MonkeyPatch()
    mp.setattr(sqlite3, "connect", guarded_connect)
    mp.setattr(store_db, "connect", guarded_db_connect)
    return mp
