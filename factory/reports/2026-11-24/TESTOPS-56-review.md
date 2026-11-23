# TESTOPS-56 review — tuning the credential screen: both directions judged

Reviewer run, 2026-11-24. Worktree `C:/Users/Chester/Projects/testops-t56`, branch
`factory/testops-56-screen-tuning`, HEAD `c800b73`. Interpreter everywhere:
`env -u PYTHONPATH -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1
C:/Users/Chester/Projects/testops/.venv/Scripts/python.exe`.

Every probe below was run by me, not taken from the build report. Detection probes called
`_looks_like_secret` directly; the HTTP battery ran against a fresh copy of `data/` served by an
in-process `ThreadingHTTPServer` on an ephemeral port with `TESTOPS_DATA` pointed at the copy —
the live store and port 8791 were never touched, and the live `testops.db` hashed `6b0d38bd…c47c`
before and after the whole session (identical to the build's record).

## Verdict

**PASS — mergeable, with findings.** The false-negative direction — the one this ticket creates —
is clean at the level the ticket addresses: every real token of its own format, at its real body
length and charset, is still refused (25+ real-shape probes, all refused; details below). The
scoped identifier rule fixes the wrong refusal from TESTOPS-51 and introduces no paste-shaped gap.
AC1–AC6 hold as built and independently verified. The findings are (1) a real leak shape that
predates this ticket and which the build's residual-risk note overstates, (2) three refusals among
my fifteen identifiers, one of them wrong, and (3) a `ghp_` qualification weaker than the build's
own table implies. None blocks merge; all three belong in tickets.

## False negatives (the real risk)

I attacked `_PREFIXED_TOKENS` (services.py:139) with real format shapes, asserting each probe's
length and charset before judging it, per the build's own discipline. Every probe at a real
format's real body was **refused**:

| Probe (body at the format's real shape) | Result |
|---|---|
| `AKIA` + 16 uppercase base32 (20-char key ID) | refused (prefix rule) |
| `ASIA` + 16 uppercase | refused |
| `ghp_` + 36 base62 (current classic) | refused |
| `ghp_` + 40 base62 (legacy) | refused |
| `gho_` / `ghs_` / `ghu_` + 36 base62 | refused (all three) |
| `ghp_` + 36 lowercase letters | refused |
| `github_pat_` + 22 base62 | refused |
| `github_pat_` + 22 + `_` + 59 (the full 82-char body) | refused |
| `glpat-` + 20 | refused |
| `xoxb-`/`xoxp-` + `1234567890-1234567890123-` + 24 base62 | refused (both) |
| short JWT (`eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig`) | refused |
| typical 3-segment JWT | refused |
| PEM RSA / EC / PKCS8 (`BEGIN PRIVATE KEY`) / OpenSSH blocks | refused (all four) |
| `sk-` + 48 | refused |
| real token + trailing sentence period (`ghp_…X.`) | refused (entropy rule) |

On length ambiguity: where a format's real body length is uncertain or has changed over time
(GitHub classic: 36 today, 40 historically; Slack segment lengths; `sk-` variants), the checks
accept a **range wide enough to hold every real shape** — `_GITHUB_CLASSIC` has no length ceiling
and no floor, `_SLACK_TOKEN`/`_GITLAB_PAT` use 12+/14+ floors. I found no real token of any format
that its own predicate rejects. That is the direction done right.

Two probes were **accepted**, and I judge both honestly:

1. `AKIA` + 16 lowercase alphanumerics — accepted. Not a false negative: AWS key IDs are
   uppercase-only, so this is not a real token of its own format. It shows the `AKIA` predicate is
   a strict fullmatch (also rejects >16-char bodies), which is correct but means the format's
   charset is being asserted by the ticket, not discovered — if AWS ever issued a differently
   cased ID the test would need updating, and the pinned test would not notice.
2. **A real token pasted inside prose is accepted.** `the key is ghp_<36 base62>`, `aws id
   AKIA<16>`, `the jwt is <3-segment JWT>` — all accepted, all real shapes. The mechanism: rule 3
   exempts whitespace, rule 4 matches only `startswith`, and the entropy/blob rule exempts
   whitespace, so a token that is neither at position 0 nor in a `name=value` pair meets none of
   the five rules. I verified on the pre-ticket baseline (`91583de`, checked out to a throwaway
   worktree, since removed) that this is **pre-existing, not created by this ticket** — the same
   three probes leak there. But the build's residual-risk sentence — "every pasted credential
   still meets rules 1, 2, 4 and 5" — is overstated: a credential pasted in a sentence meets none
   of them. One caveat softens it: `Bearer <jwt>` and `token: <jwt>` forms are refused (rules 2
   and 1), so the leak needs genuinely prose framing.

## False positives, my fifteen

`_names_a_credential` probed directly, and each verdict argued:

| Value | Result | Judgement |
|---|---|---|
| `token-bucket-limiter` | accepted | right — the TESTOPS-51 wrong refusal, fixed |
| `password-manager/tool` | accepted | right — `/` exempts it from rule 3 entirely |
| `secrets-service` | accepted | right — but by accident: `secrets` (plural) is not a credential word, so the rule never fires |
| `api-token-refresh` | accepted | right — credential word not last |
| `client-secret-rotation` | accepted | right |
| `bearer-middleware` | accepted | right |
| `auth-token-cache` | accepted | right |
| `session-token` | **refused** | **wrong** — a repository or service called `session-token` is entirely plausible; this is the same class as `token-bucket-limiter`, one notch shorter |
| `license-key-check` | accepted | right — bare `key` is not a credential word |
| `vault-token` | refused | defensible — reads as "the vault token", the `my-password` shape; a HashiCorp tool name would more likely be `vault-token-helper` |
| `oauth-secret-store` | accepted | right — suffix exemption is 2-part only, but the credential word is not last anyway |
| `passwords-list` | accepted | wrong for the *right reason to worry* — see below |
| `keyring-popup` | accepted | right |
| `cookie-token-sync` | accepted | right |
| `saml-assertion-token` | refused | borderline — a real term of art, but it does end in the credential word, which is the shape the rule exists for |

The incoherence to flag: `session-token` is refused while `passwords-list` is accepted, and
`password-list` would be refused (singular fires, plural does not). The boundary is not a
principle; it is the intersection of a "last part" rule and a singular-only word match. A user can
fix any refusal by rewording, and nothing refused is ever echoed, so the cost is friction, not
safety — but the rule should be able to explain `session-token` vs `api-token-refresh` without
pointing at a list.

## The scoped identifier rule

The build's decision (services.py:167–185): refuse a bare credential word; refuse ≤3 parts
**ending** in the credential word; exempt a 2-part name whose other part is a technical suffix;
accept everything else. I judge the scoping **sound and correctly pinned**: `token-bucket-limiter`
and `my-password` land on opposite sides by structure, not by word list, and both are pinned three
ways (function, boundary table, HTTP). The evidence in the build report for narrowing over
accepting the class is real — the ticket forbids letting `my-password` through. Two weaknesses:
the `_TECHNICAL_SUFFIXES` frozenset is a word list wearing a smaller coat (exactly what AC2 said
to avoid, though scoped to 2-part names only), and the residual-risk note in the build is honest
about 4+-part names but does not mention the singular/plural and `session-token` incoherences
above.

## Unknown keys and editing

AC4 verified over HTTP on the copy: posting `a_field_added_next_year=<ghp_ 36>` to the service
form returns **400**, the page names the key and says the configuration was *refused* rather than
saved without it, the token appears nowhere in the response, service rows 12 → 12, and a raw scan
of the copied SQLite file finds 0 occurrences of both the token bytes and the key name. An unseen
key carrying an ordinary value is also refused — the refusal is about the key, as claimed.

Editing matrix — every real settings field of every service kind, create then edit then read back
on `/config`:

| kind | fields | create | edit | read-back |
|---|---|---|---|---|
| `git_repo` | `repo` | 200, stored | 200, revised value on page, rename applied | yes |
| `jira_board` | `board`, `host` | 200, both stored | 200, both revised values on page | yes |
| `ado_pipeline` | `org`, `ado_project`, `pipeline_id` (int) | 200, all three stored | 200, revised values incl. `pipeline_id` 42→43 | yes |

No legitimate field refused, none dropped, nothing stored unscreened.

## Bypass table re-run

Attempt by attempt, over HTTP against the copy (unknown-key attempt covered under AC4 above):

| Attempt | Result |
|---|---|
| Unknown settings key + `ghp_` token | **400**, reason names the key, nothing stored (0 bytes of key or token in the file) — the silent drop is closed |
| Project named like a credential (`slug=password`) | 400 |
| Leading whitespace before token (repo) | 400 |
| Trailing newline (name and repo) | 400 |
| Double-URL-encoded `ghp_` token (board field) | 200 — stores the literal `%67%68%70_…` percent string, which nothing decodes; **not a credential in the store** (0 token bytes). Matches the build. Note: in the `repo` field the same attempt is refused by the `owner/name` shape rule, not by the screen |
| Mixed case (`PaSsWoRd=hunter2`) | 400 |
| Value split across fields (`name=token=`, `board=hunter2`) | 400 |

After all attempts: 0 occurrences of the token and `hunter2` in the store file, no project named
`password`, `/config` shows no token. One server-log observation: the refusals log the field and
rule only — the probe values appear nowhere in stderr.

## Contract suite

- `tests/test_config_credential_screen.py`: **113 passed**.
- Product suite (`pytest tests --ignore=tests/contracts`): **757 passed, 0 failed**.
- Contract suite: **2 failed, 30 passed, 3 skipped** — the failures are exactly `P07` and `P10`,
  the unchanged TESTOPS-7 promises recorded in the TESTOPS-51 review; `test_P23_password_in_free_text_field_is_refused`
  passes (3-test run: `...`).
- `git diff 91583de..HEAD` touches only `testops/services.py`, `testops/web/app.py`,
  `tests/test_config_credential_screen.py` and `factory/` files — no case-page golden changed.

## Three sharpest concerns

1. **A real token pasted in prose is stored (pre-existing, but the build claims otherwise).**
   `the key is ghp_<36>`, `aws id AKIA<16>`, `the jwt is <JWT>` are all accepted, because the
   whitespace exemption in rule 3, the `startswith` in rule 4 and the no-whitespace condition on
   the blob rule leave a sentence-wrapped paste untouched. I verified the identical leak on the
   pre-ticket baseline, so TESTOPS-56 did not open it — but the build's residual-risk note
   ("every pasted credential still meets rules 1, 2, 4 and 5") is false for this shape and should
   not be allowed to stand as the ticket's safety argument. A search-style scan for known prefixes
   and JWT/PEM shapes anywhere in a whitespace-containing value would close it; ticket it.
2. **The identifier boundary cannot explain itself at `session-token`.** A plausible service or
   repository name is refused while `passwords-list` is accepted and `password-list` would not be.
   The scoping decision is right, but the singular-only credential-word match plus the 2-part-only
   suffix exemption produce a boundary that is a list in disguise. The AC3 table should grow the
   singular/plural pair and `session-token` so the incoherence is pinned and arguable rather than
   latent.
3. **The `ghp_`/`gho_`/`ghu_`/`ghs_` qualification is charset-only, and weaker than the build's
   table reads.** `_GITHUB_CLASSIC` is `gh[pous]_[A-Za-z0-9]+` with no floor: `ghp_notes` and
   `ghp_onlyadocumentpath` (the ticket's own example, minus the underscore) are refused on their
   first characters alone — the exact class AC1 was meant to remove. Conversely the `github_pat_`
   floor of 22 means a truncated paste of a real fine-grained token (<22-char body) is accepted,
   though no realistic paste is that short. A 30+ floor on the classic body (the smallest real
   body ever issued is far above it) would fix the false positives at no false-negative cost.
