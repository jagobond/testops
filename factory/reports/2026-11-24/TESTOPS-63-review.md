# TESTOPS-63 review - `key` as a credential word by qualification

Reviewer: independent review, run in worktree `C:/Users/<name>/Projects/testops-t63`
(branch `factory/testops-63-key`). The live store and port 8791 were never contacted: a
copy of `data/testops.db` was served on port 8799 with `TESTOPS_DATA` pointed at the
reviewer's scratch directory, and every probe below went over HTTP through the real form
posts (`/config/projects`, `/config/services`). 400 = refused, 303 = accepted.

Method note: the first server launch was started from the scratch directory and imported a
stale `testops` package (every probe accepted). It was killed and relaunched from the
worktree itself before any result below was recorded; the A-section table was then
re-run in full against the worktree code.

## Verdict

**PASS, with three concerns to carry forward.** AC1 holds over HTTP exactly as the build
report claims: every determiner-marked `key` name is refused by the instance branch, and
`the-api-key-is-xyz` - the probe that opened the ticket - is refused. AC2 holds: all
fourteen protected names accepted, one at a time, no new refusal of an honest name
anywhere in the run. AC5 holds: contract suite 37 passed 2 skipped, full suite 927 passed
2 skipped, no case-page golden changed, and every T59 and T62 verdict reproduced over HTTP
by this review, independently of the build's own table.

The concerns are about what the ticket teaches: the vocabulary is still a closed list of
nouns and my attack section (C) found eighteen determiner-marked credential names it
accepts; the qualification rule is spelling-dependent in a way the build's own framing
("a word property") does not admit; and the bare-key-with-a-secret-value case is accepted,
which is the same hole this ticket closed, one level down.

## Name-field probes

| value | verdict |
|---|---|
| `my-key` | refused (400) |
| `the-key` | refused |
| `their-key` | refused |
| `the-api-key` | refused |
| `the-signing-key` | refused |
| `my-private-key` | refused |
| `the-api-key-is-xyz` | refused |
| `my-key-is-here` | refused |
| `this-is-not-a-key` | accepted - a predication about a key, per the T62 rule |
| `signing-key` (alone) | accepted - a kind name, no determiner |
| `client-secret` (alone) | accepted - same reason, consistent with the T62 boundary |

All eight refusals come back on the same page shape as a `my-password` refusal; the three
acceptances match the build's boundary table. The ticket's own headline probe
(`the-api-key-is-xyz`) is genuinely closed.

## AC2 protected names, one at a time

Every one of these was posted individually and accepted:

`key-value-store`, `keyboard`, `keynote`, `keycloak`, `monkey`, `primary-key`,
`foreign-key`, `hotkey`, `keystore`, `key-metrics`, `sorting-keys`, `sort_keys=True`,
`board_keys`, `primary_key=id`.

Fourteen for fourteen, no new refusal of an honest name. AC3's stop condition is met as
measured here, not just as reported.

## Attacking the rest of the vocabulary

Refused by a branch (a vocabulary word matched): `my-passwd`, `secret`, `the-bearer`,
`the-bearer-token`.

Accepted because **no word matches** - a determiner plus a credential-shaped noun, never
looked at: `the-passphrase`, `the-pass`, `the-cred`, `creds`, `the-jwt`, `the-cert`,
`the-private`, `the-salt`, `the-seed-phrase`, `pin-number`, `the-otp`, `totp-seed`,
`the-conn-string`, `connection-string`, `the-dsn`, `the-webhook`, `the-session-id`,
`the-cookie-value`.

That is eighteen accepted names of the shape `the-<credential-noun>`. A real JWT pasted in
is still caught by the JWT shape rule and a real certificate by the PEM rule, but the
*name* that says "this is where the passphrase/seed/OTP lives" sails through, exactly the
way `the-api-key` did before this ticket.

So the answer to the question asked: **the vocabulary is a closed list of nouns, and it is
therefore always one word behind** - `key` proved that across three tickets. The
determiner rule alone cannot be generalised to any noun (`the-customer`, `the-session`
must stay accepted), so the list is load-bearing. Three words most worth adding:

1. **`passphrase`** - the commonest password synonym after `password` itself; `the-passphrase`
   is a name a real repository would plausibly hold.
2. **`cred`/`creds`/`credential`** - developer shorthand, singular and plural, and `creds`
   alone is already accepted today.
3. **`otp` (with `totp` and `seed` for `totp-seed`/`seed-phrase`)** - the whole 2FA family
   (`pin-number`, `the-otp`, `the-seed-phrase`) is invisible.

The list cannot be exhaustive: credential naming is open-class prose. `the-dsn`,
`the-webhook-signing-secret`, `the-cookie-value` and next year's word will always be one
ticket behind, which is why the value-shape rules (pairs, prefixes, PEM, JWT, entropy) -
which *are* word-free - are the rules that must never be weakened, and why the residual
section of `_looks_like_secret` honestly saying "an unrecognised format is not detected"
matters more than any entry added to the list.

## The bare-key value case

