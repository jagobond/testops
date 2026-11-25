# TESTOPS-51 review — the credential screen on every field, and a project that can be deleted

Reviewer run, 2026-11-23. All work on a copy of `data/` served at `http://127.0.0.1:8895`
(`TESTOPS_DATA` pointed at the copy; the live store and 8791 were never touched). Every
false-positive and bypass result below was produced by hand over HTTP against that copy, not taken
from the build's table.

## Verdict

**PASS — mergeable, with findings.** AC1–AC8 hold as built and verified independently. One refusal
in my own boundary table is a refusal that would be *wrong* (`token-bucket-limiter`), and a cluster
of borderline ones; the build's own trade-off note anticipated this class. It does not block merge:
the screen's error text is non-blaming, the value never leaks, and the wrong-refusal class is narrow
(short unbroken identifiers whose credential word is a segment). A follow-up ticket should decide
deliberately whether that class is acceptable, rather than inherit it silently.

## The screen as a shape

`_looks_like_secret` (testops/services.py:159) is **a shape you can reason about, not a word-list
pile** — with one lexical exception that is where every false positive lives.

The shape rules, in order: (1) a `name=value` / `name: value` pair whose name is a credential word;
(2) issued-token shapes — PEM block anywhere in the value, a JWT (three dot segments beginning
`eyJ`), an `Authorization` scheme at the head; (3) an unbroken identifier of ≤3 segments containing
a credential word; (4) known credential prefixes (`AKIA`, `ghp_`, `xoxb-`, …) at any length, with
`sk-` and `github_pat_` qualified by body shape; (5) a 32+ character unbroken blob of high entropy
(base64 alphabet first, so `/` and `=` cannot claim to be a path). Prose (whitespace), coordinates
(`/`) and long snake_cased labels are exempt by construction — which is why the whole AC4 list and
`test password reset flow` pass. Rules 1, 2, 4 and 5 generalise to the next format: a new token
format is a prefix away, a new paste style is a pair away.

The exception is rule 3. "Short identifier containing a credential word" is a lexical judgement, and
no shape distinguishes `my-password` (rightly refused) from `token-bucket-limiter` (wrongly
refused). That single rule produces every wrong or borderline refusal I found. The build is honest
about this; the finding below makes the cost concrete.

It also reasons correctly at the boundary: `validate_settings` screens every key and every value,
`refuse_credential_in` screens every human-entered name, and both `add_service`/`update_service`
(via `_check_service`) and `add_project` go through them. A new field cannot opt out.

## False positives

Server copy, free-text Name field unless stated. "Wrong/borderline/right" is my judgement of
whether refusing a real user typing this value would be defensible.

Ticket AC4 — all eleven verified over HTTP, individually:

| Value | Result | Judgement |
|---|---|---|
| `jagobond/cotw-continuity` | accepted | right |
| `Jira board COTW` | accepted | right |
| `RuckoldtAndRylander` | accepted | right |
| `cotw-continuity pipeline #2` | accepted | right |
| `mwinteringham/restful-booker-platform` | accepted | right |
| `<tailnet-address>` | accepted | right |
| `localhost:8791` | accepted | right |
| `https://github.com/org/repo.git` | accepted | right |
| `COTW` | accepted | right |
| `TOPS` | accepted | right |
| `test password reset flow` | accepted | right |

My own boundary values (14, all a real user might type):

| Value | Field | Result | Judgement |
|---|---|---|---|
| `password-manager/tool` | name | accepted | right |
| `secrets-service` | name | accepted | right |
| `vault.internal` | host | accepted | right |
| `vault-prod` | host | accepted | right |
| `https://vault.internal:8200/v1/secret` | host | accepted | right |
| `skypoint-dashboard` | host | accepted | right |
| `docs/token-refresh.md` | name | accepted | right |
| `token-bucket-limiter` | name | **refused** | **wrong** — a rate-limiter algorithm, not a credential |
| `my-password-manager` | name | refused | borderline — a plausible tool name |
| `client_secret_manager` | name | refused | borderline — a module/label shape, not a secret |
| `Bearer token rotation work` | name | refused | borderline — prose, but indistinguishable from a pasted `Bearer <token>` head by shape alone |
| `AKIA-reviews-team` | name | refused | borderline — prefix rule fires at any length |
| `xoxb-migration-notes` | name | refused | borderline — a label about a token migration |
| `ghp_only_a_document_path` | name | refused | borderline — `ghp_` prefix rule is unqualified |

**Finding:** exactly one refusal would be wrong (`token-bucket-limiter`). All wrong/borderline
refusals come from the same two rules: the short-identifier rule (3) and the unqualified prefix
rule (4). None of the eleven ticket values is at risk, and nothing refused is ever echoed — the
screen errs safe and explains itself.

## Echo and bypass

