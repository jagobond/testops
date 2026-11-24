"""Projects and services: the store's model of what is being analysed, and how it is reached.

TESTOPS-38 implements ADR-1. A **project** is an identity - a slug and a name. A **service** is one
analysable resource inside it: a ``git_repo`` (role ``product`` or ``test``), a ``jira_board`` or an
``ado_pipeline``. Nothing here talks to Jira or ADO; the connectors land on top of this model in the
next tickets. What exists now is the seam they will use:

  * a project and its services are **rows**, so a second team adds one on the configuration page and
    needs no build, no deploy and no restart;
  * each service records its **own** last-consulted state and reason, so a page can say which
    service was not connected and why instead of one sentence standing for the whole project;
  * ``settings`` holds hosts, repository coordinates, board keys and paths. It never holds a
    credential: :func:`validate_settings` refuses one, and secrets resolve from the environment at
    call time (AC5).
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import math
import re
from dataclasses import dataclass, field

from . import sources
from .config import Project, Repo

TYPES = ("git_repo", "jira_board", "ado_pipeline")
ROLES = ("product", "test")

# What a service can say about itself. These are the words a page prints, and they never share a
# meaning: "not connected" is a connector this build does not have, "policy" is a source somebody
# forbids, "absent" is a service the project does not declare at all.
AVAILABLE = "available"
NOT_CONNECTED = "not_connected"
POLICY = "policy"
ABSENT = "absent"
NOT_ASSESSABLE = "not_assessable"
SERVICE_STATES = (AVAILABLE, NOT_CONNECTED, POLICY, ABSENT, NOT_ASSESSABLE)

CREATE_AT = "%Y-%m-%dT%H:%M:%S+00:00"

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

# TESTOPS-51. One screen, every field. Before this ticket the check was "does the value contain
# token/password/secret/bearer anywhere", it was called only from :func:`validate_settings`, and the
# service *name* - a free-text field with no format of its own - never called it at all, so
# `name=password=hunter2` was stored and echoed. A per-field check is a check the next field skips;
# the rules below are applied at the store boundary, to every settings value and every human-entered
# name, so a field added tomorrow is covered by existing.
#
# A credential is a *shape*, not a word. Four shapes are recognised, in this order:
#
#   1. a `name=value` pair whose name is a credential word, anywhere in the value - `password=hunter2`,
#      `Authorization: Bearer ***`, `api_key = "..."`. The name stands alone, so `tokens` is not
#      `token` and `cotw-continuity` contains no credential name at all;
#   2. an issued-token shape *searched anywhere* in the value, not only at position 0 - a PEM block,
#      a JWT, an `Authorization` header, and (rule 4) a known prefix with its format's real body
#      (TESTOPS-59 AC1: a real token pasted inside a sentence is still a token);
#   3. a value that is one unbroken token naming a credential *instance* (`my-password`,
#      `acme-their-password`, `an-api-token`). Prose is not one token, which is why "test password
#      reset flow" is configuration and is stored. TESTOPS-59 AC3 states the boundary structurally -
#      see :func:`_names_a_credential` - rather than by a word list, and TESTOPS-61 AC1/AC2 makes it
#      read *every* part: a determiner or possessive in any position names an instance, unless the
#      parts are a predication about the credential word (`this-is-not-a-password`, TESTOPS-62);
#   4. a known credential prefix with the body that format really issues, at any position;
#   5. a known credential prefix with a body *too short* for that format (TESTOPS-61 AC3): a cut-off
#      paste of the most recognisable prefix is refused with a reason that says so, never accepted
#      silently as a truncation.
#
# TESTOPS-63 narrowed that and TESTOPS-65 widens it again, honestly. The vocabulary below is
# **knowingly incomplete**, and it will stay incomplete: credential naming is open-class prose.
# `the-dsn` was invisible until this ticket and `the-webhook-signing-secret` is invisible today; next
# year's word will be invisible tomorrow, because the list only holds the words somebody has already
# thought of. An unlisted word therefore means an **unscreened name** - this screen does not claim to
# know every credential noun, and no reader should infer that it does.
#
# What holds when the list fails is the **value shape**, divided in two (TESTOPS-68 AC4) because the
# earlier comment claimed every value rule was word-free and that was not true:
#
#   * **shape-only** - no vocabulary is read at all: the PEM block, the JWT, the known issued-token
#     prefixes (with their real bodies and truncations), the base64/entropy floor, and the inline
#     password in a URL (`scheme://user:secret@host`, TESTOPS-68 AC3). These fire on a name nobody
#     has listed, which is why they are the floor this screen stands on;
#   * **vocabulary-dependent** - a credential word has to be known first: the `name=value` pair whose
#     name is a strong or context word, the instance rule for a determiner-marked name, the
#     qualification rule for `key`, and the bare `key` pair. They catch what the words name, and
#     nothing else; the bare `key` pair is word-free only in the sense that `key` itself is known.
#
# Credential words are matched singular and plural alike, so `passwords-list` and `password-list` are
# decided by the same rule instead of by an accident of spelling (TESTOPS-59 AC3).
#
# `key` is deliberately not a member of the membership vocabulary (TESTOPS-63). It is the one
# credential word whose reading is decided by *qualification*: `api-key`, `signing-key` and
# `encryption-key` name a credential, while `keyboard`, `primary-key`, `key-metrics` and a bare `key`
# name a part of a keyboard, an index, a measurement or a configuration slot. The rule is stated once:
# a `key`/`keys` part is a credential word when another part stands before it in the same name
# (qualified, `the-signing-key`) or when a determiner/possessive does (bare in the instance position,
# `my-key`) - never when it stands alone or as the only word. TESTOPS-65 AC3 removes the last way
# spelling could decide that: the name is **normalised into parts before any rule reads it**, so
# `apikey`, `apiKey`, `api_key` and `api-key` arrive as the same two parts and reach the same branch.
# Qualification is a property of the name, not of the hyphen.
_STRONG_WORDS = (r"passwords?|passphrases?|passwd|pwd|tokens?|api[ _-]?keys?|apikeys?|secrets?|"
                 r"authorizations?|private[ _-]?keys?|access[ _-]?keys?|client[ _-]?secrets?")
# TESTOPS-65 AC1/AC2. Words that carry a credential in ordinary use **and** have an honest life of
# their own: `pass` is a build step, `cert` is a file, `salt` is hashing vocabulary, `seed` is data,
# `jwt` is a format, `cookie` is a policy, `cred` is a path segment in `credentials-provider`, and
# `bearer` is the HTTP scheme name (`bearer-scheme`). They are therefore screened only where they
# stand in a credential *position* - the instance position, a compound that names the credential
# outright (`seed-phrase`, `pin-number`, `totp-seed`), or a pair whose value is the secret itself -
# and left alone where they name a kind of thing. AC2's table is the measurement, one word at a time.
_CONTEXT_WORDS = (r"pass|creds?|credentials?|jwts?|certs?|certificates?|salts?|seeds?|otps?|totps?|"
                  r"dsns?|webhooks?|cookies?|bearer")
# The membership vocabulary used by the instance rule. The key family (`apikey`, `api_key`,
# `api-key`, `apiKey`) is deliberately absent: `key` is decided by qualification, not membership, so
# `apikey` is normalised to `api` + `key` and read as a qualified key - the same branch, and so the
# same verdict, as `api_key` and `api-key`.
_INSTANCE_WORDS = (r"passwords?|passphrases?|passwd|pwd|tokens?|secrets?|authorizations?|"
                   r"client[ _-]?secrets?")
# The pair's name is followed by `=` or `:` and then something - the shape a secret is pasted in.
# The value is captured because TESTOPS-65 AC4 decides a key pair by the *shape of the value*: a slot
# reference (`${API_KEY}`, `from-env`, `os.environ[...]`) names where the credential lives, while a
# literal is the credential.
_CREDENTIAL_PAIR = re.compile(rf"(?i)(?<![A-Za-z0-9])({_STRONG_WORDS})[ \t]*[:=][ \t]*"
                              rf"(?P<value>[^\s,;]+)")
# TESTOPS-65: the same shape for the context words, which have honest roles where the value is a
# reference rather than a secret - `cert=/etc/ssl/ca.pem`, `salt=$SALT`, `webhook=https://...` are
# configuration, while `salt=abc123` and `cert=MIIC...` are the material itself.
_CONTEXT_PAIR = re.compile(rf"(?i)(?<![A-Za-z0-9])({_CONTEXT_WORDS})[ \t]*[:=][ \t]*"
                           rf"(?P<value>[^\s,;]+)")
# TESTOPS-65 AC4: a *bare* `key` has no qualifier to make it a credential word, so it is the value
# that decides. The lookbehind excludes `_` and `-` as well as alphanumerics, which is what keeps
# `sort_keys=True`, `sorting_keys=asc` and `primary_key=id` - the settings this product really has -
# out of the rule.
#
# TESTOPS-68 AC1 states the distinguishing rule exactly: a bare key pair is refused where it *begins
# a line* of configuration - at the start of the value, after a newline (with optional indentation),
# or after a separator such as `;` or `,` - and accepted where it stands inside a sentence. The
# lookbehind therefore excludes horizontal whitespace only (space and tab), so a preceding newline is
# a line boundary while "the key: it is in the vault" is prose; `[ \t]*` after the boundary lets an
# indented settings line be read as a line. It is a line-boundary rule, not a wider whitespace class:
# allowing any whitespace in the lookbehind is what accepted `auth = none\nkey = hunter2`.
_BARE_KEY_PAIR = re.compile(r"(?im)(?:^|(?<=[^A-Za-z0-9_ \t]))[ \t]*keys?[ \t]*[:=][ \t]*"
                            r"(?P<value>[^\s,;]+)")
# The key family as a *name*: the spellings AC3 normalises to one reading.
_KEY_FAMILY = re.compile(r"(?i)^(?:keys?|apikeys?|api[ _-]?keys?|apikey|accesskeys?|sshkeys?)$")
# A value that names where a credential lives rather than being the credential: an environment
# reference, a template placeholder, an options-flag lookup, a `from-<source>` name, or a path/URL.
_REFERENCE_VALUE = re.compile(
    r"""(?ix)^(?:
          \$ | %\w+% | \{\{? | <                     # ${VAR}, $VAR, %VAR%, {{ ref }}, <slot>
        | (?:os\.)?(?:environ|getenv|env)(?:\[|\(|\s*:)   # os.environ[...], getenv(...), env:
        | from[-_][a-z0-9_-]+                        # from-env, from_vault
        | (?:vault|ssm|secrets?|env|ref|secret)://
        | [a-z][a-z0-9+.-]*://                       # any scheme: postgres://, amqp://, redis://
        | [.~]?[/\\] | [A-Za-z]:[\\/] | https?://    # a path or a URL: a location, not a secret
        )[^\s]*$""")
# A URL that carries its own password - `scheme://user:secret@host/db` - is not a location: the
# credential is written into it. `dsn=postgres://app:***@db/qa` is the secret itself, while
# `dsn=postgres://db.example/qa` and `cert=/etc/ssl/ca.pem` are references. TESTOPS-68 AC3: this is a
# **floor**, not a gate - it is checked anywhere in a value, beside a credential word or without one,
# because a password in a URL is a shape that needs nobody to have thought of the word `dsn`.
_INLINE_PASSWORD = re.compile(r"(?i)://[^/@\s]*:[^/@\s]*@")


def _is_reference(value: str) -> bool:
    """Whether a pair's value names a slot/location rather than carrying a secret (TESTOPS-65 AC4)."""
    if _INLINE_PASSWORD.search(value):
        return False
    return bool(_REFERENCE_VALUE.match(value))


# Compounds whose *name* is a credential in ordinary use, not a kind of thing: a seed phrase is the
# passphrase, a pin number is the PIN, a connection string carries the DSN. Accepted alone they would
# be `session-token`-shaped kind names; naming a credential outright is what makes them instances.
_COMPOUND_CREDENTIAL = re.compile(
    r"(?i)^(?:seed[ _-]?phrases?|pass[ _-]?phrases?|pin[ _-]?numbers?|totps?[ _-]?seeds?|"
    r"otps?[ _-]?seeds?|session[ _-]?ids?|cookie[ _-]?values?|connection[ _-]?strings?|"
    r"conn[ _-]?strings?|dsns?)$")
# A name on its own, used for the settings *key* and for the single-token rule.
_CREDENTIAL_NAME_ALONE = re.compile(rf"(?i)(?:^|[^A-Za-z0-9]){_STRONG_WORDS}(?:$|[^A-Za-z0-9])")
# `Bearer abc123`, `Basic dXNlcjpwYXNz`: an authorization scheme and exactly one unbroken value.
# TESTOPS-59 AC1/AC2: the scheme is the shape only when the value is the whole remainder. A sentence
# that happens to open with the word ("Bearer token rotation work continues") continues past the
# first word, so it is prose, not a header - scanning prose must not turn into refusing sentences.
_AUTH_SCHEME = re.compile(r"(?i)^\s*(?:bearer|basic|digest|token)\s+[^\s,;]+$")
# A PEM private-key block, wherever it was pasted in a longer value.
_PEM_BLOCK = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")
# A JWT: the base64 header, a payload and a signature, three dot-separated segments, searched
# anywhere in the value (a JWT pasted after "the jwt is" is still a JWT).
_JWT = re.compile(r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"
                  r"(?![A-Za-z0-9_-])")

# TESTOPS-44. Base64 is the most common way a credential is written down, and its alphabet contains
# `/` - the very character the separator exemption below used to read as proof of configuration. So
# the charset is checked first: a long blob of the base64 alphabet is refused whatever punctuation it
# contains. The entropy floor separates an encoded secret from a path or a coordinate made of words:
# word-shaped settings measured here sit below 4.1 bits per character
# (`SomeOrg/SomeVeryLongRepositoryName2` is 4.023), base64 of arbitrary bytes above 4.4. The floor is
# a threshold, not a proof, and is set to keep every plausible configuration in AC2 accepted.
_BLOB_MIN = 32
_BASE64 = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")
_BASE64_ENTROPY = 4.3

# TESTOPS-44, TESTOPS-56, TESTOPS-59. A known token prefix is a shape **at any position** in the
# value, not only at position 0 (TESTOPS-59 AC1: a real token pasted inside a sentence is still a
# token). The entropy floors below only judge values of 32+ characters, so the shortest AWS
# credential - an `AKIA` key ID at 20 characters - would pass by being short; this rule runs before
# them. Each entry is the literal prefix a published format issues, the whole token's shape, and the
# body length range that format really uses - a floor AND a ceiling (AC4), so `ghp_notes` (five
# characters) is a word and an 82-character fine-grained paste truncated to 22 is not a token.
# Matching is case-sensitive, because these prefixes are case-sensitive in the formats themselves and
# lower-case lookalikes (`skipton-branch`, `masking/x`, `task-akia-review`) are real configuration.
# The lookarounds stop a match inside a longer alphanumeric run (`xghp_...`, `ghp_..._suffix`). Only
# the prefix is named in the refusal - never the value.
#
# The bodies are the formats' own:
#
#   AKIA / ASIA     a 20-character AWS key ID: 16 upper-case base32 characters
#   ghp_ gho_ ghu_ ghs_
#                   GitHub classic: one unbroken base62 body, 36 characters today and 40 in the
#                   legacy format. `ghp_notes` is below the floor and is a name.
#   github_pat_     GitHub fine-grained: 22 base62 characters, an underscore, then 59 more. A
#                   22-character paste is a truncation, not a token - and since TESTOPS-61 AC3 a
#                   truncation of a fixed-body prefix is refused by name, not accepted silently
#                   (see :func:`_truncated_token_in`).
#   glpat-          GitLab PAT: 20 base62 characters, 27 for the routable form.
#   xoxb- / xoxp-   Slack: two or three numeric segments and a 24-32 character base62 tail.
#   sk-             API key: an unbroken 32-128 character run, never a chain of lowercase words.
_WORD_CHAIN = re.compile(r"[a-z]+(?:-[a-z]+)+")     # `sk-and-words`: words, not a key
_TOKEN_FORMATS = (
    ("AKIA", re.compile(r"(?<![A-Za-z0-9])AKIA[A-Z0-9]{16}(?![A-Za-z0-9])"), 16, 16, False),
    ("ASIA", re.compile(r"(?<![A-Za-z0-9])ASIA[A-Z0-9]{16}(?![A-Za-z0-9])"), 16, 16, False),
    ("ghp_", re.compile(r"(?<![A-Za-z0-9_])ghp_[A-Za-z0-9]{36,40}(?![A-Za-z0-9_])"), 36, 40, False),
    ("gho_", re.compile(r"(?<![A-Za-z0-9_])gho_[A-Za-z0-9]{36,40}(?![A-Za-z0-9_])"), 36, 40, False),
    ("ghu_", re.compile(r"(?<![A-Za-z0-9_])ghu_[A-Za-z0-9]{36,40}(?![A-Za-z0-9_])"), 36, 40, False),
    ("ghs_", re.compile(r"(?<![A-Za-z0-9_])ghs_[A-Za-z0-9]{36,40}(?![A-Za-z0-9_])"), 36, 40, False),
    ("github_pat_",
     re.compile(r"(?<![A-Za-z0-9_])github_pat_[A-Za-z0-9]{22}_[A-Za-z0-9]{59}(?![A-Za-z0-9_])"),
     82, 82, False),
    ("glpat-", re.compile(r"(?<![A-Za-z0-9])glpat-[A-Za-z0-9_-]{20,27}(?![A-Za-z0-9_-])"),
     20, 27, True),
    ("xoxb-", re.compile(r"(?<![A-Za-z0-9])xoxb-(?:[0-9]{9,13}-){2,3}[A-Za-z0-9]{24,32}"
                         r"(?![A-Za-z0-9])"), 44, 74, True),
    ("xoxp-", re.compile(r"(?<![A-Za-z0-9])xoxp-(?:[0-9]{9,13}-){2,3}[A-Za-z0-9]{24,32}"
                         r"(?![A-Za-z0-9])"), 44, 74, True),
    ("sk-", re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{32,128}(?![A-Za-z0-9_-])"),
     32, 128, True),
)


def _issued_token_in(value: str) -> str | None:
    """The prefix of a real-shaped credential found anywhere in ``value``, or ``None``.

    A match is only a credential when its body sits inside the range that format really issues, and
    (for the formats whose bodies can be hyphenated prose) when it is not a chain of lowercase words:
    `glpat-only-a-document-path` is a name, not a token. TESTOPS-59 AC1/AC4.
    """
    for prefix, pattern, floor, ceiling, words_are_prose in _TOKEN_FORMATS:
        for match in pattern.finditer(value):
            body = match.group(0)[len(prefix):]
            if not floor <= len(body) <= ceiling:
                continue
            if words_are_prose and _WORD_CHAIN.fullmatch(body):
                continue
            return prefix
    return None


# TESTOPS-61 AC3. A prefix is only half a credential: `github_pat_` + 22 characters is the start of
# a fine-grained token, and accepting it as a "truncation" was a green tick on the most recognisable
# prefix the screen knows. A body shorter than the format's floor is a cut-off paste, and the screen
# says so. The line between a fragment and a name is the alphabet, not the length: a body of
# lower-case letters only is a word (`ghp_notes`, `github_pat_docs`), while a run carrying an
# upper-case letter or a digit cannot be an English word and is a fragment of the format's body. Only
# the formats with one unbroken fixed-length body are judged this way; `glpat-`, `xoxb-`, `xoxp-` and
# `sk-` can have word-shaped bodies, so their short bodies remain names.
_TRUNCATION_MIN = 8


def _truncated_token_in(value: str) -> tuple[str, int, int] | None:
    """``(prefix, body length, floor)`` for a real prefix cut off below its format, or ``None``.

    TESTOPS-61 AC3: never a silent accept. The caller names the prefix and the two lengths and never
    the value, because a refusal must not become a way to print a paste.
    """
    for prefix, _pattern, floor, _ceiling, words_are_prose in _TOKEN_FORMATS:
        if words_are_prose:
            continue                                  # word-shaped bodies: a short one is a name
        for match in re.finditer(rf"(?<![A-Za-z0-9_]){re.escape(prefix)}([A-Za-z0-9_]*)", value):
            body = match.group(1)
            if not _TRUNCATION_MIN <= len(body) < floor:
                continue                              # a word, a fragment too short to judge, or a
                                                          # body at its real length (rules 4 and 6)
            if body.islower() or "_" in body:
                continue                              # `github_pat_docs`, `ghp_only_a_doc_path`
            return prefix, len(body), floor
    return None


# TESTOPS-59 AC3, TESTOPS-61 AC1/AC2. The words that turn a compound into *a particular credential*
# rather than the name of a kind: `my-password`, `acme-their-password` and `an-api-token` are
# instances, while `session-token` and `vault-token` are kinds of token. The class is closed -
# determiners and possessives are a finite grammatical class, not a vocabulary of technical terms -
# and it is position-free: a possessive in the middle names an instance exactly as plainly as one at
# the front, which is what TESTOPS-61 AC1 fixes.
#
# The one thing a determiner cannot do is make a *statement* into a noun phrase. `this-is-not-a-password`
# opens with a determiner and ends with a credential word, but `is` is a finite verb and the credential
# word is its complement: the name is a predication *about* a password, not a label for one, so the
# determiner belongs to the sentence. TESTOPS-62 narrows that to what it says: a verb or a negator
# *anywhere* is not a statement - the parts must be a predication, with a subject before the predicate
# head and the credential word as the complement after it. `my-password-is-here` and
# `this-token-was-leaked` make the credential word the verb's subject, so they label an instance and
# are refused; `has-my-token` and `never-the-api-token` are fragments with no subject before the head.
# A true negator reads as an elided copula, which is why `xox-not-a-slack-token` - a subject (`xox`),
# a negator and the credential word as its complement - remains a denial and not a label, while a
# negator with nothing before it is a fragment. `vault-token` is accepted because, like
# `session-token`, it is a compound noun whose head names a kind of token and which carries no
# determiner at all (AC4: a grammatical reason, not an appeal to any vendor's vocabulary).
_DETERMINERS = frozenset({
    "my", "your", "our", "their", "his", "her", "its", "the", "a", "an", "this", "that", "these",
    "those", "some", "any", "another", "every", "each", "no",
})
# The finite verbs English supplies as copulas and auxiliaries: the closed class that makes a group of
# words a clause. A finite verb is necessary for a predication but not sufficient - the words before it
# must be a subject, and the credential word must be its complement (see `_is_predication`).
_FINITE_VERBS = frozenset({
    "am", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did",
    "will", "would", "shall", "should", "can", "could", "may", "might", "must",
})
# A true negator makes a phrase a *denial* rather than a label when it has a subject before it and the
# credential word as its complement: `xox-not-a-slack-token` is "xox [is] not a Slack token", a
# predication with the copula elided. A negator with nothing before it (`never-the-api-token`) is a
# fragment and states nothing. TESTOPS-62 AC3: `no` is also a determiner, and the precedence is stated
# here - it is read as a determiner, never as a predicate head. It therefore takes a name into the
# instance test (`acme-no-password`) and can never excuse it.
_NEGATORS = frozenset({"not", "never", "no"})
# The heads that can carry a predication. `no` is deliberately absent: a word in two classes must not
# satisfy both tests (TESTOPS-62 AC3).
_PREDICATE_HEADS = (_FINITE_VERBS | _NEGATORS) - _DETERMINERS
_CREDENTIAL_WORD = re.compile(rf"(?i)^{_INSTANCE_WORDS}$")
# TESTOPS-65 AC1: a context word is a credential head only in a credential position (see the
# vocabulary note above), which is what keeps `pass-through`, `cert-store` and `cookie-policy` names.
_CONTEXT_WORD = re.compile(rf"(?i)^{_CONTEXT_WORDS}$")
# TESTOPS-63. The one word whose reading is decided by qualification (see the vocabulary note above):
# `key`/`keys` is a credential head only when a part or a determiner stands before it in the name.
_KEY_WORD = re.compile(r"(?i)^keys?$")
# TESTOPS-65 AC3. The modifiers that make a *merged* `key` name a credential word, the same way a
# preceding hyphenated part does: `apikey`, `apikeys`, `sshkeys`, `accesskey`. This is a closed class
# of qualifiers, not a list of credential nouns - it exists so the merged, camel-case and
# separator-joined spellings of the same name reach the same branch. A merged word whose prefix is
# not one of these (`monkey`, `hotkey`, `turnkey`) is a different word and stays a name.
_KEY_QUALIFIERS = frozenset({
    "api", "ssh", "access", "private", "secret", "signing", "encryption", "auth", "deploy", "master",
    "client", "public", "gpg", "hmac", "session", "storage", "subscription", "license", "webhook",
})


def _split_merged(part: str) -> list[str]:
    """Split a merged credential name into qualifier and head (`apikey` -> `api`, `key`).

    TESTOPS-65 AC3: the same name written merged (`apikey`), camel-cased (`apiKey`), underscored
    (`api_key`) or hyphenated (`api-key`) must be read by the same rule. The separators are undone by
    the split in :func:`_credential_parts`; this undoes the merge, and only for a prefix that is a
    known qualifier, so `monkey` and `hotkey` stay single words.
    """
    for head in ("keys", "key"):
        lowered = part.lower()
        if lowered.endswith(head) and len(lowered) > len(head):
            prefix = lowered[:-len(head)]
            if prefix in _KEY_QUALIFIERS:
                cut = len(part) - len(head)
                return [part[:cut], part[cut:]]
    return [part]


def _credential_parts(name: str) -> list[str]:
    """The parts any rule reads a name by: separators and merges undone.

    Called before the rule sees the name, so qualification is a property of the name rather than of
    its spelling (TESTOPS-65 AC3). `api_key`, `api-key`, `apiKey` and `apikey` all arrive as
    `["api", "key"]`, and `the-signing-key` as `["the", "signing", "key"]`.

    TESTOPS-68 AC2: a capital letter is not a word boundary. The earlier version split camel
    boundaries first, which invented a bare `Key` out of `usbKey` (`["usb", "Key"]`) and refused
    `the-usbKey` while accepting `the-usbkey` - the verdict decided by capitalisation. A camel
    segment is one segment of a longer word, not a bare credential word, exactly as the merged
    spelling of the same word is (`usbkey`, `hotkey`). The only split inside a word is the one a
    *known qualifier* licenses (`apiKey`, `sshKey`, `privateKey`), which is the same closed class
    that already decides `apikey`; qualification is read from the letters, never from the case.
    """
    parts: list[str] = []
    for raw in re.split(r"[^A-Za-z0-9]+", name):
        if not raw:
            continue
        parts.extend(_split_merged(raw))
    return parts
# The same qualification in the pair branch: a pair whose *name* is a determiner plus `key`
# (`my-key=hunter2`, `the_keys: abc`) is a credential name, while `sort_keys=True` - the name a
# setting really has - is not. Only a hyphen or an underscore joins the two: with a space allowed,
# the ordinary sentence "the key: it is in the vault" would be read as a pair.
_DETERMINER_KEY_PAIR = re.compile(
    rf"(?i)(?<![A-Za-z0-9])(?:{'|'.join(sorted(_DETERMINERS))})[_-]keys?[ \t]*[:=][ \t]*[^\s,;]")


def _is_predication(lowered: list[str], credential_index: int) -> bool:
    """Whether the parts are a predication whose complement is the credential word (TESTOPS-62).

    A subject - at least one part before the head that is not itself a verb or negator - sits before
    a predicate head, and the credential word is the final part after it. `this-is-not-a-password`:
    subject `this`, head `is`, complement `a-password`. `xox-not-a-slack-token`: subject `xox`, head
    `not` (copula elided), complement `a-slack-token`. `my-password-is-here` fails because the
    credential word is before the head (it is the subject); `has-my-token` fails because nothing
    precedes the head; `x-not-a-token-but-abcdef` fails because the credential word is not the final
    complement.

    `no` is not a head here (see `_PREDICATE_HEADS`): it is a determiner first, so it can never
    supply the excuse its other class would (AC3).
    """
    if credential_index != len(lowered) - 1:
        return False                                  # the credential word is not the complement
    for index, part in enumerate(lowered):
        if part not in _PREDICATE_HEADS:
            continue
        subject = [word for word in lowered[:index]
                   if word not in _FINITE_VERBS and word not in _NEGATORS]
        if subject and index < credential_index:
            return True
    return False


def _names_a_credential(parts: list[str]) -> bool:
    """Whether a short identifier, split into its parts, names a *particular* credential.

    TESTOPS-59 AC3 replaced the TESTOPS-56 "last part and at most three parts" rule, which refused
    `session-token` while accepting `passwords-list` and would have refused `password-list` only
    because its word match was singular. TESTOPS-61 AC1/AC2 closed the two ends that rule left open:
    it read the first part and the last part, and nothing in between. TESTOPS-62 closes the excuse
    TESTOPS-61 left open: a verb or a negator anywhere in the name is not a statement, so several
    instance labels and fragments were accepted as if they said something.

    The rule, stated once:

      * a bare credential word (`password`, `tokens`) names the thing itself - refused;
      * a name that carries no determiner or possessive (`session-token`, `vault-token`) is a
        compound *noun* naming a kind of thing, and is accepted;
      * a name that carries a determiner names a particular instance - refused - unless the parts are
        a **predication about the credential word**: a subject before a predicate head (a finite verb,
        or a true negator reading as an elided copula), with the credential word as the complement
        after the head and the last part of the name. `this-is-not-a-password` and
        `xox-not-a-slack-token` state something about a password/token and are accepted;
      * `my-password-is-here`, `this-token-was-leaked` and `my-secret-has-value` are not predications
        *about* the credential word - it is the subject of the verb - so the name labels an instance
        and is refused;
      * `has-my-token`, `is-my-password`, `never-the-api-token`, `no-password-yet` and
        `x-not-a-token-but-abcdef` are fragments, not clauses (no subject before the head, or no
        head at all, or the credential word is not the complement), and are refused;
      * every other determiner-bearing name whose credential word is not the final part is a compound
        noun (`password-manager`, `token-bucket-limiter`, `the-token-service`) and is accepted.

    Precedence (TESTOPS-62 AC3), stated once and pinned in the tests: `no` belongs to both the
    determiner class and the negator class, and is read **only as a determiner**. It therefore takes
    a name into the instance test and can never excuse it as a predicate head - `acme-no-password`
    and `no-password-yet` are labels, not denials. A negator only excuses when it is a true negator
    with a subject before it and the credential word as its complement.

    Singular and plural are matched alike, so `password-list` and `passwords-list` are decided
    together: both are the name of a collection, and both are accepted.

    Neither list is a vocabulary of technical terms: determiners, finite verbs and negators are
    closed grammatical classes, and no entry names a credential, a product or a vendor. `session-token`
    and `vault-token` are accepted by the same reason, that the compound names a kind of token and
    carries no determiner.

    Old-style labels that carry no determiner (`session-token`, `vault-token`) are compound nouns
    naming a kind of thing and are accepted. TESTOPS-63 adds `key`, the one credential word whose
    reading depends on qualification: `my-key`, `their-key`, `the-signing-key` and
    `the-api-key-is-xyz` are screened by the same branches, with the same reason, as `my-password`.
    In the other direction, `primary-key`, `foreign-key`, `key-metrics`, `sorting-keys` and
    `key-value-store` name a field, a measurement or a collection and are accepted; and `keyboard`,
    `keynote`, `keycloak`, `keystore` and `monkey` are different words entirely, so no rule here
    can see them. `key` is a credential word only in this rule, for the reason given at the
    vocabulary itself: a pair name and a settings field name are honestly `sort_keys=` and
    `board_keys`.

    TESTOPS-65 makes the rule read the *normalised* name (``_credential_parts``), so qualification is
    a property of the name rather than of the hyphen: `apikey`, `apiKey`, `api_key` and `api-key`
    arrive as `api` + `key` and are decided together, alone (a kind name, accepted) and with a
    determiner (an instance, refused). The words AC1 adds - `passphrase`, `cred`/`creds`, `pass`,
    `bearer`, `jwt`, `cert`, `salt`, `seed`, `otp`/`totp`, `dsn`, `webhook`, `cookie` - join the head
    set as *context* words: they are read where they stand in a credential position and left alone
    where they name a kind of thing (`pass-through`, `cert-store`, `jwt-decode`, `cookie-policy`).
    A compound that *is* the credential rather than a kind of it (`seed-phrase`, `pin-number`,
    `totp-seed`, `connection-string`, `session-id`, `cookie-value`) is an instance on its own.
    The list is knowingly incomplete: an unlisted word is an unscreened name, and the value-shape
    rules are what catch a credential whose name nobody has thought of yet.

    Residual risk, stated rather than hidden: a compound whose head is a credential word but which
    carries no determiner (`prod-db-password`) is accepted as a type name, and a name whose only
    determiner is inside a predication about the credential word (`this-is-my-password`) is accepted
    because it states something rather than labelling a credential. Both are labels or jokes; a
    pasted credential is caught by rules 1, 2, 4 and 5 wherever it sits in the value.
    """
    lowered = [part.lower() for part in parts]
    if not lowered:
        return False
    # TESTOPS-65: a compound whose own name is the credential - `seed-phrase`, `pin-number`,
    # `totp-seed`, `connection-string`, `session-id`, `cookie-value` - names the thing rather than a
    # kind of thing, so it is an instance with or without a determiner. The tail after a determiner is
    # read the same way, which is what closes `the-seed-phrase` and `the-cookie-value`.
    if _COMPOUND_CREDENTIAL.fullmatch("-".join(lowered)):
        return True
    for index, part in enumerate(lowered):
        if part in _DETERMINERS and _COMPOUND_CREDENTIAL.fullmatch("-".join(lowered[index + 1:])):
            return True
    strong = [i for i, part in enumerate(lowered) if _CREDENTIAL_WORD.fullmatch(part)]
    context = [i for i, part in enumerate(lowered) if _CONTEXT_WORD.fullmatch(part)]
    # TESTOPS-63: `key` is a credential word in this rule only (see the vocabulary note), so it joins
    # the head set here and nowhere else. It is not a credential word on its own - a lone `key` is a
    # configuration slot name, not an instance label - which is why `strong`/`context` decide the
    # one-word case. TESTOPS-65 AC1 adds the context words to the head set in the same way.
    credential = sorted(set(strong + context + [i for i, part in enumerate(lowered)
                                                if _KEY_WORD.fullmatch(part)]))
    if not credential:
        return False
    if len(lowered) == 1:
        return bool(strong or context)                # `password`/`creds` name the thing; `key` is a slot name
    head = credential[-1]
    if not any(part in _DETERMINERS for part in lowered):
        return False                                  # a kind name: `session-token`, `vault-token`
    # TESTOPS-62: a word in the name is not a clause. A verb or negator anywhere makes the name a
    # candidate statement, but it is only a statement when the credential word is its complement;
    # otherwise the parts label an instance and the determiner decides the name.
    if any(part in _FINITE_VERBS or part in _NEGATORS for part in lowered):
        return not _is_predication(lowered, head)
    if head != len(lowered) - 1:
        return False                                  # the head is a later noun: a compound noun
    return True                                       # a determiner and a credential head: an instance


def _field_names_a_credential(name: str) -> bool:
    """Whether a settings **field** name is named like a credential (TESTOPS-65).

    A field name is a slot name rather than a label, which is why `key` is not a credential word here
    (`board_keys` and `jira_key` are fields this product really has) and why the membership vocabulary
    keeps deciding the strong words by search: `api_key` and `db_password` are refused unchanged.
    The words this ticket adds have honest lives as field names (`certs-dir`, `pass-through`,
    `jwt-library`, `cookie-banner`, `credentials-provider`), so they are refused only where they are
    the *last* part - `cert`, `seed`, `creds` - and a key qualified by a known modifier (`api_key`)
    is refused while one qualified by an ordinary noun (`board_keys`, `sorting_keys`) is not.
    """
    if _CREDENTIAL_NAME_ALONE.search(name):
        return True
    parts = _credential_parts(name)
    if not parts:
        return False
    if _names_a_credential(parts):
        return True
    if _CONTEXT_WORD.fullmatch(parts[-1]):
        return True
    return (len(parts) > 1 and bool(_KEY_WORD.fullmatch(parts[-1]))
            and parts[-2].lower() in _KEY_QUALIFIERS)



# What divides a structured key into readable parts. `COTW-PROJ-KEY-0123456789-ABCDEFG` and a UUID
# are configuration written as short parts; a token is one long unbroken run. Judging the longest run
# rather than the whole value is what lets a hyphenated key through while a `ghp_...` token stays out.
_SEPARATORS = re.compile(r"[/\\\-._:]")

_LOG = logging.getLogger(__name__)


class ConfigError(ValueError):
    """A configuration the store or the model cannot express, in words a user can act on."""


class UnknownProject(ConfigError):
    """No project with that slug. The message names the slug and the projects that do exist."""

    def __init__(self, slug: str, known: list[str]) -> None:
        self.slug = slug
        known_text = ", ".join(known) if known else "none"
        super().__init__(f"unknown project {slug!r}; this store holds: {known_text}. "
                         f"Add it on the configuration page (/config) or as a row in the project "
                         f"table - no code change is needed.")


# ---------------------------------------------------------------- credentials (AC5)

def _entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = {ch: text.count(ch) for ch in set(text)}
    return -sum((n / len(text)) * math.log2(n / len(text)) for n in counts.values())


def _looks_like_secret(value: str) -> str | None:
    """Why ``value`` reads as a credential, or ``None`` when it reads as configuration.

    The reason never contains the value: refusing a secret must not become the way it is printed.
    Names and prefixes may be named, because they are what the reader has to change.

    The value is scanned, not prefix-matched: a real token, pair, JWT or PEM block anywhere in the
    string is a credential (TESTOPS-59 AC1). The vocabulary is knowingly incomplete (TESTOPS-65 AC5):
    a credential *name* built from a word nobody listed is unscreened. TESTOPS-68 AC4 states where
    the floor actually is: shape-only rules (PEM, JWT, known issued prefixes, the base64/entropy
    floor, and an inline password in a URL) need nobody to have thought of the word, while the pair,
    instance and `key`-qualification rules depend on the vocabulary and catch only what it names.
    Residual risk, stated rather than implied: an
    unrecognised format is not detected at all; a covered prefix whose body is too short to tell a
    word from a fragment (below eight characters, or all lower-case letters) is a name and is
    accepted (see ``_TOKEN_FORMATS`` and ``_truncated_token_in``); a compound label whose head is a
    credential word but which carries no determiner (``prod-db-password``) is accepted as a type
    name; and the base64/entropy floors are thresholds, not proofs. TESTOPS-56's note claimed every
    pasted credential met the rules - that was false for a sentence-wrapped token, which is the leak
    TESTOPS-59 fixed.
    """
    plain = (value or "").strip()
    if not plain:
        return None
    # 0. TESTOPS-68 AC3: a password written into a URL (`scheme://user:secret@host`) is a shape, not
    #    a vocabulary lookup. It is refused anywhere in the value, with or without a credential word
    #    beside it, which is what makes this a floor: `postgres://app:secret@db/qa` on its own is
    #    caught here, before any rule asks whether somebody listed `dsn`. The reason names the shape
    #    and never the secret.
    if _INLINE_PASSWORD.search(plain):
        return ("it embeds a password in a URL: the 'scheme://user:password@host' form carries the "
                "credential inside the address")
    # 1. A pasted `name=value` (or `name: value`) pair: the shape a credential arrives in. The reason
    #    names the field, never the value. TESTOPS-65 AC4: a key-family name whose value is a slot
    #    reference (`${API_KEY}`, `from-env`, `os.environ[...]`) names where the credential lives and
    #    is configuration, while a literal after the same name is the credential itself - which is
    #    also why `apikey`, `api_key`, `api-key` and `apiKey` cannot disagree here.
    for pair in _CREDENTIAL_PAIR.finditer(plain):
        if _KEY_FAMILY.match(pair.group(1)) and _is_reference(pair.group("value")):
            continue
        return (f"it reads as a credential: the name {pair.group(1)!r} is followed by '=' or ':' "
                f"and a value")
    # TESTOPS-65 AC1: a context word with a value is decided by the shape of that value too -
    # `cert=/etc/ssl/ca.pem` and `salt=$SALT` are references, `salt=abc123` is the material.
    for pair in _CONTEXT_PAIR.finditer(plain):
        if _is_reference(pair.group("value")):
            continue
        return (f"it reads as a credential: the name {pair.group(1)!r} is followed by '=' or ':' "
                f"and a value")
    # TESTOPS-65 AC4: a *bare* `key`/`keys` has no qualifier to make it a credential word, so the
    # value decides the name. `key = hunter2` and `key=hunter2` are refused; `key = ${API_KEY}` and
    # `key = from-env` are accepted, because they name a slot rather than carrying a secret.
    # `sort_keys=True` never reaches this rule: the lookbehind excludes `_` and `-`.
    bare = _BARE_KEY_PAIR.search(plain)
    if bare and not _is_reference(bare.group("value")):
        return ("it reads as a credential: a bare `key` is followed by '=' or ':' and a value that "
                "is not a slot reference")
    # TESTOPS-63: the same shape for the one word the pair vocabulary cannot carry alone - a `key`
    # named with a determiner (`my-key=hunter2`). `sort_keys=True` and `board_keys` stay configuration.
    if _DETERMINER_KEY_PAIR.search(plain):
        return ("it reads as a credential: a key named with a determiner/possessive is followed by "
                "'=' or ':' and a value")
    # 2. Issued-token shapes, searched anywhere in the value (TESTOPS-59 AC1): a PEM block, a JWT
    #    and a complete authorization header pasted into a longer string are still secrets.
    if _PEM_BLOCK.search(plain):
        return "it contains a PEM private-key block ('-----BEGIN ... PRIVATE KEY-----')"
    if _JWT.search(plain):
        return ("it contains a JSON Web Token: three dot-separated segments beginning 'eyJ', the "
                "header of every JWT")
    if _AUTH_SCHEME.match(plain):
        return ("it is an authorization header: a scheme ('Bearer', 'Basic', 'Digest' or 'Token') "
                "and one unbroken value")
    # 3. One short unbroken identifier naming a credential instance: `my-password`,
    #    `acme-their-password`, `an-api-token` - a determiner or possessive in any position, unless
    #    the parts are a predication about the credential word (`this-is-not-a-password`, TESTOPS-62
    #    AC1: subject, predicate head, credential word as complement). Whitespace means
    #    prose is not a token, a repository coordinate or path (a '/') is a coordinate, and a longer
    #    snake_cased label (`test_password_reset_flow`) is a name, not a secret. TESTOPS-59 AC3 states
    #    the rule itself in :func:`_names_a_credential`. The pair, PEM, JWT and prefix rules catch a
    #    real credential in any other form.
    if not any(ch.isspace() for ch in plain) and "/" not in plain:
        parts = _credential_parts(plain)
        if _names_a_credential(parts):
            return "it is a short identifier naming a credential"
    # 4. A known credential prefix with its format's real body, anywhere in the value (TESTOPS-59
    #    AC1/AC4): `the key is ghp_...` is a token pasted in a sentence, while `ghp_notes` (below the
    #    floor) and `AKIA-reviews-team` (not the body) are names. Before the entropy floors, because
    #    the shortest AWS key ID is 20 characters.
    issued = _issued_token_in(plain)
    if issued:
        return f"it contains {issued!r}, the prefix of a known credential format"
    # 5. A known credential prefix with a body too short for its format (TESTOPS-61 AC3): the start
    #    of a real token, cut off. Accepting it as a "truncation" was a silent green tick on the
    #    most recognisable prefix on the board, so it is refused and the reason says why.
    truncated = _truncated_token_in(plain)
    if truncated:
        prefix, body_length, floor = truncated
        return (f"it begins with {prefix!r}, a known credential prefix, but carries only "
                f"{body_length} characters after it - too short for that format ({floor}), so it "
                f"reads as a cut-off paste rather than a name")
    # A long blob of one alphabet is a token shape, not a host, a path or a repository. URLs and
    # paths are exempt: they are what settings are for.
    if len(plain) >= _BLOB_MIN and not any(ch.isspace() for ch in plain) \
            and not plain.startswith(("http://", "https://")):
        # AC1: before the separator exemption, because base64 always contains '/' and often '+' or
        # '='. A blob that is entirely the base64 alphabet and carries encoded-secret entropy is
        # refused even though it looks like a path.
        if _BASE64.fullmatch(plain) and _entropy(plain) >= _BASE64_ENTROPY:
            return (f"it looks like a base64-encoded secret ({len(plain)} characters of the "
                    f"base64 alphabet)")
        # AC2: a structured key is written in short parts; a token is one long unbroken run. Only
        # the longest run is judged, so a UUID or COTW-PROJ-KEY-... is configuration and ghp_... is
        # still a token.
        longest = max(len(part) for part in _SEPARATORS.split(plain))
        if longest >= 32 and (re.fullmatch(r"[A-Fa-f0-9]+", plain)
                              or (_entropy(plain) >= 3.5 and len(set(plain)) >= 12)):
            return "it looks like a high-entropy secret (32+ characters, no separators)"
    return None


def validate_settings(settings: dict) -> dict:
    """Refuse a credential in service settings, saying which field and why (AC5).

    Settings are written to the store, printed on the configuration page and copied into backups. A
    token there is a token in every one of them. Credentials resolve from the environment when a
    connector is called; the row holds the host, the key or the path, never the secret. The value is
    never echoed in the error - refusing a secret must not be another way to print it.
    """
    if not isinstance(settings, dict):
        raise ConfigError("settings must be a mapping of field names to values")
    for key, value in settings.items():
        if not isinstance(key, str) or not key.strip():
            raise ConfigError("every settings field needs a name")
        if _field_names_a_credential(key.strip()):
            # AC3: the field name and the reason are logged; the value never is. A refusal that
            # printed the secret would be a second way to leak it.
            _LOG.warning("settings field %r refused: the field name reads as a credential", key)
            raise ConfigError(
                f"settings field {key!r} is named like a credential. Settings hold hosts, "
                f"repository coordinates, board keys and paths only; a secret resolves from the "
                f"environment at call time, so it must not be stored here.")
        if isinstance(value, (dict, list, tuple)):
            raise ConfigError(f"settings field {key!r} must be a single value, not a nested "
                              f"{type(value).__name__}")
        # TESTOPS-65 AC4: the field that is itself a key slot (`key`, `keys`, `apikey`, `api_key`)
        # holds the secret or a reference to it - `{"key": "hunter2"}` is the hole the T63 review left
        # open, while `{"key": "${API_KEY}"}` and `{"key": "from-env"}` name where the secret lives.
        # The JSON/HTTP form whitelists field names, so this closes the rule, not just that route.
        if _KEY_FAMILY.match(key.strip()) and not _is_reference(str(value).strip()):
            _LOG.warning("settings field %r refused: a key slot holding a literal value", key)
            raise ConfigError(
                f"settings field {key!r} was refused: a field named as a key holds the secret "
                f"itself, and a literal value there would leak through the store, the page and "
                f"every backup. Name the slot instead (an environment reference such as "
                f"'${{API_KEY}}' or 'os.environ[NAME]'), or rename the field if it holds a key "
                f"such as a board key.")
        reason = _looks_like_secret(str(value))
        if reason:
            _LOG.warning("settings field %r refused: %s", key, reason)
            raise ConfigError(
                f"settings field {key!r} was refused: {reason}. Settings hold hosts, repository "
                f"coordinates, board keys and paths only - never a token, password or key. A "
                f"credential written here would leak through the store, the page and every backup. "
                f"Resolve it from the environment when the connector runs.")
    return dict(settings)


def refuse_credential_in(value: str, what: str) -> None:
    """The one screen for a human-entered name, applied at the store boundary (TESTOPS-51 AC1).

    A name is a label a reader sees, and it is stored and printed exactly like a settings value -
    so it is screened by the same rules, through the same call. Every create/edit path calls this
    rather than repeating the detection, which is what keeps a field added tomorrow covered.
    """
    reason = _looks_like_secret(value)
    if reason is None:
        return
    _LOG.warning("%s refused: %s", what, reason)
    raise ConfigError(
        f"the {what} was refused: {reason}. A {what} is a label a reader sees, and it is written "
        f"to the store and printed on the page - a credential written there would leak through "
        f"both. Secrets resolve from the environment when the connector runs, so a credential "
        f"must not be entered here.")


# ---------------------------------------------------------------- projects

@dataclass(frozen=True)
class Service:
    id: int
    project: str
    type: str
    role: str
    name: str
    settings: dict
    last_state: str | None = None
    last_reason: str | None = None
    last_consulted_at: str | None = None

    def record(self) -> dict:
        """The service as a snapshot records it: no settings, so no host leaks into a run page."""
        return {"id": self.id, "name": self.name, "type": self.type, "role": self.role,
                "state": self.last_state or "", "reason": self.last_reason or ""}


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _rows(conn, sql: str, args: tuple = ()) -> list[dict]:
    return [dict(row) for row in conn.execute(sql, args)]


def list_projects(conn) -> list[dict]:
    return _rows(conn, "SELECT slug, name, created_at FROM project ORDER BY slug")


def get_project(conn, slug: str) -> dict | None:
    rows = _rows(conn, "SELECT slug, name, created_at FROM project WHERE slug = ?", (slug,))
    return rows[0] if rows else None


def require_project(conn, slug: str) -> dict:
    """The project row, or :class:`UnknownProject` naming the slug and the store's projects."""
    project = get_project(conn, slug)
    if project is None:
        raise UnknownProject(slug, [row["slug"] for row in list_projects(conn)])
    return project


def add_project(conn, slug: str, name: str) -> dict:
    """Add a project. A slug is an identity: it may not be blank, re-used or decorative."""
    slug = (slug or "").strip()
    name = (name or "").strip() or slug
    # TESTOPS-51: the screen runs before the format checks, so a credential-shaped value is refused
    # with a reason that does not repeat it, whichever field it was typed into.
    refuse_credential_in(slug, "project slug")
    refuse_credential_in(name, "project name")
    if not _SLUG.fullmatch(slug):
        raise ConfigError(f"project slug {slug!r} must be lower-case letters, digits and hyphens, "
                          f"starting with a letter or digit (for example: cotw)")
    if get_project(conn, slug) is not None:
        raise ConfigError(f"a project {slug!r} already exists; choose another slug")
    conn.execute("INSERT INTO project (slug, name, created_at) VALUES (?,?,?)",
                 (slug, name, _now()))
    conn.commit()
    return {"slug": slug, "name": name}


def evidence_counts(conn, slug: str) -> dict:
    """How much evidence a project holds: runs, snapshots and cases, counted, not assumed.

    The three are counted separately because a reader asked to delete a project needs to know what
    would be lost, and "it has evidence" is not a count.
    """
    return {
        "runs": int(conn.execute("SELECT COUNT(*) FROM run WHERE project = ?", (slug,)).fetchone()[0]),
        "snapshots": int(conn.execute("SELECT COUNT(*) FROM snapshot WHERE project = ?",
                                      (slug,)).fetchone()[0]),
        "cases": int(conn.execute("SELECT COUNT(*) FROM case_ WHERE project = ?",
                                  (slug,)).fetchone()[0]),
    }


def remove_project(conn, slug: str) -> None:
    """Remove a project with its services, if it holds no evidence (TESTOPS-51 AC6).

    Evidence is immutable: a configuration action removes configuration. A project that still holds
    runs, snapshots or cases is refused, with the counts named, so nobody deletes the store's memory
    from a page that says "configuration". A project with no evidence - the empty
    ``contract-audit-*`` rows the contract suite leaves - is removed with its services.
    """
    require_project(conn, slug)
    counts = evidence_counts(conn, slug)
    if any(counts.values()):
        held = ", ".join(f"{n} {name}" for name, n in counts.items())
        _LOG.warning("project %r not deleted: it holds %s", slug, held)
        raise ConfigError(
            f"project {slug!r} was not deleted: it holds {held}. Runs, snapshots and cases are "
            f"evidence and are never deleted by a configuration action; only a project with no "
            f"evidence can be removed from this page.")
    conn.execute("DELETE FROM project WHERE slug = ?", (slug,))
    conn.commit()


# ---------------------------------------------------------------- services

def _service(row: dict) -> Service:
    try:
        settings = json.loads(row.get("settings") or "{}")
    except json.JSONDecodeError as exc:
        raise ConfigError(f"service {row.get('id')} holds unreadable settings: {row.get('settings')!r}"
                          ) from exc
    return Service(id=row["id"], project=row["project"], type=row["type"], role=row["role"],
                   name=row["name"], settings=settings if isinstance(settings, dict) else {},
                   last_state=row.get("last_state"), last_reason=row.get("last_reason"),
                   last_consulted_at=row.get("last_consulted_at"))


def list_services(conn, slug: str) -> list[Service]:
    return [_service(row) for row in
            _rows(conn, "SELECT * FROM service WHERE project = ? ORDER BY type, role, id", (slug,))]


def get_service(conn, service_id: int) -> Service | None:
    rows = _rows(conn, "SELECT * FROM service WHERE id = ?", (service_id,))
    return _service(rows[0]) if rows else None


def _check_service(conn, project: str, kind: str, role: str, name: str, settings: dict) -> None:
    if get_project(conn, project) is None:
        raise ConfigError(f"no project {project!r}; add the project before adding services to it")
    if kind not in TYPES:
        raise ConfigError(f"unknown service type {kind!r}; expected one of {', '.join(TYPES)}")
    if kind == "git_repo" and role not in ROLES:
        raise ConfigError("a git repository service is either the product or the tests: "
                          "role must be 'product' or 'test'")
    if kind != "git_repo" and role:
        raise ConfigError(f"a {kind} service has no role; leave it empty")
    if not (name or "").strip():
        raise ConfigError("a service needs a name a reader can see")
    # TESTOPS-51: the name is a user-supplied value like any other. It was the field the blind
    # author used, and the only reason it was accepted is that this screen was never applied here.
    refuse_credential_in(name, "service name")
    validate_settings(settings)
    if kind == "git_repo":
        repo = str(settings.get("repo") or "")
        if not _REPO.fullmatch(repo):
            raise ConfigError(f"a git repository service needs settings.repo as 'owner/name', "
                              f"found {repo!r}")
    if kind == "jira_board" and not str(settings.get("board") or "").strip():
        raise ConfigError("a Jira board service needs settings.board (the board or project key)")
    if kind == "ado_pipeline":
        if not str(settings.get("org") or "").strip():
            raise ConfigError("an Azure DevOps service needs settings.org")
        pipeline_id = settings.get("pipeline_id")
        if pipeline_id is not None and not isinstance(pipeline_id, int):
            raise ConfigError("settings.pipeline_id must be a number when present")


def add_service(conn, project: str, kind: str, role: str, name: str, settings: dict) -> Service:
    settings = dict(settings or {})
    _check_service(conn, project, kind, role, name, settings)
    cur = conn.execute(
        "INSERT INTO service (project, type, role, name, settings, created_at) VALUES (?,?,?,?,?,?)",
        (project, kind, role, name.strip(), json.dumps(settings, sort_keys=True), _now()))
    conn.commit()
    return get_service(conn, int(cur.lastrowid))  # type: ignore[arg-type]


def update_service(conn, service_id: int, *, kind: str, role: str, name: str,
                   settings: dict) -> Service:
    existing = get_service(conn, service_id)
    if existing is None:
        raise ConfigError(f"no service {service_id}")
    settings = dict(settings or {})
    _check_service(conn, existing.project, kind, role, name, settings)
    conn.execute("UPDATE service SET type=?, role=?, name=?, settings=? WHERE id=?",
                 (kind, role, name.strip(), json.dumps(settings, sort_keys=True), service_id))
    conn.commit()
    return get_service(conn, service_id)  # type: ignore[return-value]


def remove_service(conn, service_id: int) -> None:
    conn.execute("DELETE FROM service WHERE id = ?", (service_id,))
    conn.commit()


# ---------------------------------------------------------------- the project as the pipeline sees it

@dataclass(frozen=True)
class ProjectAssessment:
    """What the store's own services can say about a project, before any connector is called."""
    slug: str
    state: str                      # available | not_assessable
    reason: str
    services: tuple[dict, ...] = field(default_factory=tuple)

    @property
    def assessable(self) -> bool:
        return self.state != NOT_ASSESSABLE

    def record(self) -> list[dict]:
        return [dict(state) for state in self.services]


def _repo_of(service: Service) -> Repo | None:
    text = str(service.settings.get("repo") or "")
    if "/" not in text:
        return None
    owner, name = text.split("/", 1)
    return Repo(owner, name)


def assess_services(conn, slug: str) -> ProjectAssessment:
    """Per-service state for a project, with an absent service named rather than omitted (AC4/AC7).

    A missing product repository is the case AC7 exists for: the project can still be listed, its
    test repository read, and the page must say the product code could not be assessed. A project
    with no Jira board says so as a *service* that is absent, not as silence.
    """
    rows = list_services(conn, slug)
    product = next((s for s in rows if s.type == "git_repo" and s.role == "product"), None)
    test = next((s for s in rows if s.type == "git_repo" and s.role == "test"), None)

    states: list[dict] = []
    missing: list[str] = []
    for role, found, title in (("product", product, "Product repository"),
                               ("test", test, "Test repository")):
        if found is not None:
            states.append({"id": found.id, "name": found.name, "type": "git_repo", "role": role,
                           "state": AVAILABLE, "reason": ""})
            continue
        reason = (f"no {'product' if role == 'product' else 'test'} git repository is configured "
                  f"for this project, so nothing can be said about it - which is not the same as "
                  f"finding nothing")
        states.append({"id": None, "name": title, "type": "git_repo", "role": role,
                       "state": ABSENT, "reason": reason})
        missing.append(reason)

    jira = next((s for s in rows if s.type == "jira_board"), None)
    if jira is None:
        states.append({"id": None, "name": "Jira board", "type": "jira_board", "role": "",
                       "state": ABSENT,
                       "reason": "no Jira board is configured for this project"})
    else:
        # No connector in this ticket. The reason says both facts: this build lacks the connector,
        # and at Quilter the source is blocked by policy. Neither is a zero.
        states.append({"id": jira.id, "name": jira.name, "type": "jira_board", "role": "",
                       "state": POLICY,
                       "reason": ("no Jira connector is installed in this build, and Quilter "
                                  "policy forbids issuing a personal access token because of "
                                  "breach risk")})
    pipelines = [s for s in rows if s.type == "ado_pipeline"]
    if not pipelines:
        states.append({"id": None, "name": "Azure DevOps pipeline", "type": "ado_pipeline",
                       "role": "", "state": ABSENT,
                       "reason": "no Azure DevOps pipeline is configured for this project"})
    for pipeline in pipelines:
        states.append({"id": pipeline.id, "name": pipeline.name, "type": "ado_pipeline",
                       "role": "", "state": POLICY,
                       "reason": ("no connector for Azure DevOps is installed in this build, and "
                                  "Quilter policy forbids a personal access token")})

    if missing:
        return ProjectAssessment(slug, NOT_ASSESSABLE, " ".join(missing), tuple(states))
    return ProjectAssessment(slug, AVAILABLE, "", tuple(states))


def project_from_store(conn, slug: str) -> Project:
    """Assemble the pipeline's :class:`Project` from a store project and its services (AC8).

    ``service_states`` is what the services said when the project was resolved, so the run can write
    that record into its snapshot instead of re-deriving it at render time. A project with no
    product repository is returned with ``product=None`` - not refused and not defaulted to the test
    repository - so the pipeline reports ``not_assessable`` rather than collecting the wrong arm.
    """
    if get_project(conn, slug) is None:
        raise UnknownProject(slug, [row["slug"] for row in list_projects(conn)])
    services = list_services(conn, slug)
    assessment = assess_services(conn, slug)
    product = next((s for s in services if s.type == "git_repo" and s.role == "product"), None)
    test = next((s for s in services if s.type == "git_repo" and s.role == "test"), None)
    if test is None:
        raise ConfigError(f"project {slug!r} has no test git repository service, so there is "
                          f"nothing to analyse. Add one on the configuration page (/config).")
    jira = next((s for s in services if s.type == "jira_board"), None)
    ado = [s for s in services if s.type == "ado_pipeline"]
    return Project(
        key=slug,
        product=_repo_of(product) if product else None,
        test=_repo_of(test),  # type: ignore[arg-type]
        jira_key=str((jira.settings if jira else {}).get("board") or ""),
        ado_org=str(ado[0].settings.get("org") or "") if ado else None,
        ado_project=str(ado[0].settings.get("project") or "") if ado else None,
        ado_pipeline_ids=tuple(int(s.settings["pipeline_id"]) for s in ado
                               if isinstance(s.settings.get("pipeline_id"), int)),
        service_states=tuple(dict(state) for state in assessment.services),
        assessment_state=assessment.state,
        assessment_reason=assessment.reason,
    )


def record_consultation(conn, slug: str, states: list[dict]) -> list[dict]:
    """Write each service's last-consulted state and reason to its own row (AC4).

    Called when a run resolves a project. A state with no service row (the absent product/test
    repository, for instance) has nowhere to live and is not written: inventing a row for it would
    turn "the project does not declare this" into "somebody configured it".
    """
    now = _now()
    written: list[dict] = []
    for state in states:
        service_id = state.get("id")
        if service_id is None:
            written.append(dict(state))
            continue
        conn.execute("UPDATE service SET last_state=?, last_reason=?, last_consulted_at=? "
                     "WHERE id=?", (state.get("state"), state.get("reason"), now, service_id))
        row = dict(state)
        row["at"] = now
        written.append(row)
    conn.commit()
    return written
