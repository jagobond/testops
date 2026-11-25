# TESTOPS-63 build - `key` is in the vocabulary now, by qualification

Ticket: `factory/tickets/TESTOPS-63.md`. Branch: `factory/testops-63-key`.
Store copy used for the HTTP run: `data/testops.db`, copied to a scratch path first. The live store
and port 8791 were never contacted.

One note on the brief: `factory/reports/2026-11-24/TESTOPS-62-review.md` does not exist in this
worktree, on any branch, or in the primary checkout. Concern 1 was taken from the ticket, which
restates it in full (the vocabulary hole, not a grammar hole).

## The rule, in the rule's own terms

`key` is the one credential word whose reading is decided by **qualification**, not membership, so it
is deliberately *not* added to `_CREDENTIAL_NAME`. The qualification rule is stated once, at the
vocabulary:

> a `key`/`keys` part is a credential word when another part stands before it in the same name
> (qualified, `the-signing-key`) or when a determiner/possessive does (bare in the instance
> position, `my-key`) - never when it stands alone or as the only word.

It is applied in the two rules where a name is a **position** rather than a bare word:

- `_KEY_WORD` - the instance rule, `_names_a_credential`. `key`/`keys` joins the credential-head set
  there and nowhere else, so `my-key`, `the-api-key`, `the-signing-key` and `the-api-key-is-xyz` walk
  the same branches, and get the same reason, as `my-password`. A lone `key` is not an instance
  label (it is a configuration slot name), and it is not a bare credential word either: `strong`,
  not the union, decides the one-word case.
- `_DETERMINER_KEY_PAIR` - the pair branch, for a key *with* a value: `my-key=hunter2`. Only a hyphen
  or underscore joins the two, because with a space allowed the ordinary sentence "the key: it is in
  the vault" would be read as a pair. `sort_keys=True`, `sorting_keys=asc` and `primary_key=id` stay
  configuration.

It is not applied to a settings field name. `board_keys` is exactly the field the refusal message
says settings may hold, and `sort_keys=` is an honest name: refusing those to catch `my-key=` would
be the false positive this ticket forbids.

## AC1 - qualified and bare-in-instance

