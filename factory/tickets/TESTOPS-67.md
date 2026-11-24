---
id: TESTOPS-67
title: The guard's ignore list is a green channel, and corruption blames the suite
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-66
---

# TESTOPS-67 - Three more ways the guard says "0 files" and means nothing

## Why this exists

TESTOPS-66 taught the guard to excuse a difference only when the bytes agree with the excusing commit, gave staged
changes their own class, and gave an unreadable repository its own message. Its review then found three boundaries where
the guard still reports a confident zero that is not true.

1. **The ignore list is a silent green channel.** `build/`, `dist/`, `__pycache__/`, `.pytest_cache/` and `*.pyc` are
   skipped by the snapshot walk, so a test writing `build/x.txt` goes green and prints "0 files" - the same lie as before,
   in a quieter voice, and the docstring never mentions it.
2. **A corrupt repository is misattributed as staged.** `rev-parse --is-inside-work-tree` survives object corruption while
   `ls-tree` failure is swallowed into an empty tree, so a committed addition is reported as "staged but uncommitted" and
   git is never named. Right verdict, wrong suspect - and the reason is the product here.
3. **Digest alphabets can mix.** If the baseline used blob-sha and the comparison falls back to sha256, every tracked file
   appears changed and is blamed on the suite: a mass false failure, the exact outcome that trains people to ignore a guard.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Policy-ignored paths are **visible in the summary even when nothing fails**: the report states how many paths under ignored directories changed and that they are not attributed, so "0 files" can never again mean "0 files outside the places we do not look". Writes inside an ignored directory are reported, not excused silently; whether they fail is stated explicitly as policy, and the choice is documented in the module docstring. |
| AC2 | A repository that cannot be **read** is unreadable, not staged: `ls-tree` (or the tree lookup) failing makes the state unreadable with git named, and no difference is attributed to a commit. Pinned by a test that corrupts the object store, or simulates the failure if corruption is impractical. |
| AC3 | The two digest alphabets never mix within one comparison: if the baseline snapshot used blob digests and the comparison cannot, the guard fails as unreadable with a message saying the two snapshots are not comparable - it never compares a blob sha to a sha256. Pinned by test. |
| AC4 | The five existing pinned cases keep passing, plus the three new ones, plus the partition test extended to include the ignored-path class. |
| AC5 | Full suite green; contract suite green; no case-page golden changes. |