Posted as a free-text settings value through the `board` field (the `repo` field refuses on
format before the credential screen runs, which is itself worth knowing):

| value | verdict |
|---|---|
| `key = hunter2` | **accepted** |
| `key=hunter2` | **accepted** |
| `apikeys = abc123` | refused (pair branch) |
| `password = hunter2` | refused (pair branch) |
| `sort_keys=True` | accepted |

And directly against `validate_settings` (the field-name screen):

- field `key` = `hunter2` → **accepted**
- field `api_key` = `abc123` → refused
- field `signing_key` = `abc123` → accepted
- field `board_keys` = `x` → accepted

So a settings entry literally named `key` holding a short unremarkable secret is stored,
printed on the configuration page and copied into backups. The build's residual section
states this ("`key` remains accepted as a settings value on its own, deliberately: it is a
slot name") and I verified it rather than took it on trust. It is a defensible boundary
only in a narrow sense: `key` really is a configuration slot name in this product, the HTTP
form whitelists field names so no literal `key` field can be created there, and
`hunter2`-shaped values carry no shape to catch. But it is the next hole, not a closed one:
the exact failure this ticket fixed for *names* (`my-key` screened, bare `key` not) is
still open for *field names and values*, and the mitigation is a whitelist on one form
rather than a rule. If a settings path ever calls `validate_settings` with a caller-chosen
field dict, `key: <secret>` goes in.

## Qualification, tested

The build claims qualification is "a word property, not a verdict": `signing-key` alone is
accepted as a kind while `the-signing-key` is refused as an instance. Tested across
spellings, as names:

| value | verdict |
|---|---|
| `apikey` | refused |
| `api_key` | **accepted** |
| `apiKey` | refused |
| `accesskey` | refused |
| `ssh_key` | **accepted** |
| `the-apikey` | refused |
| `my-api_key` | refused |
| `my-accesskey` | refused |
| `my-ssh_key` | refused |
| `the-apiKey` | refused |

The distinction does **not** hold uniformly. It holds for hyphenated and spaced compounds
(the ones the build tested) but breaks for underscored ones: the name is split on
non-alphanumerics before the rule runs, so `api_key` becomes parts `api` + `key`, the
`api` qualifier is invisible, and the name falls back to bare-`key` treatment - accepted
alone, refused with a determiner. Meanwhile the merged and camelCase spellings
(`apikey`, `apiKey`) match `_CREDENTIAL_WORD` outright and are refused *even alone*, where
`signing-key` alone is accepted. So the same "kind name" is refused or accepted depending
on spelling, and the qualification property the build claims is really a property of the
hyphen. Not a regression - T62's spellings were as they were - but the ticket's framing
should not claim more than the code delivers.

## No weakening

Re-run over HTTP by this review, independent of the build's table:

- T59 leak probes: `ghp_...`, `AKIA...`, `glpat-...` refused; `sk-...` and `xoxb-...`
  pastes whose bodies do not match the format accepted (their long bodies in the T59 set
  are refused in the suite - see below); every verdict as before.
- T59 twenty ordinary values: all twenty accepted, verdicts kept.
- T62 twelve refused cases: all twelve refused, verdicts kept.
- T62 accepted set spot-check (`this-is-not-a-password`, `xox-not-a-slack-token`,
  `password-manager`, `prod-db-password`, `the-token-service`): all accepted.

Suites: contract `37 passed, 2 skipped`; full `927 passed, 2 skipped`, run with the
stripped environment (`env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX
PYTHONNOUSERSITE=1`). `git status` clean; the two ticket commits touch only
`testops/services.py`, `tests/test_config_credential_screen.py` and factory files - no
case-page golden changed.

## Three sharpest concerns

1. **The vocabulary is a closed noun list and stays one word behind.** Eighteen
   determiner-marked credential names (`the-passphrase`, `the-jwt`, `the-otp`,
   `the-seed-phrase`, `creds`, `the-cert`, `the-dsn`, ...) are accepted today by the same
   "no word matches" mechanism that hid `key` for three tickets. Add `passphrase`,
   `cred/creds`, and the OTP/TOTP/seed family, and say in the vocabulary comment that the
   list is knowingly incomplete and the value-shape rules are the real floor.

2. **Qualification is not the word property the build claims; it is a hyphen property.**
   `api_key` and `ssh_key` are accepted alone and refused with a determiner, while
   `apikey`/`apiKey` are refused alone - the split-on-non-alphanumerics step destroys the
   qualifier before the rule sees it. The boundary should be stated as spelling-dependent
   or fixed at the split.

3. **The bare-key value case is the next hole, already open.** `key = hunter2` as a
   settings value, and a settings field literally named `key` holding a secret, are both
   accepted and stored. The ticket fixed the name surface only; the value/field-name
   surface relies on the HTTP form's field whitelist. A follow-up ticket should either
   screen a bare `key=<value>` pair whose value is not a slot-shaped word, or document
   that a `key` field with a secret is out of scope *by rule*, not by accident of the
   form.
