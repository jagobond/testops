---
id: TESTOPS-49
title: The packaging coverage test passes when there is nothing to check
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-48
---

# TESTOPS-49 — A test that cannot tell "nothing to check" from "all checked"

## Finding (TESTOPS-48 review, concern 1)

TESTOPS-48 decides package-data coverage from the built wheel's namelist. The reviewer monkeypatched
`_data_files_on_disk` to return `[]`, and **the test passed**: zero files enumerated, zero assertions made. The same
happens if `PACKAGE` points at a directory that does not exist.

A test that reports success when its subject has vanished is protection-shaped. This is the last of the same family
found today: a claimed guard that cannot fail.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The enumeration must assert it found a non-empty set, naming the directory it walked, before any verdict is drawn. Empty enumeration fails with a message that says the walk found nothing, not that packaging is fine. |
| AC2 | Prove it: monkeypatch the enumeration to `[]` (or point `PACKAGE` at a missing directory) and watch the test fail. Paste the failure. Then restore and confirm green. |
| AC3 | A **minimum count** is pinned alongside non-emptiness - at least the files known today (`judgement/prompts/level_fitness.md`, `store/schema.sql`). Adding a third non-Python file must not require editing the number, but deleting one must fail. |
| AC4 | The same rule is applied wherever else the suite enumerates a tree to prove something about it, if such a place exists; list them or say there are none. |
| AC5 | Suite green, counts unchanged, no product code touched. |

## Notes

- `assert files` is the one-line version of AC1; AC3 is what makes it stay true.
- Do not weaken the wheel-namelist verdict while adding this guard.
