# TESTOPS-56 build — tune the credential screen without opening it

Builder run, 2026-11-24. Worktree `C:/Users/Chester/Projects/testops-t56`, branch
`factory/testops-56-screen-tuning`. Interpreter, everywhere below:

    env -u PYTHONPATH -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 C:/Users/Chester/Projects/testops/.venv/Scripts/python.exe

No product code was edited outside this ticket, no contract test was edited, no case-page golden
changed (`git status` shows exactly `testops/services.py`, `testops/web/app.py`,
`tests/test_config_credential_screen.py`). The live store and the live server on 8791 were never
used: every HTTP result below comes from a **copy** of `data/` served on port 8899.

## What changed

- `testops/services.py`
  - Rule 3 (short identifier naming a credential) is now `_names_a_credential(parts)`, a scoped
    decision written down in one function, instead of "≤3 parts containing a credential word".
  - Rule 4 (known credential prefix) is now `_PREFIXED_TOKENS`, a table of
    `(prefix, body-shape predicate)`. Every prefix is qualified; there is no longer any prefix that
    refuses on its first characters alone.
- `testops/web/app.py`
  - `_settings_from_form` refuses an unrecognised settings key (`ConfigError` → 400 with a reason)
    instead of building a dict from a whitelist and letting the rest evaporate. It also screens
    every submitted settings value, including one this service kind will not store, so no value
    reaches the store or disappears unexamined.
- `tests/test_config_credential_screen.py` — the AC3 boundary table (38 values), the AC1 real-body
  table, the AC2 pins, the AC4 unknown-key tests and an AC5 re-run of the TESTOPS-51 bypass table.
  113 tests in the file, all passing.

## AC1 — every prefix qualified by body shape

`_PREFIXED_TOKENS` (services.py) holds, in order:

| prefix | format | body shape required |
|---|---|---|
| `AKIA` / `ASIA` | AWS key ID | `AKIA`/`ASIA` + exactly 16 upper-case base32 characters |
| `ghp_` `gho_` `ghu_` `ghs_` | GitHub classic token | one unbroken base62 run (real body: 36) |
| `xoxb-` `xoxp-` | Slack token | digit-and-hyphen segments, 12+ chars, not a lowercase word chain |
| `glpat-` | GitLab PAT | one 14+ character run, not a lowercase word chain |
| `eyJ` | JWT | base64url segments after the header |
| `-----BEGIN ` | PEM | a `PRIVATE KEY` block |
| `github_pat_` | GitHub fine-grained | 22+ base62 (unchanged from TESTOPS-44) |
| `sk-` | API key | 32+ unbroken run, not a word chain (unchanged from TESTOPS-44) |

`test_a_real_token_of_each_format_is_still_refused` builds each probe from the format's own body and
asserts the body's **length and charset** before it asserts the refusal, so the table cannot decay
into "a prefix and some characters". `test_a_prefix_followed_by_ordinary_words_is_not_a_refusal`
pins `AKIA-reviews-team`, `xoxb-not-a-token`, `ghp_only_a_document_path`, `glpat-migration-plan`.

## AC2 — the short-identifier rule, scoped deliberately

**Decision: narrow the class.** A value (one unbroken identifier, no whitespace, no `/`) is refused
when, split into alphanumeric parts:

1. it is a bare credential word (`password`, `token`) — the name of the thing itself; or
2. its **last** part is the credential word and it has at most three parts (`my-password`,
   `an-api-token`, `client-secret`) — how a credential is named out loud; unless
3. it is two parts and the other part is a known technical suffix (`password-manager`,
   `token-bucket`) — the name of a tool.

Everything else is accepted, including any compound whose last part is not the credential word
(`token-bucket-limiter`, `my-password-manager`, `client_secret_manager`, `xoxb-not-a-token`).

Evidence for narrowing rather than accepting the class: (a) the reviewer found the refusal would be
*wrong* for a real user — `token-bucket-limiter` is a rate-limiting algorithm; (b) every wrong or
borderline refusal in the review came from this rule alone (review section "The screen as a shape");
(c) the two shapes that must stay refused (`my-password`, `an-api-token`) both end in the credential
word, and the three that must pass have the credential word in the middle or first — so "last part"
separates them without a word list; (d) the ticket's own escape hatch ("identifiers of two parts
where one part is a credential word and the other is not a known technical suffix") is subsumed by
this rule and only differs on `an-api-token`, which a narrower rule keeps refused. Rejected
alternative: accepting the whole class — it would let `my-password` through, which the ticket
forbids. Rejected alternative: a word list — it is what the ticket calls a rule that cannot be
argued with.

