---
id: TESTOPS-68
title: The bare-value rule misses the next line, the camel split invents a key, and the URL rule is not a floor
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-65
---

# TESTOPS-68 - Three seams the vocabulary ticket left open

## Why this exists

TESTOPS-65 grew the vocabulary, normalised spelling before the rule reads a name, and added a bare-value branch. Its
review reproduced the whole false-positive bill (33 rows plus twenty collisions, no honest name refused, 1043 passed) and
then found three seams.

1. **The bare-value branch is one newline behind.** The lookbehind on `_BARE_KEY_PAIR` excludes whitespace, so
   `auth = none\nkey = hunter2` is accepted - a second line of configuration carrying a literal - while the rule was
   written to catch exactly that. The settings blob and the prose sentence ("the key: it is in the vault") share the same
   exclusion, so the branch cannot yet tell one from the other.
2. **The camel split manufactures a bare `Key` part.** `_credential_parts` splits camel boundaries before the merge split,
   so `usbKey` arrives as `['usb', 'Key']` and the fragment `Key` matches the bare-word rule: `the-usbKey`, `the-hotKey`,
   `the-turnKey` are **refused** while `the-usbkey`, `the-hotkey` are accepted. Same word, verdict decided by capitalisation
   - the false positive this family of tickets exists to avoid.
3. **The inline-password rule is gated behind a credential word**, so a bare `postgres://app:***@db/qa` with no credential
   word anywhere is accepted. The AC5 comment claims the value-shape rules are the real floor because they need nobody to
   have thought of the word; this one fires only when somebody already did.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A bare key pair is refused wherever it begins a **line** of configuration, including after a newline and after another pair, while a sentence in prose is still accepted: `auth = none\nkey = hunter2` refused, `repo=x\nkey = hunter2` refused, "the key: it is in the vault" accepted. The distinguishing rule is the line boundary and the separator form, stated in the code - not a wider whitespace class. |
| AC2 | A camel-case fragment that is one segment of a longer word is **not** a bare credential word: `the-usbKey`, `the-hotKey`, `the-turnKey`, `the-monKey`, `the-donKey` are accepted, matching their all-lower-case forms. The qualifier path still refuses `the-apiKey`, `the-sshKey`, `the-privateKey`. Pinned in both directions, so capitalisation never decides a verdict. |
| AC3 | The inline-password shape is a **floor, not a gate**: `scheme://user:secret@host` is refused **anywhere in a value**, with or without a credential word beside it, with the password absent from the reason. An honest URL without a password (`postgres://app@db/qa`, `https://example.com/path`) is still accepted. Pinned both ways. |
| AC4 | The AC5 comment now tells the truth: it names which rules are shape-only (PEM, JWT, known prefixes, inline password) and which depend on the vocabulary, so a reader knows where the floor ends. |
| AC5 | No detection is weakened and nothing honest regresses: the 33-row bill, the twenty collisions, the T59, T62 and T63 probe sets all keep their verdicts; contract suite green; full suite green; no case-page golden changes. |
