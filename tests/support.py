"""Support code for the suite: a content snapshot of the repository, the write guard, and the store guard.

The write guard (``repository_snapshot`` + ``attribute_differences``) compares a digest of the whole
working tree before the first test with one taken after the last. TESTOPS-64: a difference is only
evidence of a test writing if *no commit made during the run* accounts for it, so the guard also
records ``HEAD`` and the index at baseline and reads the two commits' trees at comparison. TESTOPS-66:
an excuse needs agreement of content, not only of path: the working-tree digest must equal the blob
the excusing commit holds for the path. A staged-but-uncommitted change is its own failure, and a
git failure is reported as a git failure, never as a suite write.

What the guard can attribute:

* A path whose blob differs between the baseline commit and the commit at comparison **and whose
  working-tree digest equals the blob in the new commit's tree** was changed by that commit. That is
  reported, counted, and does not fail the suite.
* A path the new commit added whose working-tree digest equals the committed blob was added by that
  commit; a path the new commit removed was deleted by that commit (reported, not failed, per
  TESTOPS-64 AC3).
* A path whose index entry changed during the run and whose working-tree digest equals the new index
  blob, while the index differs from ``HEAD``, is a staged but uncommitted change. It fails and is
  named as staged: that is how a suite write would look if someone ran ``git add`` on it.
* Everything else fails: a modified, added or removed path with no commit whose tree agrees with it,
  including every untracked addition and every content mismatch between the working tree and the
  excusing commit. The message names the paths; for a mismatch it names the expected blob and the
  observed digest and says the working tree and the commit disagree.
* When git cannot be read, the difference is reported as unreadable: "the repository could not be
  read, so nothing could be attributed". It still fails - the invariant is unproven - but git is the
  suspect, not the suite. A repository whose *tree* cannot be read (``ls-tree`` fails, as with a
  corrupt object store) is unreadable too, never "staged": git is named and nothing is attributed to
  a commit.

Policy-ignored paths (TESTOPS-67 AC1):

* ``.git`` and ``.venv`` are not repository content and are never walked; a change there is outside
  the guard's subject.
* ``__pycache__/``, ``.pytest_cache/``, ``build/``, ``dist/`` and ``*.pyc`` are walked, digested and
  compared, but are **report-only**. The interpreter, pytest and builds write them into the checkout
  during a legitimate run, so they do not fail the suite. The summary always states how many such
  paths changed and that they are not attributed, and a non-zero count is listed by path. "0 files"
  in the ordinary classes therefore never means "0 files where the guard does not look": the ignored
  count is printed beside it.

Digest alphabets (TESTOPS-67 AC3): a snapshot uses exactly one alphabet - git's blob sha, or a raw
sha256 when git cannot be run. The two are never compared. If the baseline used blob digests and the
comparison cannot, the report is unreadable, says the two snapshots are not comparable, and
attributes nothing, rather than treating every tracked file as changed by the suite.

What it cannot attribute:

* *Which* person or process made a commit. A test write that produces exactly the same bytes as the
  commit's blob is indistinguishable from the commit's content and is excused; a write that produces
  different bytes is not.
* Content restored to its exact baseline bytes by the end of the run (a write reverted by the same
  run), which no digest can see - that is why the store guard below refuses the open instead.
* Anything at all when the checkout has no commit or the walk finds no files: with no commit to
  consult, every difference is unexplained, which is the loud direction. Git unavailability is the
  separate unreadable class above.
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

# Not repository content: never walked at all.
_EXCLUDED_DIRS = {".git", ".venv"}
# Written by Python's import machinery, pytest and build tooling, not by a test. Walked and counted
# under the report-only policy (TESTOPS-67 AC1), never failed and never attributed.
_POLICY_IGNORED_DIRS = {"__pycache__", ".pytest_cache", "build", "dist"}
_POLICY_IGNORED_SUFFIXES = (".pyc",)

# The two digest alphabets. A snapshot uses one of these throughout, and they are never compared.
BLOB_ALPHABET = "git-blob"
RAW_ALPHABET = "sha256"


class Snapshot(dict):
    """A path-to-(size, digest) map that also records which alphabet its digests use."""

    def __init__(self, files=(), *, alphabet: str = BLOB_ALPHABET):
        super().__init__(files)
        self.alphabet = alphabet


def _raw_digest(path: Path) -> tuple[int, str]:
    """A sha256 fallback used only when git cannot be run."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return path.stat().st_size, h.hexdigest()


