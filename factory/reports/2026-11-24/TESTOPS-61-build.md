# TESTOPS-61 build — the rule reads every part, and a cut-off prefix is refused

Builder run, 2026-11-24. Worktree `C:/Users/<name>/Projects/testops-t61`, branch
`factory/testops-61-grammar-fix` (the main checkout and other worktrees were not touched). Interpreter
everywhere below:

    env -u PYTHONPATH -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe

Files changed: `testops/services.py`, `tests/test_config_credential_screen.py`, and this report. No
contract test was edited, no case-page golden changed, the live store was never written and port 8791
was never contacted.

## The two blind spots, and what replaced them

`_names_a_credential` used to read `parts[0]` and the last part. It now reads every part and states
one rule, in four clauses:

  * a bare credential word (`password`, `tokens`) names the thing itself — refused;
  * a name that **ends** in a credential word and carries a determiner or possessive **in any
    position** (`my-password`, `acme-their-password`, `an-api-token`) names a particular instance —
    refused;
  * **unless the parts are a statement**: a finite verb (`is`, `has`, `must`, …) makes them a clause,
    and a negator (`not`, `never`, `no`) makes them a denial. A determiner inside a statement belongs
    to the statement, not to the credential word — `this-is-not-a-password` and
    `xox-not-a-slack-token` are accepted;
  * every other compound is a compound **noun** naming a kind of thing — `session-token`,
    `vault-token`, `password-manager`, `token-bucket-limiter` — and is accepted.

Neither list is a vocabulary of technical terms. Determiners are a closed grammatical class; the
finite verbs are the closed class that makes a clause; negators are the closed class that makes a
denial. No entry names a credential, a product or a vendor.

The deciding rule for AC2 is therefore **clause or denial vs. noun phrase**, not length: an instance
label carries a determiner and states nothing, a sentence-name states something. That also keeps AC1
absolute — `acme-their-prod-db-password` (five parts, a possessive, no verb, no negator) is still
refused, where a "short enough" length rule would have let it through.

## AC1 — every part

    my-password                        refused   determiner + credential head
    acme-their-password                refused   possessive in a middle position
    acme-our-token                     refused   the same, a different possessive
    their-password                     refused   the same, two parts
    my-old-api-token                   refused   determiner, two modifiers, credential head
    acme-their-prod-db-password        refused   five parts, no statement: still a label
    session-token / vault-token /
    prod-db-password / password-list   accepted  no determiner anywhere: a kind name

Pinned by `test_a_determiner_or_possessive_in_any_position_names_an_instance` and by thirteen rows in
`BOUNDARY`.

## AC2 — a statement is not a label

    this-is-not-a-password            accepted  clause: `is` is a finite verb
    this-is-my-password               accepted  clause
    xox-not-a-slack-token             accepted  denial: `not` (and one of the twenty ordinary values)
    not-a-password                    accepted  denial
    acme-their-prod-db-password       refused   the boundary: same possessive, no verb, no negator

Pinned by `test_a_statement_about_a_credential_is_not_an_instance_label`, which asserts both the
accepted sentence-name and its refused boundary. The rule is stated in the `_names_a_credential`
docstring, the comment above `_DETERMINERS`/`_FINITE_VERBS`, and the module's rule list.

## AC3 — a truncation is no longer a silent accept

New `_truncated_token_in`: for the formats whose body is one unbroken run of fixed length (AKIA, ASIA,
ghp_/gho_/ghu_/ghs_, github_pat_), a body shorter than the format's floor is a cut-off paste and is
**refused**, with a reason that names the prefix and both lengths:

    github_pat_ + 22 base62    400  "it begins with 'github_pat_', a known credential prefix, but
                                     carries only 22 characters after it - too short for that format
                                     (82), so it reads as a cut-off paste rather than a name"
    ghp_ + 19 base62           400  the same, floor 36
    AKIA + 15 upper-case       400  the same, floor 16

