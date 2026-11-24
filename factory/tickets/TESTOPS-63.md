---
id: TESTOPS-63
title: `key` is not in the credential vocabulary, so `the-api-key-is-xyz` is never screened
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-62
---

# TESTOPS-63 - The commonest credential word is missing from the vocabulary

## Why this exists

The T62 review attacked the complement position and found the largest hole yet, and it is not in the new rule: it is in
the list of words the rule is about. `_CREDENTIAL_NAME` matches `apikeys?` (no separator) and any `_keys?` suffix, but it
never matches a bare or hyphenated `key`. So `the-api-key-is-xyz`, `my-private-key`, `the-signing-key` and `my-key` are
not screened by any branch at all - they are accepted because nothing looks at them.

This is the most common word in the vocabulary in real repositories, and it was invisible the whole time. That is the
lesson worth keeping: three rounds were spent refining the grammar of a rule whose subject list had a hole in the middle.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | `key` is a credential word when **qualified** - `api-key`, `private-key`, `secret-key`, `signing-key`, `access-key`, `auth-key`, `ssh-key`, `encryption-key` (hyphen or underscore or space) - and when **bare in an instance position** with a determiner or possessive: `the-key`, `my-key`, `their-key`. Screened by the same branches as every other credential word, so the same refusals and the same reasons apply. |
| AC2 | `key` is **not** a credential word where it means something else, and the boundary is pinned by test: `key-value-store`, `keyboard`, `keynote`, `keycloak`, `monkey`, `primary-key`, `foreign-key`, `hotkey`, `keystore`-as-a-product-name, `key-metrics`, `keys` in a plural-noun sense (`sorting-keys`). None of these may be refused. |
| AC3 | The false-positive risk is asymmetric and must be measured, not assumed: run the twelve named T62 cases, the twenty ordinary values from T59 and every value in AC2, and report the full table. A single new refusal of an honest name is a failure of this ticket, not a cost of it. |
| AC4 | The same `the-api-key-is-xyz` probe is added to the leak side of the boundary table, labelled refused, alongside `the-api-key` and `my-key`; and the vocabulary comment states the qualification rule rather than listing vendors or frameworks. |
| AC5 | No detection is weakened: the T59 and T62 probe sets all keep their verdicts; contract suite green; full suite green; no case-page golden changes. |
