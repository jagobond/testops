---
id: TESTOPS-75
title: Two sentences and one regex - polish from the residuals review
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-71
---

# TESTOPS-75 - Small things a reader would trip over

## Why this exists

Three items from the TESTOPS-71 review, each too small for its own ticket and each a place where the product speaks
worse than it works.

1. **A user-facing guard message ends with a ticket id.** "…nothing was pruned or ignored by name (TESTOPS-71 AC1)" prints
   into a message a stranger reads in a failure. It cannot be resolved and it dates the message.
2. **`example-<word>` is a placeholder by construction.** The regex admits any value beginning `example` plus a separator,
   so a demo whose secret is `example-password` passes. The whole-value rule is right; the tail is the leak.
3. **The loud direction's cost is unstated.** A repository with a 10k-file `.venv` and git broken at walk time costs ~72s
   per snapshot cold (3s warm). The behaviour is right; the module docstring should say what it costs, so the next reader
   does not discover it in production.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | No user-facing message contains a ticket id or an AC number. Searchable: a test greps the message strings for `TESTOPS-` and fails. |
| AC2 | `example` is a placeholder only as a **whole value** (`example`, `EXAMPLE`, `<example>`), not as a prefix of an arbitrary value; `example-password` refuses because it carries a secret-shaped suffix. Pinned both ways, and the residual is stated if the tail is kept for a stated reason. |
| AC3 | The module docstring states the measured cost of the loud direction, with the file count and the timing basis, so the trade can be judged without re-measuring. |
| AC4 | No detection weakened: the placeholder and slot sets keep every other verdict; contract suite green; full suite green; no case-page golden changes. |
