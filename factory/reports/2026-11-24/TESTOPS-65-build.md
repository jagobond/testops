# TESTOPS-65 build - the list says it is incomplete, and the spelling stops deciding

Ticket: `factory/tickets/TESTOPS-65.md`. Branch: `factory/testops-65-vocabulary`, built in the linked
worktree `C:/Users/<name>/Projects/testops-t65`. The live store and port 8791 were never contacted:
every probe below is a direct call to `testops.services`, plus one in-process HTTP run against a
`tmp_path` database. Files touched: `testops/services.py` and the new
`tests/test_credential_vocabulary.py`. No case-page golden, template or fixture changed
(`git diff --stat`: one product file, 233 insertions, 24 deletions).

## The three faults, and what was done about each

1. **A closed noun list is one word behind.** Three vocabularies now exist and say what each is for:
   `_STRONG_WORDS` (a word that names a credential by membership), `_CONTEXT_WORDS` (AC1's words,
   which also have an honest life and are therefore screened only in a credential *position*), and
   `_INSTANCE_WORDS` (what the instance rule reads by membership). `bearer` moved from strong to
   context, which is what lets `bearer-scheme` be a settings field name again (see residual 3).
2. **The split destroyed the qualifier.** `_credential_parts` now normalises a name - separators
   undone, camel case undone, a merged key split when its prefix is a known qualifier - *before* any
   rule reads it. `apikey`, `apiKey`, `api_key` and `api-key` arrive as `["api", "key"]`.
3. **A bare key carrying a literal.** `_BARE_KEY_PAIR` plus `_is_reference`: a bare `key`/`keys`
   followed by a literal is refused, a slot reference is accepted; the same value test decides a
   context word's pair (`cert=/etc/ssl/ca.pem` accepted, `salt=abc123` refused), a key-family pair
   (`apikey = ${API_KEY}` accepted), and a settings field literally named `key` or `keys`.

## AC1 - the eighteen, each re-probed

Every name the T63 review found accepted is refused now, as is the rest of AC1's list.

`the-passphrase`, `my-passwd`, `the-cred`, `the-bearer`, `the-jwt`, `the-cert`, `the-salt`,
`the-seed-phrase`, `pin-number`, `the-otp`, `totp-seed`, `the-dsn`, `the-webhook`,
`the-session-id`, `the-cookie-value` - 15/15 refused, and so are `the-pass`, `creds`,
`the-credentials`, `their-jwt`, `our-cert`, `my-salt`, `the-seeds`, `my-totp`, `our-otp`,
`their-dsn`, `my-webhook`, `the-cookies`, `an-api-key`, `the-access-key`, `my-ssh-key`,
`the-connection-string`, `connection-string`, `the-certificate`. `the-passphrase`, `the-cert`,
`the-jwt`, `the-otp`, `the-salt` and `the-seed-phrase` are refused *by the same branch, with the
same reason string, as `my-password`* - asserted, not assumed.

`the-seed-phrase`, `the-cookie-value`, `the-session-id`, `pin-number`, `totp-seed` and
`connection-string` needed one thing the determiner rule could not supply: the compound *is* the
credential rather than a kind of it, so `_COMPOUND_CREDENTIAL` names those compounds (and the tail
after a determiner) as instances. That is a small, declared list of credential *names*, not another
noun list, and it is why `the-token-service` and `password-manager` stay accepted.

Pairs are refused too, with the value absent from the reason: `passphrase=<value>`, `pass=hunter2`,
`cred=abc123`, `jwt=<value>`, `cert=MIIC0wIB…`, `salt=a1b2c3`, `seed=a1b2c3`, `otp=123456`,
`totp=123456`, `dsn=postgres://app:<password>@db/qa`, `webhook=<value>`, `cookie=<value>`,
`credentials=<value>`. The last one matters: the DSN's password is *inside* the URL, so
`_INLINE_PASSWORD` refuses `scheme://user:secret@host` even though it is a URL.

## AC2 - the false-positive bill, the full table

Each row is asserted twice: the value is accepted by `_looks_like_secret` **and** stored by
`validate_settings` on that surface. `name` = a settings value or a human-entered name; `field` = a
settings field name. 33 rows, all accepted; one refusal of an honest name would fail this ticket.