The line between a fragment and a name is the **alphabet**, not the length: a body of lower-case
letters only is a word (`ghp_notes`, `github_pat_docs`, `ghp_only_a_document_path`) and stays a name;
a run carrying an upper-case letter or a digit cannot be an English word. `glpat-`, `xoxb-`, `xoxp-`
and `sk-` are excluded because their bodies can be word-shaped. The value is never echoed; the prefix
and two lengths are.

Pinned by `test_a_truncated_prefix_is_refused_and_the_reason_says_it_is_too_short`,
`test_a_truncated_fine_grained_prefix_is_refused_over_http` (400, reason on the page, no row stored)
and `test_every_prefix_carries_a_floor_and_a_ceiling`, whose two truncation accepts are now refusals.

## AC4 — grammatical justifications only

The HashiCorp sentence is gone from the code, the docstring and the boundary table. `vault-token` is
accepted by exactly the reason that holds for `session-token`: a compound noun whose head names a kind
of token and which carries no determiner. No source file under `testops/` or `tests/` mentions
HashiCorp any more (only stale `__pycache__` blobs do).

## AC5 — the boundary table

`BOUNDARY` goes from 61 to **74** values. New rows, each with its one-line reason: `this-is-not-a-password`,
`this-is-my-password`, `xox-not-a-slack-token`, `not-a-password`, `acme-their-password`,
`their-password`, `acme-our-token`, `my-old-api-token`, `acme-their-prod-db-password`,
`prod-db-password`, `github_pat_` + 22, `ghp_` + 19, `AKIA` + 15. `session-token` and `vault-token`
stay, with `vault-token`'s reason rewritten grammatically.

## AC6 — nothing weakened

Every probe below ran over HTTP through the service **name** field, against a **copy** of `data/` in
the scratch directory served by an in-process `ThreadingHTTPServer` on an ephemeral port
(`TESTOPS_DATA` pointed at the copy; the copy was deleted afterwards).

| Probe | Result |
|---|---|
| `the key is ghp_<36>` | 400, names `ghp_`, value not echoed |
| `the jwt is <3-segment JWT>` | 400, names the JWT shape |
| PEM block inside a sentence | 400, names the PEM block |
| `notes: name=token=abc123` | 400, names the `token=` pair |
| `aws id AKIA<16>` | 400, names `AKIA` |

All **twenty** ordinary values from the TESTOPS-59 review were re-posted and all returned **200**,
including `xox-not-a-slack-token`, `session-token`, `vault-token`, `my-password-manager` and the ten
prose samples. No refused value was stored: the copy holds 40 rows — the 28 posted values that were
accepted (20 ordinary + 8 boundary accepts) plus the 12 rows the store already had — and none of the
refused values appears.

Suites:

- `tests/test_config_credential_screen.py` + `tests/test_secret_guard.py`: **224 passed**.
- Contract suite alone: **37 passed, 2 skipped** (P9 and P14 are standing marker skips; the T59
  review's third skip was removed by TESTOPS-57, not by this ticket).
- Full suite: **852 passed, 2 skipped** in 163s. Collected tests at HEAD before this change: **837**;
  after: **854** (+17: 13 boundary rows, 3 named tests, 1 HTTP test). Baseline pass count at HEAD is
  therefore 835 passed / 2 skipped.

Live store:

    sha256 before: 6b0d38bd11e4b2ffe3ab8b677a9ebd20a3b61937db82f4eef1779d0e92e4c47c
    sha256 after:  6b0d38bd11e4b2ffe3ab8b677a9ebd20a3b61937db82f4eef1779d0e92e4c47c

## Residual risk, stated

A compound whose head is a credential word and which carries no determiner (`prod-db-password`) is
accepted as a type name. A name whose only determiner sits inside a statement (`not-my-password`,
`this-is-my-password`) is accepted, because it states something rather than labelling a credential.
A cut-off paste shorter than eight body characters, or one whose fragment happens to be all lower-case
letters, is indistinguishable from a word and is accepted. An unrecognised format is still not
detected at all, and the base64/entropy floors remain thresholds. What is no longer true is that a
possessive in the middle of a name is invisible, that a sentence-name is refused for its first word,
or that `github_pat_` + 22 characters gets a green tick with no hint.
