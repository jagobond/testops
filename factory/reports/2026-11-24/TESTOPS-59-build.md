# TESTOPS-59 build — search inside the value, and a boundary that states itself

Builder run, 2026-11-24. Worktree `C:/Users/Chester/Projects/testops-t59`, branch
`factory/testops-59-prose-scan` (the main checkout and other worktrees were not touched). Host clock
at the time of writing was 2026-11-23 UTC; the report is filed under the ticket's date directory as
directed. Interpreter everywhere below:

    env -u PYTHONPATH -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 C:/Users/Chester/Projects/testops/.venv/Scripts/python.exe

Files changed: `testops/services.py`, `tests/test_config_credential_screen.py`,
`tests/test_secret_guard.py`, `tests/test_projects_services.py`, and this report plus the correction
to `factory/reports/2026-11-24/TESTOPS-56-build.md`. No case-page golden changed; no contract test was
edited. The live store was never written and port 8791 was never contacted.

## The three faults

**1. A real token inside a sentence was accepted (the leak).** Rule 2 now *searches* the value for a
PEM block and a three-segment JWT; rule 4 searches for every known prefix with its format's real
body, with word-boundary lookarounds so a match cannot sit inside a longer run (`xghp_...`,
`ghp_..._suffix`). Rule 1 already searched for `name=value` pairs. Nothing depends on position 0 or
on the absence of whitespace any more. The authorization-scheme rule was also made a shape: a scheme
plus exactly one unbroken value is a header; a sentence that merely opens with "Bearer" continues
past the first word and is prose, so AC2's `Bearer token rotation work continues` is now accepted
(it was refused by the old `^\s*bearer\s+\S+` rule).

**2. `session-token` was refused by a list in disguise.** `_TECHNICAL_SUFFIXES` is gone.
`_names_a_credential` now states itself: a bare credential word is refused; a name that *ends* in a
credential word and *opens with a determiner or possessive* (`my-password`, `an-api-token`,
`the-secret`) names a particular instance and is refused; every other compound is a compound noun
naming a kind of thing and is accepted. `_DETERMINERS` is a closed grammatical class, not a
vocabulary of technical terms. Singular and plural credential words are matched alike, so
`password-list` and `passwords-list` are decided together (both accepted: they name a collection).

**3. `ghp_` was charset-only; `github_pat_`'s floor accepted a truncation.** `_TOKEN_FORMATS` gives
every prefix a body shape **and** a floor and ceiling drawn from the format's real body.

## AC1 — search, not prefix

`_issued_token_in` runs each format's pattern with `finditer` over the whole value. Probes built from
real bodies and wrapped in prose (name field, over HTTP on a copy of `data/`):

| Probe (real body inside a sentence) | Result |
|---|---|
| `the key is ghp_<36>` | **400**, reason names `ghp_`, value not echoed |
| `aws id AKIA<16>` | **400**, names `AKIA` |
| `the jwt is <3-segment JWT>` | **400**, names the JWT shape |
| `key -----BEGIN RSA PRIVATE KEY-----` | **400** |
| `bot xoxb-<12>-<13>-<24> ok` | **400** |
| `pat glpat-<20> ok` | **400** |
| `key sk-<40> ok` | **400** |
| `pat github_pat_<22>_<59> ok` | **400** |
| trailing sentence period: `the key is ghp_<36>.` | **400** |

After the attempts a raw scan of the copied SQLite file found **0** occurrences of each token body.
Pinned by `test_a_real_token_pasted_inside_a_sentence_is_refused` and
`test_a_prose_wrapped_token_is_refused_over_http`.

