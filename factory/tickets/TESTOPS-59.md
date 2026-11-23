---
id: TESTOPS-59
title: A real token pasted inside a sentence is stored, and the identifier boundary cannot explain itself
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-56
---

# TESTOPS-59 - The screen does not look inside prose, and its word boundary is a list in disguise

## Why this exists

The T56 review found three things, one of them a genuine leak that predates the screen's tuning:

1. **A token pasted inside a sentence is accepted.** `the key is ghp_<36 base62>`, `aws id AKIA<16>`, `the jwt is
   <three segments>` - all accepted and stored. Rule 3 exempts whitespace, rule 4 matches only `startswith`, and the blob
   rule requires no whitespace, so a sentence-wrapped paste meets no rule. Verified on the pre-T56 baseline, so this
   ticket did not create it - but the build's residual-risk note claimed "every pasted credential still meets rules 1, 2,
   4 and 5", and that sentence is false for this shape. A false safety argument is worse than a known gap.
2. **`session-token` is refused while `passwords-list` is accepted** (and `password-list` would be refused, because the
   word match is singular-only). A plausible repository or service name is refused by a boundary that is the intersection
   of a "credential word last" rule and a singular-only word list.
3. **`ghp_`/`gho_`/`ghu_`/`ghs_` is charset-only with no floor**, so `ghp_notes` is refused on its first characters -
   the exact class T56 was meant to remove - while `github_pat_`'s 22-character floor would accept a truncated paste.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | **Search, not prefix:** any value is scanned for a credential shape **at any position**, not only at position 0 - known prefixes with their real body shape, JWT/PEM blocks, and `name=value` pairs anywhere in the string. A token inside a sentence is refused. Pinned by tests built from real format bodies embedded in prose. |
| AC2 | Detection is not weakened for value in prose: at least ten prose samples with ordinary words (`the password reset flow is documented`, `Bearer token rotation work continues`, `documents/token-refresh.md`) must still be **accepted**. Scanning inside a string must not turn into refusing sentences. |
| AC3 | The identifier boundary is **explained by a rule that can state itself**, and `session-token` is accepted while `my-password` and `vault-token` are refused (or a stated alternative that the report defends with evidence). The singular/plural asymmetry is either fixed or pinned deliberately - `passwords-list` and `password-list` must be decided together, not by accident. |
| AC4 | Every prefix has a **floor and a ceiling** derived from the format's real body (classic GitHub bodies are far longer than `ghp_notes`; fine-grained tokens are not 22 characters). `ghp_notes` is accepted. A real token of each format is still refused, pinned by test. |
| AC5 | The AC3 boundary table grows past 40 values and includes the pairs this review found: `session-token`, `passwords-list`, `password-list`, `ghp_notes`, plus the prose samples from AC2. |
| AC6 | Contract suite green (it is green now - keep it green); full suite green; no case-page goldens change; the residual-risk note in the code and the ticket is rewritten to match what is true. |