**Echo.** A refused value (`passwd=Zq9Wx8Vv7Uu6Tt5`, and a project name `secret=Yy7Xx6Ww5Vv4`)
appears nowhere: not in the 400 error page, not on `/config` after the refusal, not in any form
field's value attribute, and not in the server log — the log lines name only the field and the rule
(`service name refused: it reads as a credential: the name 'passwd' is followed by '=' or ':' and a
value`); grep of the log file for every probe value returned zero hits. No store row is written for
any refused value (checked in SQLite after each refusal).

**Bypass attempts, without editing code:**

| Attempt | Result |
|---|---|
| Unknown settings key (`a_field_added_next_year=<ghp_ token>`) via POST | 303 accepted — but the form layer whitelists fields (`_settings_from_form`, app.py:2116), so the value is **silently dropped, never stored** (0 rows, 0 bytes in the db file). Not a leak; a silent-drop UX gap (see concerns). |
| Project named like a credential (`slug=password`) | refused 400 |
| Repo field, leading whitespace before the token | refused 400 |
| Name, trailing newline after the token | refused 400 |
| Double-URL-encoded `ghp_` in board field | accepted 303 — the stored value is the literal `%67%68%70_…` string, which nothing ever decodes, so it is not a credential in the store. Passes the screen, harmless today. |
| Mixed-case credential word (`PaSsWoRd=hunter2`) | refused 400 |
| Value split across fields (`name='token='` + `board='hunter2'`) | refused 400 |

No attempt puts a credential in the store. Two get past the screen into a 303, and both store
something that is not a secret.

## The delete route

On the copy: `POST /config/project/<slug>/delete`, control on `/config` states runs, snapshots and
cases are never deleted and names the counts when the project holds any (app.py:2232-2235).

- Empty project with one service: 303; project row gone, its service cascaded (service count for
  the project 1 → 0); all other rows untouched (47 runs, 30 snapshots, 208 cases before and after).
- `cotw` (33 runs, 16 snapshots, 61 cases): refused 400, page names all three counts, project and
  evidence intact — counts match `evidence_counts` exactly.
- Cannot be forced: `force=1`/`confirm=yes` fields → 400; trailing slash → refused; malformed slug
  (`COTW`) → 400; URL-encoded slug (`%63otw`) → 400 (refuses as cotw); a second submit → 400 each
  time; GET on the route → 404. No code path deletes an evidence row: `remove_project` only runs
  after `any(counts.values())` is false, and only deletes from `project`.

## Contract suite

`TESTOPS_BASE=http://127.0.0.1:8895` against the copy, suite unedited:

    5 failed, 21 passed, 3 skipped

The delta from main's 6/20/3 is exactly `test_P23_password_in_free_text_field_is_refused`, now
passing. The five remaining failures are P04, P05 (×2), P07 and P10 — the same promises TESTOPS-7
found, unchanged. Full product suite (`pytest tests --ignore=tests/contracts`, suite unedited):
**676 passed** in 145s. No golden or case-page fixture was touched by the ticket (`git diff` shows
only `testops/services.py`, `testops/web/app.py`, and the new `tests/test_config_credential_screen.py`).

## Live store untouched

    sha256 before: 48ac05fe14943cad3fa0192b5eeeb04b3a65352574f50b741fc354e03b418d9a
    sha256 after:  48ac05fe14943cad3fa0192b5eeeb04b3a65352574f50b741fc354e03b418d9a

Read-only check of the live db: `contract-audit-*` projects = 0; projects still exactly
`cotw`, `reqoverflow`, `restfulbooker`, `testops`.

## Three sharpest concerns

1. **The short-identifier rule refuses at least one value it should not.** `token-bucket-limiter`
   is an ordinary technical name, refused with 400. No shape separates it from `my-password`, which
   must be refused. The choice is deliberate-but-unstated: either accept this class (users reword),
   or scope the rule (for example to identifiers that are a credential word plus one part). Decide
   it in a ticket, with the boundary pinned, rather than inherit it.
2. **The unqualified prefix rule fires at any length.** `AKIA-reviews-team`, `xoxb-migration-notes`,
   `ghp_only_a_document_path` are all refused because of their first characters alone, while `sk-`
   and `github_pat_` are qualified by body shape. The same qualification (body length/charset like
   the real format) would remove three borderline refusals at no detection cost — a real `ghp_`
   token has a 36-character base62 body; a document path does not.
3. **The web layer silently drops unknown settings keys instead of refusing them.** A POST with an
   unseen settings key returns 303 and the value evaporates; the screen is never consulted on that
   path. Today the whitelist makes this safe (nothing reaches the store, and `validate_settings`
   would refuse the key if it did), but it means the "every value is screened" guarantee lives at
   the services layer only. A future refactor of `_settings_from_form` that forwards unknown keys
   would bypass the screen silently — the form layer should refuse unknown keys, not discard them.
