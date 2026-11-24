---
id: TESTOPS-69
title: The small residuals the credential and guard threads left behind
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-67, TESTOPS-68
---

# TESTOPS-69 - Six known small seams, collected

## Why this exists

Both threads (the credential screen, the isolation guard) ended each review with small, stated residuals that are too
small to be worth a ticket apiece and too real to lose. They are collected here so the board stays clear and none of them
is quietly forgotten. None is a leak; each is a place where a message or a rule is slightly less true than it reads.

1. **A tab never licenses the line boundary** (T68 review): `x\tkey = hunter2` is accepted because the lookbehind excludes
   horizontal whitespace including tab, so a tab-separated config line reads as prose.
2. **The inline-password floor is a one-line shape** (T68 review): percent-encoded userinfo, whitespace-split URLs, and
   `postgres://app@db/qa?password=x` are not caught.
3. **"0 unreadable files" can print when git was never readable** (T67 review): the unreadable count is difference-driven,
   so a run with no differences and no readable git passes with a zero summary. Add "git readable: yes/no" to the summary.
4. **Committed build artefacts ride the ignored channel** (T67 review): a mid-run commit adding `build/gen.txt` is
   report-only. Decide whether committed artefacts should fail while cache churn stays report-only.
5. **Pruning is by name at any depth** (T67 review): a repository directory named `.venv`, or any `*.pyc`, is invisible or
   report-only even at the root. Add a tracked-path guard so a commit-tracked path is never pruned.
6. **The boundary table's prose sentences are position, not intent** (T68 review): a wrapped sentence whose next line
   begins `Key:` is read as configuration. Keep it stated in the comment rather than silently absorbed.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Each of the six is either fixed or explicitly documented as a stated limit, and the ticket's report says which for each, with the reason. |
| AC2 | The tab decision is made on purpose: a tab before a bare key pair is either a line boundary (refused) or documented as prose, and pinned. |
| AC3 | The guard's summary carries a `git readable: yes/no` field in every run, printed on pass as well as failure. |
| AC4 | A commit-tracked path is never pruned by name: pinned by a test with a tracked file named `.pyc` or under `.venv`. |
| AC5 | No detection weakened; contract suite green; full suite green; no case-page golden changes. |
