---
id: TESTOPS-60
title: The unplaced section is a wall at 200+, and its anchors are positional
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-57
---

# TESTOPS-60 - A wall nobody reads, and anchors that move

## Why this exists

TESTOPS-57 gave the unplaced claims a section, and the review proved the section is honest, counted and soft-toned. It
also rendered one with **220 entries**: ~93KB, a flat `<ul>`, no grouping, no cap, no disclosure, and every entry ending
in the same repeated reason clause. The store holds **351** unplaced claims in a single bad run. That is the same failure
mode the ticket rejected "a case per unplaced claim" for - a wall nobody reads - arriving by another route.

Two smaller things came with it: the branch that handles a run which declared **no binding patterns** exists in code and
is tested nowhere; and the anchors (`#unplaced-<n>`) are ordinals over claim-id order, stable only because claims are
never deleted. Both are cheap to make structural now and expensive later.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | **Group by reason.** Entries are grouped by what the tool could not do (no binding matches these words / no patterns declared / other), with a count per group, and the group sentence says what the group has in common. A reader must be able to see the shape of the failure before reading 200 rows. |
| AC2 | **A disclosure or a cap with an honest count.** Above a threshold (state it) the section shows the first N with a line saying how many are not shown and how to see them, OR a collapsed `<details>` block. It must never truncate silently. Tested at 0, 1, threshold-1, threshold, threshold+1 and 500 entries. |
| AC3 | **The repeated reason clause is not repeated.** The per-entry "Why it was not assessed: no binding matches these words." is stated once per group; each entry keeps only what is specific to it (the step's words, its nearest patterns). |
| AC4 | **Anchors become structural:** `#unplaced-<claim_id>` (or an equivalent identity that survives claim pruning and reordering), with a test that deletes an earlier claim from a copy and proves existing anchors still resolve to the same claim. The old ordinal form must either keep working or redirect. |
| AC5 | **The empty-binding-list branch is pinned** by a test: a run whose snapshot declares no patterns says so, and does not claim nearest patterns it does not have. |
| AC6 | Honesty unchanged: nothing implies a conclusion; banned phrases absent; the count sentence and the number of entries agree in every group and in total; contract suite green including P20; suite green; case-page goldens byte-identical. |
