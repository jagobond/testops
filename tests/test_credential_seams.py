"""TESTOPS-68: the line boundary, the camel fragment, and the URL floor.

Suite: tests/test_credential_seams.py.

The TESTOPS-65 review found three seams and this file pins the closure of each, in both directions
where a direction exists:

1. the bare-key branch was one newline behind: its lookbehind excluded all whitespace, so a second
   line of configuration ("auth = none\\nkey = hunter2") was read as prose;
2. the camel split ran before the merge split, so `usbKey` arrived as `usb`, `Key` and the fragment
   `Key` was read as a bare credential word - `the-usbKey` refused, `the-usbkey` accepted;
3. the inline-password rule was gated behind a credential word, so a `scheme://user:secret@host`
   value with no credential word beside it was accepted, although AC5 called shape rules the floor.

A verdict must be a function of the words in the value, never of a capital letter or of a word
somebody happened to list.
"""
from __future__ import annotations

import inspect

import pytest

from testops import services

# --------------------------------------------------------------------------- AC1 the line boundary

# A bare key pair that begins a line of configuration is refused: after a newline, after another
# pair, indented, at the start of the value, and after a separator.
LINE_BOUND_PAIRS_REFUSED = [
    "auth = none\nkey = hunter2",
    "repo=x\nkey = hunter2",
    "settings:\n  key: hunter2",
    "  key = hunter2",
    "auth=none; key=hunter2",
    "line one\n\n\nkey=hunter2",
    "repo = owner/name\nkeys = abc123",
]

# The same words in a sentence are prose, not configuration. The space between the determiner and
# `key` is what marks it as part of a sentence; the line start is what marks a settings line.
LINE_BOUND_PROSE_ACCEPTED = [
    "the key: it is in the vault",
    "ask for the key: the platform team has it",
    "the key is in the vault",
    "read the private key exchange note first",
    "auth = none and the key: it is in the vault",
    # the settings this product really has, whose field name merely ends in `keys`
    "sort_keys=True",
    "sorting_keys=asc",
    "primary_key=id",
    "board_keys=DEMO",
]


@pytest.mark.parametrize("value", LINE_BOUND_PAIRS_REFUSED)
def test_a_bare_key_pair_beginning_a_line_is_refused(value):
    reason = services._looks_like_secret(value)
    assert reason is not None, f"{value!r} begins a settings line and was accepted"
    assert "hunter2" not in reason and "abc123" not in reason, "the refusal printed the value"


@pytest.mark.parametrize("value", LINE_BOUND_PROSE_ACCEPTED)
def test_a_bare_key_inside_a_sentence_is_still_prose(value):
    assert services._looks_like_secret(value) is None, f"prose was refused: {value!r}"


def test_the_rule_is_the_line_boundary_and_the_separator_form():
    """AC1: the same pair is refused at a line start and accepted inside a sentence.

    This is the distinguishing rule stated in the code: a bare key pair is read where it begins a
    line (start of value, after a newline, after a separator) and not where a word and a space
    precede it. It is a line-boundary rule, not a wider whitespace class.
    """
    assert services._looks_like_secret("key = hunter2") is not None
    assert services._looks_like_secret("auth = none\nkey = hunter2") is not None
    assert services._looks_like_secret("the key: it is in the vault") is None
    # A slot reference is configuration on either line of a settings blob.
    assert services._looks_like_secret("auth = none\nkey = ${API_KEY}") is None


def test_a_line_bound_key_pair_is_refused_by_the_bare_key_rule():
    """The refusal comes from the branch that already reads a bare key, not a new one."""
    reason = services._looks_like_secret("auth = none\nkey = hunter2")
    assert reason == services._looks_like_secret("key = hunter2")


# --------------------------------------------------------------------------- AC2 the camel fragment

# One segment of a longer word is not a bare credential word, whatever its case. Both spellings must
# reach the same verdict - capitalisation may name the word but must not decide it.
CAMEL_ACCEPTED = ["the-usbKey", "the-hotKey", "the-turnKey", "the-monKey", "the-donKey"]
LOWER_ACCEPTED = ["the-usbkey", "the-hotkey", "the-turnkey", "the-monkey", "the-donkey"]
# A known qualifier is what licenses a split inside the word; these stay refused.
QUALIFIED_CAMEL_REFUSED = ["the-apiKey", "the-sshKey", "the-privateKey"]


