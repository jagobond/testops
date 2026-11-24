# TESTOPS-67 build - no green zeros, no swallowed git failure, no mixed alphabets

Branch `factory/testops-67-honest-zero`, worktree `C:/Users/Chester/Projects/testops-t67`.
The live store and port 8791 were never touched. The corruption probe used a disposable git
repository under pytest's `tmp_path`. The TESTOPS-66 review was read from
`C:/Users/Chester/Projects/testops-t66/factory/reports/2026-11-24/TESTOPS-66-review.md` (it is
untracked there and absent from this worktree).

## What changed

`tests/support.py`

- **Policy-ignored paths are visible (AC1).** The walk now separates two buckets. `.git` and
  `.venv` are pruned as non-content. `__pycache__/`, `.pytest_cache/`, `build/`, `dist/` and
  `*.pyc` are walked, digested and compared in a second snapshot (`repository_ignored_snapshot`),
  but are **report-only**: they are never attributed and never fail. `AttributionReport` carries
  `ignored_changed`, `summary()` always prints "N paths under policy-ignored directories changed
  (report-only: not attributed)", including at zero, and lists the changed paths on a second line
  when N is non-zero. The policy and the boundary are in the module docstring.
- **An unreadable tree is unreadable, not staged (AC2).** `GitRepository.commit_blobs()` now
  returns `None` when `ls-tree` fails, distinct from a genuinely empty tree. `attribute_differences`
  turns that into the unreadable class before any staged/content rule runs, names the commit whose
  tree git could not read, and attributes no difference to a commit. `RepoState` is unchanged; the
  `ls-tree` failure is the signal, because `rev-parse` survives object corruption.
- **Digest alphabets never mix (AC3).** `repository_snapshot` returns a `Snapshot` that records its
  alphabet (`git-blob` or `sha256`). `_digest_paths` uses one alphabet for the whole snapshot: if
  `hash-object` fails, every path falls back to sha256 rather than mixing within the snapshot.
  `attribute_differences` compares the baseline/comparison alphabets (ordinary and ignored halves)
  before comparing digests; a mismatch returns the unreadable class with `not_comparable=True`, says
  the snapshots are not comparable, compares no digest, and attributes nothing. The guard's session
  report passes both alphabets through, so the latent mass false-failure is closed.
- **Partition.** `ignored_changed` is a class in the report. It is reported and counted against the
  total difference but is excluded from `failures`, matching the stated report-only policy.

`tests/conftest.py`, `tests/test_isolation.py` - docstrings state the report-only ignored policy,
the unreadable-tree verdict and the incomparable-alphabet verdict.

`tests/test_guard_attribution.py` - the existing five pinned cases and the partition test still
pass; three new pins:

1. a write to `build/x.txt` (and a `.pyc`) is counted, named and not a failure, with a zero in the
   ordinary classes;
2. a real corrupt object store makes `commit_blobs` return `None` and the report unreadable, not
   staged, with git named and no commit attribution - the exact TESTOPS-66 finding reproduced;
3. a blob baseline against a sha256 comparison fails as "not comparable", for both the ordinary
   and ignored halves, and never as a mass suite write.

The partition test was extended with the ignored-path class and reconciles the total across the
normal, ignored and git-unreadable states.

## Verification

Interpreter: `env -u PYTHONPATH -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1
C:/Users/Chester/Projects/testops/.venv/Scripts/python.exe -m pytest -q`.

- Targeted guard + isolation tests: **15 passed**.
- Full suite: **941 passed, 2 skipped** (162.86s).
- Contract suite (`tests/contracts`): **37 passed, 2 skipped** (13.08s).
- `tests/test_isolation.py -s` on the real worktree prints the summary with
  "0 paths under policy-ignored directories changed (report-only: not attributed)" and passes.
- `git status --short` shows only the four test files; no case-page golden changed.

## What remains out of scope

- A test write whose bytes exactly equal the excusing commit's blob is still indistinguishable from
  the commit; a write reverted to its baseline bytes is still invisible to a digest.
- `.git` and `.venv` are outside the guard's subject by design, and the docstring says so.
- Policy-ignored changes are reported, not failed. If a future ticket wants build-artefact writes to
  fail, the policy line changes in one place (`AttributionReport.failures` / the summary wording),
  but today a report-only count is the deliberate choice because pytest and the interpreter write
  those paths during a legitimate run.
