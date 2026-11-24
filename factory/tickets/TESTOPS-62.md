---
id: TESTOPS-62
title: The clause exemption fires on a word, not on a clause
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-61
---

# TESTOPS-62 - A word in the name is not a clause

## Why this exists

TESTOPS-61 exempts a name from the instance-label refusal when its parts "are a statement": a finite verb or a negator
anywhere in the name. That is true of `this-is-not-a-password`, which is why the ticket exists - but it is also true of
`my-password-is-here`, `the-token-is-abcd1234`, `has-my-token`, `is-my-password`, `this-token-was-leaked`,
`never-the-api-token`, `no-password-yet` and `acme-no-password` (the last defeats the any-position possessive refusal
outright, because a negator anywhere excuses the whole name). All ten were accepted by the T61 review.

None of them leaks a secret - the shape rules catch a real credential wherever it sits - so the cost is a rewording, not
a leak. But the rule's own claim is that it distinguishes an instance from a statement, and eleven of the review's ten
probes show it distinguishes an instance from *the appearance of one*. Also: `no` is in both the determiner class and the
negator class, which is how `no-password-yet` escapes both tests.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The exemption holds only when the parts form a **predication about the credential word**: a finite verb is present, a subject sits before it, and the credential word is the **complement after the verb**. `this-is-not-a-password` is accepted; `my-password-is-here` and `this-token-was-leaked` are refused, because the credential word is the subject of the predication rather than its complement. |
| AC2 | A fragment is not a clause: `has-my-token`, `is-my-password`, `never-the-api-token`, `no-password-yet`, `x-not-a-token-but-abcdef` are all **refused** (no subject before the verb, or no verb at all). |
| AC3 | A **negator alone never excuses** a name: `acme-no-password` and `acme-their-no-password` are refused by the any-position possessive/negation refusal. A word that belongs to two classes must not satisfy both tests; state the precedence explicitly and pin it. |
| AC4 | The ten review probes and the two named cases appear in the boundary table, each labelled with its one-line grammatical reason, so the boundary is arguable rather than latent. |
| AC5 | No detection is weakened and no legitimate name regresses: the T59 leak probes still refuse, the twenty ordinary values still accept, and `token-bucket-limiter`, `session-token`, `vault-token`, `password-manager/tool`, `acme-their-prod-db-password` (refused) keep their T61 verdicts. |
| AC6 | Contract suite green; full suite green; no case-page golden changes; the residual note in the code states what the exemption now requires, in the rule's own terms. |