| value | word | role outside credentials | surface | verdict |
|---|---|---|---|---|
| `pass-through` | pass | a verb / a build step | name | accepted |
| `pass-fail` | pass | a build step's outcome | name | accepted |
| `pass-through` | pass | a build step's outcome | field | accepted |
| `passwd-file` | passwd | a system file | name | accepted |
| `passphrase-manager` | passphrase | a tool that manages one | name | accepted |
| `credentials-provider` | cred | credentials as a path segment | name | accepted |
| `credentials-provider` | cred | credentials as a path segment | field | accepted |
| `creds-provider` | creds | credentials as a path segment | field | accepted |
| `bearer-scheme` | bearer | an HTTP scheme name | name | accepted |
| `bearer-scheme` | bearer | an HTTP scheme name | field | accepted |
| `Bearer tokens are refreshed hourly` | bearer | prose naming the scheme | name | accepted |
| `jwt-decode` | jwt | a library/function call | name | accepted |
| `jwt-library` | jwt | a library | field | accepted |
| `jwt.decode lives in lib/auth.py` | jwt | a library call inside a sentence | name | accepted |
| `cert-store` | cert | a certificate store | name | accepted |
| `certs-dir` | cert | a certificate directory | field | accepted |
| `cert=/etc/ssl/certs/ca.pem` | cert | a certificate *file* reference | name | accepted |
| `salt-hash` | salt | hashing vocabulary | name | accepted |
| `salt-hash` | salt | hashing vocabulary | field | accepted |
| `salt=$SALT` | salt | a salt read from the environment | name | accepted |
| `seed-data` | seed | seeding data | name | accepted |
| `seeding` | seed | the act of seeding | name | accepted |
| `seeding` | seed | the act of seeding | field | accepted |
| `otp-delivery` | otp | a delivery mechanism | name | accepted |
| `totp-enrolment` | totp | an enrolment flow | name | accepted |
| `dsn-scheme` | dsn | a scheme/format name | name | accepted |
| `dsn=postgres://db.example/qa` | dsn | a DSN that names a host | name | accepted |
| `webhook-delivery` | webhook | delivery machinery | name | accepted |
| `webhook-signature-scheme` | webhook | a signing scheme | field | accepted |
| `webhook=https://hooks.example.com/services/T000/B000` | webhook | a URL naming an endpoint | name | accepted |
| `cookie-policy` | cookie | a browser policy | name | accepted |
| `cookie-banner` | cookie | a consent banner | field | accepted |
| `credentials-provider` | credentials | a provider module | field | accepted |

The rule behind the table, stated once: a context word is read where it stands in a credential
position (determiner + head, a compound that names the credential, or a pair whose value is the
secret itself) and left alone where it names a kind of thing. Instances are unaffected: `the-cert`
refused, `cert-store` accepted; `the-pass` refused, `pass-through` accepted.

## AC3 - four spellings, both positions, pinned

| spelling | alone | with a determiner | pair | slot pair |
|---|---|---|---|---|
| `apikey` | accepted | `the-apikey` refused | `apikey=abc123` refused | `apikey = ${API_KEY}` accepted |
| `apiKey` | accepted | `the-apiKey` refused | `apiKey=abc123` refused | `apiKey = ${API_KEY}` accepted |
| `api_key` | accepted | `the-api_key` refused | `api_key=abc123` refused | `api_key = ${API_KEY}` accepted |
| `api-key` | accepted | `the-api-key` refused | `api-key=abc123` refused | `api-key = ${API_KEY}` accepted |

"Alone" is the verdict `signing-key`, `ssh_key` and `api_key` already had in T63: a qualified key
with no determiner is a kind name, and the determiner is what makes it an instance. The four
determined forms share one reason string, identical to `my-key`'s, and a test asserts the four bare
verdicts and the four determined verdicts are each a single value - so the punctuation cannot decide
anything again. `_credential_parts("monkey") == ["monkey"]` and `_credential_parts("hotkey") ==
["hotkey"]` are pinned as the other direction: a merged word with a prefix that is not a qualifier is
a different word, not a bare key.