`token-bucket-limiter` accepted and `my-password` refused are pinned at the function
(`test_the_short_identifier_rule_accepts_a_tool_name_and_refuses_a_credential_name`), in the
boundary table, and over HTTP
(`test_the_scoped_rule_over_http_stores_the_tool_and_refuses_the_credential`: 200 then 400).

Residual risk, stated: a 4+ part name ending in a credential word is accepted, and a two-part name
ending in one whose other part is a technical suffix is accepted. Both are names a real user types;
neither is a pasted credential, and every pasted credential still meets rules 1, 2, 4 and 5.

## AC3 — the false-positive boundary is a table

`BOUNDARY` in `tests/test_config_credential_screen.py`: **38 values** (26 accepted, 12 refused), each `(value, verdict,
one-line reason)`, parametrised so a failure names the value and prints the argument. It contains the
original ticket's eleven, the reviewer's fourteen (including `Bearer token rotation work`, still
refused), and the boundary in both directions: `my-password`, `an-api-token`, `password`,
`client-secret` refused; `password-manager`, `token-bucket` accepted; and one real token of each
format refused. A second test asserts the table has ≥25 values and both verdicts.

## AC4 — unknown settings keys are refused, not discarded

`_settings_from_form` now rejects any posted key outside `_FORM_FIELDS | _SETTINGS_FIELDS` with a
`ConfigError` naming the key and saying it was refused rather than saved without it. The reason never
contains the value. `test_an_unknown_settings_key_is_refused_with_a_reason_and_nothing_is_stored`
posts `a_field_added_next_year=<ghp_ token>`, asserts 400, asserts the key name and "refused" are in
the page and the token is not, asserts no service row exists, and scans the SQLite file for both the
key bytes and the token bytes (0 of each). A second test proves the refusal is about the key, not the
value: an unseen key holding an ordinary value is refused too. Every *known* settings value is now
screened whether or not the kind stores it, so a stray value cannot evaporate unscreened either.

## AC5 — the TESTOPS-51 bypass table, re-run attempt by attempt

Copy of `data/` at `…/cache/scratch/t56-store`, served on 8899; results by hand over HTTP:

| Attempt | Before (TESTOPS-51) | Now | Verdict |
|---|---|---|---|
| Unknown settings key + `ghp_` token | 303, value silently dropped | **400** refused, naming the key | closed (was a silent drop) |
| Project named like a credential (`slug=password`) | 400 | 400 | unchanged |
| Leading whitespace before the token (repo) | 400 | 400 | unchanged |
| Trailing newline after the token (name) | 400 | 400 | unchanged |
| Double-URL-encoded `ghp_` (board) | 303, stores the literal `%67%68%70_…` string | 303/200, stores the same literal percent string | unchanged, not a credential in the store |
| Mixed case (`PaSsWoRd=hunter2`) | 400 | 400 | unchanged |
| Value split across fields (`name=token=`, `board=hunter2`) | 400 | 400 | unchanged |

After all attempts: `token bytes in the store file: 0`, `hunter2 bytes: 0`, no project named
`password`, `/config` contains no token. Also over the same copy: `ghp_only_a_document_path`,
`AKIA-reviews-team`, `xoxb-not-a-token` and `token-bucket-limiter` accepted (200); a real
`AKIA`+16 token refused (400); `my-password` refused (400).

## AC6 — suite and contracts

- `pytest -q` (whole suite, unedited): **787 passed, 2 failed, 3 skipped** in 176s. The two failures
  are `P07` and `P10` — the unchanged TESTOPS-7 promises recorded in the TESTOPS-51 review. Verified
  pre-existing: with this ticket's changes stashed, the same two fail and `P23` passes.
- `test_P23_password_in_free_text_field_is_refused` passes with the change and on the stashed
  baseline (3-test run: `FF.`).
- Case-page goldens untouched (no diff outside the three files named above).

## Live store untouched

    sha256 before: 6b0d38bd11e4b2ffe3ab8b677a9ebd20a3b61937db82f4eef1779d0e92e4c47c
    sha256 after:  6b0d38bd11e4b2ffe3ab8b677a9ebd20a3b61937db82f4eef1779d0e92e4c47c

The server used for AC5 ran on 8899 with `TESTOPS_DATA` pointed at the copy; port 8791 was not used.
