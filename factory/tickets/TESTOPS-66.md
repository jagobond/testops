---
id: TESTOPS-66
title: A committed write launders, the index is dead, and git failure blames the suite
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-64
---

# TESTOPS-66 - Three ways the guard still lies

## Why this exists

TESTOPS-64 made the isolation guard attribute a difference to a commit made during the run, and it does that correctly.
Its review then found three ways the guard still tells a reader something untrue.

1. **A write can be laundered by a commit.** The rule excuses any changed path whose blob differs between the two commits.
   So a suite that writes `data/` and a developer who commits *any* change to that path in the same window produce a green
   run - and the working-tree bytes need not match the commit's blob at all.
2. **The index is recorded and never read.** An unused field in a guard is a claim that something is checked when it is
   not; staged-but-uncommitted writes are exactly the case the HEAD-diff rule cannot see.
3. **A git failure is reported as the suite writing.** The message asserts "the suite wrote outside tmp_path" even when the
   truth is "git could not be read and nothing was attributable", which sends a reader to investigate the suite instead of
   the tool.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | An excuse requires agreement of **content**, not only of path: the working-tree file's digest must equal the blob the excusing commit holds for that path. On mismatch the guard **fails**, naming the path, the expected blob and the observed digest, and saying the working tree and the commit disagree. Pinned by a test that changes a committed file's bytes after the commit. |
| AC2 | The index either becomes load-bearing or is removed. Preferred: detect a **staged but uncommitted** change to a path the suite could write and fail naming it, because that state is invisible to the HEAD rule and is how a suite's write would look if someone staged it. Otherwise delete the field and the docstring sentence that claims it is checked. |
| AC3 | Git unavailability is reported as its own class - "the repository could not be read, so nothing could be attributed" - and does not claim the suite wrote. It still fails, because the invariant is unproven, but the message names the tool as the suspect. |
| AC4 | The three classes are printed with counts, and the total always reconciles: every difference appears in exactly one of explained-by-commit, staged, unexplained, or unreadable. A test proves the partition (a difference cannot be counted twice or dropped). |
| AC5 | The original false alarm still passes (a mid-run commit to a tracked file), a plain write still fails, an untracked addition still fails, and each of the three new cases fails for its own stated reason - five pinned tests plus the partition test. |
| AC6 | Full suite green; contract suite green; no case-page golden changes; module docstring states what the guard can and cannot attribute. |
