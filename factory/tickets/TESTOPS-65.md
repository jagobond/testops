---
id: TESTOPS-65
title: The vocabulary is a closed list, and the split decides the answer
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-63
---

# TESTOPS-65 - A list is always one word behind, and the hyphen decides the verdict

## Why this exists

`key` was invisible for three tickets because the vocabulary is a closed list of nouns. The T63 review then found
eighteen determiner-marked credential names that are still accepted by the same "no word matches" mechanism -
`the-passphrase`, `my-passwd`, `the-cred`, `the-bearer`, `the-jwt`, `the-cert`, `the-salt`, `the-seed-phrase`,
`pin-number`, `the-otp`, `totp-seed`, `the-dsn`, `the-webhook`, `the-session-id`, `the-cookie-value` - and the bare
`key = hunter2` value case is open, because the ticket fixed the name surface only.

It also found the qualification rule is not the word property the build claims: `apikey` and `apiKey` are refused alone
while `api_key` and `ssh_key` are accepted alone, because the split on non-alphanumerics destroys the qualifier before the
rule sees it. Same name, two verdicts, decided by spelling.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The vocabulary grows with the words that carry a credential in ordinary use - `passphrase`, `passwd`, `pass`, `cred`/`creds`, `bearer`, `jwt`, `cert`, `salt`, `seed` (as a phrase/seed), `otp`/`totp`, `dsn`, `webhook`, `cookie` - each screened by the existing instance and pair branches. |
| AC2 | **The false-positive bill is paid explicitly**: every added word is tested in the roles it has outside credentials - `pass` as a verb and a build step (`pass-through`, `pass-fail`), `cert` as a certificate *file* (`cert-store`, `certs-dir`), `salt` as hashing vocabulary (`salt-hash`), `seed` as data (`seed-data`, `seeding`), `bearer` as an HTTP scheme (`bearer-scheme`), `jwt` as a format (`jwt-decode`, `jwt-library`), `cookie` as a noun (`cookie-policy`, `cookie-banner`), `cred` as `credentials` in a path (`credentials-provider`). Report the full table; one new refusal of an honest name fails this ticket. |
| AC3 | **The hyphen stops deciding the verdict.** Qualification is normalised before the rule reads the name, so `apikey`, `apiKey`, `api_key` and `api-key` reach the same branch and produce the same verdict, both alone and with a determiner. Pin all four spellings in both positions. |
| AC4 | **The bare-value case is decided, not left to the form.** A value that is a bare `key`/`apikey` pair with a non-slot-shaped value - `key = hunter2`, `apikey = abc123`, `key=hunter2` - is refused, while a slot-shaped value (`key = ${API_KEY}`, `key = from-env`, `apikey = os.environ[...]`) is accepted because it names a slot rather than carrying a secret. Pin both directions. |
| AC5 | **The comment tells the truth about the list.** It states that the vocabulary is knowingly incomplete, that an unlisted word means an unscreened name, and that the value-shape rules - pair, PEM, JWT, prefix - are the real floor because they do not depend on anyone having thought of the word. A reader must not infer exhaustiveness. |
| AC6 | No detection is weakened and nothing honest regresses: the T59, T62 and T63 probe sets all keep their verdicts; contract suite green; full suite green; no case-page golden changes. |
