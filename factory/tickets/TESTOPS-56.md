---
id: TESTOPS-56
title: Tune the credential screen so it stops refusing ordinary words
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-51
---

# TESTOPS-56 - Tune the credential screen

## Why this exists

The screen works: nothing credential-shaped reaches the store, nothing is echoed, and a bypass hunt found no way in.
But three refusals it produces would be wrong for a real user, and one guarantee is weaker than it reads:

1. `token-bucket-limiter` is refused - a rate-limiting algorithm, not a secret. So are `my-password-manager` and
   `client_secret_manager` (borderline, plausible tool/module names).
2. `AKIA-reviews-team`, `xoxb-not-a-token` and `ghp_only_a_document_path` are refused **because of their first
   characters alone** - the prefix rule fires at any length, while `sk-` and `github_pat_` are already qualified by body
   shape. A real `ghp_` token has a 36-character base62 body; a document path does not.
3. The web layer **silently drops unknown settings keys** (303, value evaporates) instead of refusing them. Today that is
   safe only because a separate whitelist stands in front; a future refactor forwarding unknown keys would bypass the
   screen with no test failing.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Every credential **prefix** rule is qualified by body shape, as `sk-` and `github_pat_` already are, so a prefix alone is not a refusal. A real token of each format is still refused, pinned by a test built from the format's actual body (length and charset). |
| AC2 | The short-identifier rule is **scoped deliberately and written down**: decide (with evidence in the report) between accepting the class or narrowing it - e.g. only identifiers of two parts where one part is a credential word and the other is not a known technical suffix. Whatever is chosen, `token-bucket-limiter` is accepted and `my-password` is refused, both pinned by test. |
| AC3 | The false-positive boundary is a **table of at least 25 values** in the test file, each labelled accepted/refused with a one-line reason, so the rule can be argued with rather than guessed at. Include the reviewer's 14 and the original 11. |
| AC4 | Unknown settings keys are **refused with a reason**, not silently discarded - so the screen is consulted on every path and a refactor cannot quietly bypass it. A test posts an unseen key and asserts 400 plus a reason, and asserts nothing is stored. |
| AC5 | Detection is not weakened: every shape the previous ticket refused for the right reason is still refused (the AC5 bypass table from TESTOPS-51 is re-run and reported, attempt by attempt). |
| AC6 | Contract suite P23 still passes; full suite green; no case-page golden changes. |