def _blob_digests(root: Path, paths: list[str]) -> dict[str, str] | None:
    """Git's own blob sha for every working-tree path, with its filters applied.

    ``git hash-object --stdin-paths`` applies the repository's clean filters (including
    ``core.autocrlf``), so the digest is the blob the excusing commit would hold for the same bytes.
    A raw sha256 cannot be compared with a committed blob on a checkout with CRLF conversion. Returns
    ``None`` when git cannot be run, so the caller can fall back to a raw digest and the comparison
    can report the unreadable class.
    """
    if not paths:
        return {}
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "hash-object", "--stdin-paths"],
            input="\n".join(paths) + "\n", capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    lines = done.stdout.splitlines()
    if len(lines) != len(paths):
        return None
    return dict(zip(paths, lines))


def _walk(root: Path) -> tuple[list[str], list[str]]:
    """Normal paths and policy-ignored paths, relative to ``root``, both sorted and deterministic.

    ``.git`` and ``.venv`` are pruned entirely. A policy-ignored directory is walked (so its
    contents are visible and counted) and every path under it is classified as ignored; a ``.pyc``
    file is ignored wherever it sits.
    """
    normal: list[str] = []
    ignored: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _EXCLUDED_DIRS)
        directory = Path(dirpath).relative_to(root)
        under_ignored_dir = any(part in _POLICY_IGNORED_DIRS for part in directory.parts)
        for name in sorted(filenames):
            relative = (directory / name).as_posix() if directory.parts else name
            if under_ignored_dir or name.endswith(_POLICY_IGNORED_SUFFIXES):
                ignored.append(relative)
            else:
                normal.append(relative)
    return normal, ignored


def _digest_paths(root: Path, paths: list[str]) -> Snapshot:
    """Digest ``paths`` with one alphabet throughout; never mix blob shas and sha256 in one snapshot."""
    if not paths:
        return Snapshot({}, alphabet=BLOB_ALPHABET)
    blobs = _blob_digests(root, paths)
    use_blobs = blobs is not None and all(path in blobs for path in paths)
    out: dict[str, tuple[int, str]] = {}
    for relative in paths:
        path = root / relative
        size = path.stat().st_size
        if use_blobs:
            assert blobs is not None
            out[relative] = (size, blobs[relative])
        else:
            out[relative] = _raw_digest(path)
    return Snapshot(out, alphabet=BLOB_ALPHABET if use_blobs else RAW_ALPHABET)


def repository_snapshot(root: Path = ROOT) -> Snapshot:
    """Digest every file in the repo that the guard attributes: everything outside the ignored set.

    The digest is git's blob sha, so it can be compared directly with the blob an excusing commit
    holds for the path. A raw sha256 fallback is used only when git cannot be run, and the snapshot
    records which alphabet it used so a comparison can refuse an incomparable pair (TESTOPS-67 AC3).
    Comparing two snapshots detects an added, removed or modified file anywhere in the working tree,
    which is what AC10 needs: a test may only write under pytest's ``tmp_path``.
    """
    return _digest_paths(root, _walk(root)[0])


def repository_ignored_snapshot(root: Path = ROOT) -> Snapshot:
    """Digest the policy-ignored paths the summary reports but does not attribute (TESTOPS-67 AC1)."""
    return _digest_paths(root, _walk(root)[1])


def snapshot_difference(before: Mapping[str, tuple[int, str]],
                        after: Mapping[str, tuple[int, str]]) -> dict[str, list[str]]:
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
    """``HEAD``, the index and whether git could be read at one moment.

    ``index`` maps a path to the blob sha the index records for it (``git ls-files -s``). The
    comparison uses it to see a staged-but-uncommitted change: an index entry that changed during the
    run, whose blob equals the working-tree digest and differs from the blob in ``HEAD``'s tree.
    ``readable`` is false when git could not be run; then nothing is attributable and the comparison
    reports every difference as unreadable rather than accusing the suite. ``head`` is ``None`` when
    the checkout has no commit or git is unreadable.
    """

    head: str | None
    index: Mapping[str, str]
    readable: bool = True