@pytest.mark.parametrize("value", CAMEL_ACCEPTED)
def test_a_camel_fragment_is_not_a_bare_credential_word(value):
    assert services._looks_like_secret(value) is None, \
        f"{value!r} is one word and was refused for its capital letter"
    assert services.validate_settings({"name": value}) == {"name": value}


@pytest.mark.parametrize("camel,lower", list(zip(CAMEL_ACCEPTED, LOWER_ACCEPTED)))
def test_a_camel_word_keeps_the_verdict_of_its_lower_case_form(camel, lower):
    assert services._looks_like_secret(camel) == services._looks_like_secret(lower) is None
    assert services._looks_like_secret(camel.upper()) is None


@pytest.mark.parametrize("value", QUALIFIED_CAMEL_REFUSED)
def test_a_qualified_camel_key_is_still_refused(value):
    reason = services._looks_like_secret(value)
    assert reason is not None, f"{value!r} names a qualified key and was accepted"
    assert reason == services._looks_like_secret("my-key"), \
        "the camel spelling must reach the same branch as the hyphenated one"


def test_the_camel_split_does_not_manufacture_a_key():
    """AC2 at the normaliser: only a known qualifier cuts a word, and case cuts nothing."""
    assert services._credential_parts("usbKey") == ["usbKey"]
    assert services._credential_parts("hotKey") == ["hotKey"]
    assert services._credential_parts("turnKey") == ["turnKey"]
    assert services._credential_parts("monKey") == ["monKey"]
    assert services._credential_parts("donKey") == ["donKey"]
    # The qualified spellings still arrive as two parts, which is what keeps them refused.
    assert services._credential_parts("apiKey") == ["api", "Key"]
    assert services._credential_parts("sshKey") == ["ssh", "Key"]
    assert services._credential_parts("privateKey") == ["private", "Key"]


# --------------------------------------------------------------------------- AC3 the URL floor

# A password inside a URL is a shape, not a vocabulary lookup: refused anywhere in the value, with
# or without a credential word beside it.
INLINE_PASSWORD_REFUSED = [
    "postgres://app:pa55word@db/qa",
    "the db is at postgres://app:pa55word@db/qa",
    "dsn=postgres://app:pa55word@db/qa",
    "mysql://root:hunter2@localhost/qa",
    "see https://ci:tok3n@ci.example.com/job",
]
# Honest URLs carry no password and stay configuration.
HONEST_URLS_ACCEPTED = [
    "postgres://app@db/qa",
    "https://example.com/path",
    "dsn=postgres://db.example/qa",
    "webhook=https://hooks.example.com/services/T000/B000",
]


@pytest.mark.parametrize("value", INLINE_PASSWORD_REFUSED)
def test_an_inline_password_is_refused_anywhere(value):
    reason = services._looks_like_secret(value)
    assert reason is not None, f"{value!r} carries a password in a URL and was accepted"
    assert "pa55word" not in reason and "hunter2" not in reason and "tok3n" not in reason, \
        "the refusal printed the password"
    assert "URL" in reason, "the reason should name the shape the reader has to change"
    with pytest.raises(services.ConfigError):
        services.validate_settings({"name": value})


@pytest.mark.parametrize("value", HONEST_URLS_ACCEPTED)
def test_an_honest_url_is_still_configuration(value):
    assert services._looks_like_secret(value) is None, f"{value!r} was refused"
    assert services.validate_settings({"name": value}) == {"name": value}


def test_the_url_floor_fires_without_any_credential_word():
    """AC3: the shape alone refuses; nobody has to have listed a word for this value."""
    assert services._looks_like_secret("postgres://app:pa55word@db/qa") is not None
    assert services._looks_like_secret("postgres://app@db/qa") is None


# --------------------------------------------------------------------------- AC4 the comment

def test_the_comment_separates_shape_only_rules_from_vocabulary_rules():
    """AC4: a reader must know where the word-free floor ends."""
    source = inspect.getsource(services)
    raw = source.split("_STRONG_WORDS = ", 1)[0]
    comment = " ".join(raw.split())
    for phrase in ("shape-only", "vocabulary-dependent", "PEM", "JWT", "issued-token",
                   "inline", "password in a URL"):
        assert phrase in comment, f"the vocabulary comment does not name {phrase!r}"
    docstring = services._looks_like_secret.__doc__ or ""
    for phrase in ("shape-only", "inline password", "depend on the vocabulary"):
        assert phrase in docstring, f"the screen's docstring does not state {phrase!r}"