## AC4 - the bare value, both directions

| value | verdict |
|---|---|
| `key = hunter2` | refused |
| `key=hunter2` | refused |
| `apikey = abc123` | refused |
| `keys = abc123`, `api_key=abc123`, `api-key=abc123`, `apiKey=abc123` | refused |
| `key = ${API_KEY}` | accepted |
| `key = from-env` | accepted |
| `apikey = os.environ[API_KEY]` | accepted |
| `key = $API_KEY`, `key = os.getenv('API_KEY')`, `apikey = from-vault`, `key = %API_KEY%` | accepted |

At the field surface (`validate_settings({"key": …})`) the same two directions are pinned: `key` and
`keys` holding `hunter2` are refused, holding `${API_KEY}`, `from-env` or `os.environ[API_KEY]` are
stored. This closes the exact entry the T63 review recorded (`field key = hunter2 → accepted`) as a
*rule*, not as an accident of the HTTP form's field whitelist. The honest key settings keep their
values: `sort_keys=True`, `sorting_keys=asc`, `primary_key=id`, `board_keys=COTW`, `jira_key=TOPS`,
`key_metrics=latency` all store. Prose keeps the space it needs: "the key: it is in the vault" and
"ask for the key: the platform team has it" stay configuration, because the lookbehind excludes a
space and `_`/`-` as well as alphanumerics.

## AC5 - the comment tells the truth

The vocabulary comment states, in those words: the list is **knowingly incomplete**; an unlisted word
means an **unscreened name**; and the **value shape** rules (pair, PEM, JWT, prefix, entropy) are the
real floor because they need nobody to have thought of the word. `_looks_like_secret`'s docstring
carries the same sentence next to its existing "an unrecognised format is not detected at all".
A test reads the module source and fails if any of those statements is edited away - a comment nobody
checks is not a statement.

## AC6 - no detection weakened

- Full suite: **1043 passed, 2 skipped** (baseline before this ticket: 927 passed, 2 skipped; the
  difference is the 116 new pins).
- Contract suite `tests/contracts`: **37 passed, 2 skipped**, unchanged.
- `git status` clean of case-page goldens: only `testops/services.py` and the new test file.
- T62's twelve refusals, T59's twenty ordinary values and T63's accepted/refused `key` sets are
  transcribed into the new file and re-asserted: every verdict kept. Every issued token shape
  (`AKIA`, `ghp_`, `glpat-`, `xoxb-`, `sk-`), the PEM block and the JWT are still refused.

## Residual risk, and two changes of verdict worth naming

1. **The list is still incomplete, by design.** `the-private` remains accepted (it names no credential
   word; `private` alone is not one, and the screen will not guess "private key"), and next year's
   noun will be invisible on the day it arrives. That is why AC5 is in the code rather than implied.
2. **A field name that is a context word in final position is refused.** `cert`, `seed`, `creds`,
   `pass` as field names are refused because they are the slot; `certs-dir`, `pass-through`,
   `jwt-library`, `cookie-banner`, `credentials-provider` are accepted. A context word *before* the
   head (`cert-store`) is a description, not a slot.
3. **Two loosened verdicts, named rather than hidden.** `apikey`, `apiKey`, `accesskey` and
   `sshkey` alone were refused for their spelling and are accepted now, which is the point of AC3
   (`api_key` and `ssh_key` were always accepted alone; T63's review recorded the disagreement).
   And `bearer-scheme` as a *settings field* was refused by the search-based strong vocabulary and is
   accepted now that `bearer` is a context word; `bearer` and `the-bearer` are still refused. Neither
   is a probe-set entry, and no T59/T62/T63 verdict changes.
4. **A literal in a key slot is refused even when the value has no shape to catch.** `key = hunter2`
   is refused because the *position* says the value is a secret and `hunter2` is not a reference -
   not because anything about `hunter2` is recognisable. That is the honest basis, and it is the same
   basis on which `key = ${API_KEY}` is accepted.

## Verification

```
env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
  C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe -m pytest -q
1043 passed, 2 skipped in 159.57s

env ... -m pytest -q tests/contracts
37 passed, 2 skipped in 11.14s
```