Refused, all by the instance branch with the reason "it is a short identifier naming a credential"
(asserted identical to `my-password`'s): `my-key`, `their-key`, `our-key`, `the-key`, `my_keys`,
`the_keys`, `their_key`, `the-api-key`, `the-private-key`, `my-secret-key`, `the-signing-key`,
`the-access-key`, `the-auth-key`, `the-ssh-key`, `the-encryption-key`, `my-deploy-key`,
`the-api-key-is-xyz`, `my-key-is-here`. `my-key=hunter2`, `the-key: abc123`, `their_keys=v` are
refused by the pair branch, with the value absent from the reason.

The T62 grammar applies unchanged: `the-api-key-is-xyz` is refused because `key` is the *subject* of
`is` (not its complement), while `this-is-not-a-key` is a predication about a key and stays accepted.

**Qualification is a word property, not a verdict.** `signing-key` on its own is accepted, exactly as
`client-secret` is (both are in the boundary table): a compound with no determiner names a kind. The
determiner is what marks an instance. This is stated in the docstring and pinned by test.

## AC2 - `key` meaning something else, each pinned

`key-value-store`, `keyboard`, `keynote`, `keycloak`, `monkey`, `primary-key`, `foreign-key`,
`hotkey`, `keystore`, `key-metrics`, `sorting-keys` - all accepted, pinned one by one in
`test_key_that_means_something_else_is_accepted` and again in the boundary table with a one-line
grammatical reason each. `key` and `keys` alone are accepted too (a slot name, a collection name).

## AC3 - the measurement, full table

Stop condition: **one new refusal of an honest name fails the ticket.** Result: **zero**.

### AC1 probes - refused

| value | verdict |
|---|---|
| `my-key` | refused |
| `their-key` | refused |
| `the-key` | refused |
| `the-api-key` | refused |
| `the-api-key-is-xyz` | refused |
| `my-private-key` | refused |
| `my-signing-key` | refused |
| `the-access-key` | refused |
| `the-auth-key` | refused |
| `the-ssh-key` | refused |
| `the-encryption-key` | refused |
| `my-key=hunter2` | refused |

### AC1 probes - qualified but determiner-less: kind names, accepted

| value | verdict |
|---|---|
| `key` | accepted |
| `keys` | accepted |
| `api-key` | accepted |
| `private-key` | accepted |
| `secret-key` | accepted |
| `signing-key` | accepted |
| `access-key` | accepted |
| `auth-key` | accepted |
| `ssh-key` | accepted |
| `encryption-key` | accepted |

### AC2 - `key` meaning something else, all accepted

| value | verdict |
|---|---|
| `key-value-store` | accepted |
| `keyboard` | accepted |
| `keynote` | accepted |
| `keycloak` | accepted |
| `monkey` | accepted |
| `primary-key` | accepted |
| `foreign-key` | accepted |
| `hotkey` | accepted |
| `keystore` | accepted |
| `key-metrics` | accepted |
| `sorting-keys` | accepted |

### TESTOPS-62 twelve cases - every verdict kept (refused)

| value | verdict |
|---|---|
| `my-password-is-here` | refused |
| `the-token-is-abcd1234` | refused |
| `this-token-was-leaked` | refused |
| `my-secret-has-value` | refused |
| `has-my-token` | refused |
| `is-my-password` | refused |
| `never-the-api-token` | refused |
| `no-password-yet` | refused |
| `x-not-a-token-but-abcdef` | refused |
| `acme-no-password` | refused |
| `acme-their-no-password` | refused |
| `not-a-password` | refused |

### TESTOPS-59 twenty ordinary values - every verdict kept (accepted)

| value | verdict |
|---|---|
| `the token is validated in middleware` | accepted |
| `our password policy is documented` | accepted |
| `Bearer tokens are refreshed hourly` | accepted |
| `secrets are rotated weekly` | accepted |
| `jwt.decode lives in lib/auth.py` | accepted |
| `no token needed for this endpoint` | accepted |
| `docs/how-to-reset-your-password.md` | accepted |
| `pat-notes.md` | accepted |
| `gh_workflows/` | accepted |
| `akia-notes` | accepted |
| `xox-not-a-slack-token` | accepted |
| `the private key is in vault` | accepted |
| `my-password-manager` | accepted |
| `session-token` | accepted |
| `vault-token` | accepted |
| `password-list` | accepted |
| `passwords-list` | accepted |
| `token-refresh-service` | accepted |
| `the-token-service` | accepted |
| `my-secret-store` | accepted |

The two earlier probe sets are transcribed into the test (`T62_REFUSED`, `T59_ORDINARY`) with a
length assertion, so the table above cannot drift from what the suite checks.

## The route, measured on a copy of `data/`

`data/testops.db` copied to scratch, served on an ephemeral port (not 8791):

- `the-api-key-is-xyz`, `the-api-key`, `my-key`, `my-private-key` -> **400**, value absent from the
  page, services 12 -> 12 for those.
- `key-value-store`, `primary-key`, `sorting-keys`, `keyboard`, `key` -> **200**, stored as named.
- Raw scan of the copied file: no occurrence of either refused probe.

## AC4 - boundary table and vocabulary comment

`the-api-key-is-xyz`, `the-api-key` and `my-key` are in `BOUNDARY` as refusals, with `my-signing-key`,
`key`, `signing-key`, `key-metrics`, `primary-key`, `foreign-key`, `key-value-store`, `sorting-keys`
and the five one-word lookalikes as acceptances, each with a grammatical reason. The comment at the
vocabulary states the qualification rule; it names no vendor, framework or product.

## AC5 - verification

    env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
      C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe -m pytest -q

- Contract suite: `pytest tests/contracts -q` -> **37 passed, 2 skipped**.
- Full suite: `pytest -q` -> **927 passed, 2 skipped**.
- Case-page goldens untouched: `git status --short` shows only `testops/services.py` and
  `tests/test_config_credential_screen.py`.

## Residual, stated rather than hidden

- A settings **field name** that is only `..._key`/`..._keys` (`signing_key`, `api_keys` as a field
  name rather than a value) is not refused by `_CREDENTIAL_NAME_ALONE`, because `board_keys` is a
  field the settings message promises to accept. The value in such a field is still screened.
- `signing-key=<value>` (qualified, no determiner, with a value) is not refused by the pair branch:
  a qualifier is open-class and the same shape is honest configuration under another name
  (`deploy-key=...` versus `sort_keys=...`). The instance rule sees it, the pair rule does not.
- A key-named value inside a longer name (`acme-signing-key-prod`, no determiner) is a label as a
  kind name, exactly as `prod-db-password` is.
- `key` remains accepted as a settings value on its own, deliberately: it is a slot name.
