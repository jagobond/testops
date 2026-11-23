---
id: TESTOPS-61
title: The grammatical rule reads the first word and the last part, and nothing in between
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-59
---

# TESTOPS-61 - A rule that states itself, except at both ends

## Why this exists

TESTOPS-59 replaced a word list with a grammatical claim: refuse a name that ends in a credential word and opens with a
determiner or possessive; accept every other compound. The review judged the principle genuinely structural - the
determiner class is closed, and `session-token`, `vault-token`, `token-bucket-limiter` and `password-manager` all land on
the accepted side by one stated reason - and then found the two cases the claim cannot state:

- **`this-is-not-a-password` is refused.** It ends in a credential word and opens with `this`, so the rule fires - but it
  is a sentence-name naming no credential, the kind of joke repository name that exists in the wild.
- **`acme-their-password` is accepted.** The rule checks only the first part, so a possessive anywhere else is invisible -
  yet it names a particular credential exactly as plainly as `my-password`.

Neither is a leak: real pasted credentials are caught by the shape rules wherever they sit, so this boundary costs a
rewording, never a secret. But the ticket's claim is that the rule states itself, and these two are the cases where it
does not. Also: `github_pat_` + 22 characters is accepted as a truncation with no hint, which is a silent green tick on the
most recognisable prefix on the board; and `vault-token`'s comment appeals to HashiCorp's vocabulary - a fact about a
vendor, not a grammar - which is the same "list wearing grammar's coat" defect this line of tickets exists to remove.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The rule considers **every part**, not only the first: a possessive or determiner in any position makes the name an instance (`acme-their-password` refused). Pinned by test. |
| AC2 | A long name is not refused for opening with a determiner when its other parts show it is a sentence (`this-is-not-a-password` accepted). State the rule that decides this - e.g. the compound is short enough to be an instance label - and pin both it and its boundary. |
| AC3 | `github_pat_` truncation is **no longer a silent accept**: a value that begins with a real token prefix but is too short for that format is either refused with a reason that says so, or accepted with an explicit warning in the response naming the shape. Silently green is the failure. |
| AC4 | Every justification in code and docstring is **grammatical**. The vendor appeal for `vault-token` is removed; if the name is accepted, the reason given is the one that holds for `session-token` too. |
| AC5 | The boundary table grows with these six and their variants: `this-is-not-a-password`, `acme-their-password`, `prod-db-password`, `github_pat_` + 22, `session-token`, `vault-token` - each labelled accepted/refused with the one-line grammatical reason. |
| AC6 | No detection is weakened: the T59 leak probes are re-run (`the key is ghp_<36>`, prose JWT, PEM in a sentence, `notes: name=token=abc123`) and all still refused; the twenty ordinary values still accepted; contract suite green; full suite green. |