Process note: the first probe run imported the venv's installed `testops` from the main checkout
(the script's own directory was `sys.path[0]`, not this worktree). Those numbers were discarded; the
probe was re-run with `PYTHONPATH` pinned to this worktree, and every figure above is from that run.

## AC2 — scanning does not refuse sentences

Ten samples are pinned in `BOUNDARY` and accepted at the function and over HTTP:
`the password reset flow is documented`, `Bearer token rotation work continues`,
`documents/token-refresh.md`, `the api key rotation schedule is quarterly`,
`secret scanning runs on every pull request`, `session tokens expire after thirty minutes`,
`our refresh token job runs nightly`, `read the private key exchange note first`,
`client secrets live in the environment, not here`, `vault-token-helper wrapper script`.

## AC3 — the boundary can explain itself

`session-token` and `vault-token` are **accepted**. That is the stated alternative the ticket allows,
and it is deliberate: they have the same grammatical shape (a compound noun whose head is the
credential word), and HashiCorp itself names the credential a Vault client presents a
"vault token". Refusing `vault-token` while accepting `session-token` could only be done by a word
list — the exact defect this ticket identifies. `client-secret` is accepted for the same reason and
because it names a *kind* of secret; the determiners are what mark an instance (`my-password`,
`an-api-token`, `the-secret` are all refused). The reviewer's judgement that `vault-token` was
"defensible" is superseded here, with the reason written into the function docstring and pinned in
the table.

Singular/plural: both `password-list` and `passwords-list` are accepted (a collection name), and bare
`passwords` / `my-passwords` are refused alongside the singular.

## AC4 — floor and ceiling for every prefix

| prefix | body | floor | ceiling |
|---|---|---|---|
| `AKIA` / `ASIA` | 16 upper-case base32 | 16 | 16 |
| `ghp_` `gho_` `ghu_` `ghs_` | unbroken base62 | 36 (today) | 40 (legacy) |
| `github_pat_` | 22 base62, `_`, 59 base62 | 82 | 82 |
| `glpat-` | base62 | 20 | 27 (routable) |
| `xoxb-` / `xoxp-` | 2–3 numeric segments + base62 tail | 44 | 74 |
| `sk-` | unbroken run, never a lowercase word chain | 32 | 128 |

`ghp_notes` and `github_pat_docs` are accepted (below their floors). A 22-character fine-grained
paste is accepted as a truncation — a truncated paste below a real body is indistinguishable from an
identifier, and that limit is stated in the residual note rather than denied. A real token at each
format's real body is still refused, pinned by `REAL_TOKENS` (which asserts each probe's length and
charset before asking for the refusal) and re-pinned in `test_secret_guard.py`.

## AC5 — the boundary table

`BOUNDARY` now holds **61 values** (was 38), including `session-token`, `passwords-list`,
`password-list`, `ghp_notes`, all ten AC2 prose samples, the singular/plural pair, the truncated
fine-grained paste, and the prose-wrapped real tokens. The guard test asserts `> 40` and both
verdicts.

## AC6 — suites, goldens, and the residual note

- `pytest -q` (whole suite): **829 passed, 3 skipped** in 139s. Baseline before the change was
  **800 passed, 3 skipped** (the difference is the tests added here).
- Contract suite alone: **36 passed, 3 skipped**.
- `git status --short` touches only the four test/product files and `factory/`; no golden changed.
- Residual-risk note rewritten in two places: the `_looks_like_secret` docstring (it now states what
  is *not* caught) and the TESTOPS-56 build report (the false sentence "every pasted credential still
  meets rules 1, 2, 4 and 5" is replaced with a correction that names why it was false).

Two existing tests were updated because they encoded the behaviour TESTOPS-59 calls wrong:
`test_secret_guard.py`'s "refused at any length" table (now real bodies, plus an explicit pin that
`ghp_aaaaaaaaa` is a name) and `test_projects_services.py`'s `shhh-secret` probe (now `the-secret`,
which the determiner rule refuses). Both changes are commented in place.

## Live store untouched

    sha256 before: 6b0d38bd11e4b2ffe3ab8b677a9ebd20a3b61937db82f4eef1779d0e92e4c47c
    sha256 after:  6b0d38bd11e4b2ffe3ab8b677a9ebd20a3b61937db82f4eef1779d0e92e4c47c

Every HTTP probe ran against a copy of `data/` in the scratch directory, served by an in-process
`ThreadingHTTPServer` on an ephemeral port. The copy was deleted afterwards. The read-only check of
the 12 existing service rows found no value the new screen would now refuse.

## Residual risk, stated

An unrecognised credential format is not detected at all; a paste truncated below a covered format's
real body is accepted; a compound label whose head is a credential word but which opens with no
determiner (`prod-db-password`) is accepted as a type name; the base64 and entropy floors remain
thresholds, not proofs. What is no longer true — and was true before this ticket — is that a
sentence-wrapped real token of a covered format passes the screen.