@dataclass(frozen=True)
class AttributionReport:
    """A difference between two snapshots, split by what accounts for it.

    ``changed_by_commit`` / ``added_by_commit`` / ``deleted_by_commit`` are explained by a commit made
    during the run and do not fail. ``staged`` is a staged-but-uncommitted change. ``unexplained``
    (modified or removed with no commit whose tree agrees with the working tree) and ``untracked`` (an
    addition no commit contains) are failures. ``unreadable`` is every difference when git could not
    be read; it is a failure too, but the suspect is git. ``content_mismatches`` carries
    ``(path, expected_blob, observed_digest)`` for paths where a commit touched the path but the
    working tree disagrees with the blob it holds. ``ignored_changed`` is policy-ignored paths that
    changed; they are reported and counted but never attributed or failed. ``not_comparable`` means
    the two snapshots used different digest alphabets, so no digest was compared.
    """

    changed_by_commit: tuple[str, ...] = ()
    added_by_commit: tuple[str, ...] = ()
    deleted_by_commit: tuple[str, ...] = ()
    staged: tuple[str, ...] = ()
    unexplained: tuple[str, ...] = ()
    untracked: tuple[str, ...] = ()
    unreadable: tuple[str, ...] = ()
    ignored_changed: tuple[str, ...] = ()
    content_mismatches: tuple[tuple[str, str, str], ...] = ()
    unreadable_reason: str | None = None
    not_comparable: bool = False
    head_before: str | None = None
    head_after: str | None = None

    @property
    def failures(self) -> tuple[str, ...]:
        return tuple(sorted(self.unexplained + self.untracked + self.staged + self.unreadable))

    @property
    def explained_count(self) -> int:
        return len(self.changed_by_commit) + len(self.added_by_commit)

    def summary(self) -> list[str]:
        """Every class with its count, so a reader never has to infer the outcome from a pass.

        The policy-ignored count is always printed, including its "report-only: not attributed"
        wording, so a zero in the attributed classes cannot be read as "nothing changed anywhere we
        did not look" (TESTOPS-67 AC1).
        """
        lines = [
            "write guard: "
            f"{_count(self.explained_count, 'file')} changed by a commit during the run, "
            f"{_count(len(self.deleted_by_commit), 'file')} deleted by a commit during the run, "
            f"{_count(len(self.staged), 'staged but uncommitted change')}, "
            f"{_count(len(self.unexplained), 'file')} unexplained, "
            f"{_count(len(self.untracked), 'untracked addition')} no commit accounts for, "
            f"{_count(len(self.unreadable), 'unreadable file')}, "
            f"{_count(len(self.ignored_changed), 'path')} under policy-ignored directories changed "
            "(report-only: not attributed)"
        ]
        if self.ignored_changed:
            lines.append("write guard: policy-ignored paths changed and are not attributed: "
                         + ", ".join(self.ignored_changed))
        return lines

    def failure_message(self) -> str:
        assert self.failures
        lines: list[str] = []
        if self.unreadable:
            if self.not_comparable:
                lines.append(self.unreadable_reason or (
                    "the two snapshots are not comparable: the baseline and the comparison used "
                    "different digest alphabets, so no digest was compared"))
                lines.append("(no difference was attributed; the suite is not the suspect)")
            else:
                lines.append(self.unreadable_reason or (
                    "the repository could not be read, so nothing could be attributed: "
                    f"{', '.join(self.unreadable)}"))
                lines.append("(git is the suspect; the suite did not write this)")
        else:
            if self.staged:
                lines.append(
                    "a staged but uncommitted change appeared during the run: "
                    f"{', '.join(self.staged)}")
            blamed = tuple(sorted(set(self.unexplained + self.untracked)
                                  - {path for path, _, _ in self.content_mismatches}))
            if blamed:
                lines.append(
                    "the suite wrote outside tmp_path: no commit made during the run accounts for "
                    f"{', '.join(blamed)}")
            for path, expected, observed in self.content_mismatches:
                lines.append(
                    f"{path}: the working tree and the commit disagree "
                    f"(expected blob {expected}, observed digest {observed})")
        lines.append(f"(HEAD {_short(self.head_before)} -> {_short(self.head_after)})")
        lines.extend(self.summary())
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
                          commit_blobs: Callable[[str | None], Mapping[str, str] | None],
                          before_alphabet: str | None = None,
                          after_alphabet: str | None = None,
                          before_ignored_alphabet: str | None = None,
                          after_ignored_alphabet: str | None = None,
                          before_ignored: Mapping[str, tuple[int, str]] | None = None,
                          after_ignored: Mapping[str, tuple[int, str]] | None = None) -> AttributionReport:
    """Split the difference between two snapshots into exactly one class per path.

    ``commit_blobs(commit)`` returns the path-to-blob-sha map of that commit's tree, or ``None`` when
    git cannot read that tree (a corrupt object store, a failed ``ls-tree``). A commit excuses a path
    only when it touched the path **and** the working-tree digest equals the blob the new commit holds
    for it; a path the commit added or removed must be present or absent in the new tree as
    appropriate. A staged-but-uncommitted change is detected from the index when its entry changed
    during the run and the working tree matches the new index blob. When git is unreadable - or a
    tree it should be able to read is not - every difference is reported as unreadable and nothing is
    blamed on the suite. When ``HEAD`` did not move - or either side has no commit - nothing is
    explained, which is the loud direction. If the two snapshots used different digest alphabets,
    nothing is compared: the report is unreadable and says they are not comparable. ``before_ignored``
    and ``after_ignored`` are the policy-ignored snapshots; their differences are reported in
    ``ignored_changed`` and are never attributed or failed.
    """
    difference = snapshot_difference(dict(before), dict(after))
    all_paths = sorted(set(difference["added"]) | set(difference["removed"])
                       | set(difference["changed"]))
    for baseline_alpha, comparison_alpha in (
            (before_alphabet, after_alphabet),
            (before_ignored_alphabet, after_ignored_alphabet)):
        if (baseline_alpha is not None and comparison_alpha is not None
                and baseline_alpha != comparison_alpha):
            return AttributionReport(
                # Every path in the comparison is unreadable, not just the ones whose digests
                # happened to differ: no digest from a different alphabet was compared.
                unreadable=tuple(all_paths or sorted(set(before) | set(after))),
                not_comparable=True,
                unreadable_reason=(
                    "the two snapshots are not comparable: the baseline used "
                    f"{baseline_alpha} digests and the comparison used {comparison_alpha} digests, "
                    "so no digest was compared and nothing was attributed to a commit"),
                head_before=before_state.head,
                head_after=after_state.head)
    ignored_difference = snapshot_difference(dict(before_ignored or {}), dict(after_ignored or {}))
    ignored_changed = tuple(sorted(set(ignored_difference["added"])
                                   | set(ignored_difference["removed"])
                                   | set(ignored_difference["changed"])))
    if not before_state.readable or not after_state.readable:
        return AttributionReport(unreadable=tuple(all_paths),
                                 ignored_changed=ignored_changed,
                                 head_before=before_state.head,
                                 head_after=after_state.head)

    moved = bool(before_state.head and after_state.head and before_state.head != after_state.head)
    before_tree: Mapping[str, str] | None = commit_blobs(before_state.head) if moved else {}
    after_tree: Mapping[str, str] | None = commit_blobs(after_state.head) if moved else {}
    if before_tree is None or after_tree is None:
        failed = before_state.head if before_tree is None else after_state.head
        return AttributionReport(
            unreadable=tuple(all_paths),
            ignored_changed=ignored_changed,
            unreadable_reason=(
                "the repository could not be read: git could not read the tree of commit "
                f"{_short(failed)} (ls-tree failed), so the difference is unreadable, not staged, "
                "and no difference is attributed to a commit"),
            head_before=before_state.head,
            head_after=after_state.head)

    def digest_of(path: str) -> str:
        return after[path][1]

    def index_changed(path: str) -> bool:
        return before_state.index.get(path) != after_state.index.get(path)

    def staged(path: str) -> bool:
        """A staged-but-uncommitted change: the index moved and the working tree agrees with it."""
        if not index_changed(path):
            return False
        if path in difference["removed"]:
            # A staged deletion: the index no longer has the path, but HEAD's tree still does.
            return path in after_tree and path not in after_state.index
        blob = after_state.index.get(path)
        return blob is not None and blob == digest_of(path) and blob != after_tree.get(path)

    changed_by_commit: list[str] = []
    added_by_commit: list[str] = []
    deleted_by_commit: list[str] = []
    staged_paths: list[str] = []
    unexplained: list[str] = []
    untracked: list[str] = []
    mismatches: list[tuple[str, str, str]] = []

    for path in difference["added"]:
        if staged(path):
            staged_paths.append(path)
        elif moved and path in after_tree and digest_of(path) == after_tree[path]:
            added_by_commit.append(path)
        elif moved and path in after_tree:
            # The commit added the path, but its bytes are not the commit's bytes.
            unexplained.append(path)
            mismatches.append((path, after_tree[path], digest_of(path)))
        else:
            # AC3: an addition is attributed only when the new commit's tree actually contains it.
            untracked.append(path)

    for path in difference["removed"]:
        if staged(path):
            staged_paths.append(path)
        elif moved and path in before_tree and path not in after_tree:
            deleted_by_commit.append(path)
        else:
            # A commit that merely modified the path does not account for its disappearance.
            unexplained.append(path)

    for path in difference["changed"]:
        if staged(path):
            staged_paths.append(path)
        elif moved and path in after_tree and before_tree.get(path) != after_tree.get(path):
            if digest_of(path) == after_tree[path]:
                changed_by_commit.append(path)
            else:
                unexplained.append(path)
                mismatches.append((path, after_tree[path], digest_of(path)))
        else:
            unexplained.append(path)

    return AttributionReport(
        changed_by_commit=tuple(sorted(changed_by_commit)),
        added_by_commit=tuple(sorted(added_by_commit)),
        deleted_by_commit=tuple(sorted(deleted_by_commit)),
        staged=tuple(sorted(staged_paths)),
        unexplained=tuple(sorted(unexplained)),
        untracked=tuple(sorted(untracked)),
        ignored_changed=ignored_changed,
        content_mismatches=tuple(sorted(mismatches)),
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
        """``HEAD`` and the index now; ``readable=False`` when git cannot be run."""
        inside = self._git("rev-parse", "--is-inside-work-tree")
        if inside is None or inside.strip() != "true":
            return RepoState(head=None, index={}, readable=False)
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

    def commit_blobs(self, commit: str | None) -> Mapping[str, str] | None:
        """The path-to-blob-sha map of ``commit``'s tree, or ``None`` if git cannot read the tree.

        ``None`` is distinct from ``{}``: an empty tree is a real answer, a failed ``ls-tree``
        (corrupt object store, unreadable object) is not. Conflating them is how TESTOPS-66 reported
        a corrupt repository's committed addition as "staged but uncommitted" with git never named.
        """
        if not commit:
            return {}
        if commit in self._trees:
            return self._trees[commit]
        prefix = self._relative_prefix()
        stem = f"{prefix}/" if prefix else ""
        tree: dict[str, str] = {}
        listing = self._git("ls-tree", "-r", "-z", "--full-tree", commit)
        if listing is None:
            return None
        for record in listing.split("\0"):
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
    """What the write guard records before the first test: the digest, ``HEAD`` and the index.

    ``ignored_snapshot`` is the policy-ignored half (build outputs, caches, ``*.pyc``); it is
    compared and reported but never attributed or failed (TESTOPS-67 AC1).
    """

    snapshot: Mapping[str, tuple[int, str]]
    state: RepoState
    ignored_snapshot: Mapping[str, tuple[int, str]] | None = None
    root: Path = ROOT


def guard_baseline(root: Path = ROOT) -> GuardBaseline:
    return GuardBaseline(snapshot=repository_snapshot(root), state=GitRepository(root).state(),
                         ignored_snapshot=repository_ignored_snapshot(root), root=Path(root))


def guard_report(baseline: GuardBaseline) -> AttributionReport:
    """Compare ``baseline`` with the tree as it is now, attributing what a commit can account for."""
    repository = GitRepository(baseline.root)
    after_snapshot = repository_snapshot(baseline.root)
    after_ignored = repository_ignored_snapshot(baseline.root)
    return attribute_differences(
        baseline.snapshot, after_snapshot,
        before_state=baseline.state, after_state=repository.state(),
        commit_blobs=repository.commit_blobs,
        before_alphabet=getattr(baseline.snapshot, "alphabet", None),
        after_alphabet=getattr(after_snapshot, "alphabet", None),
        before_ignored_alphabet=getattr(baseline.ignored_snapshot, "alphabet", None),
        after_ignored_alphabet=getattr(after_ignored, "alphabet", None),
        before_ignored=baseline.ignored_snapshot,
        after_ignored=after_ignored)


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
