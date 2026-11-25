# TESTOPS-68 build - the line boundary, the camel fragment, and the URL floor

Ticket: `factory/tickets/TESTOPS-68.md`. Branch: `factory/testops-68-seams`, built in the linked
worktree `C:/Users/<name>/Projects/testops-t68`. The live store and port 8791 were never contacted:
every probe is a direct call to `testops.services`, plus the existing in-process HTTP test.

Note on sources: `factory/reports/2026-11-24/TESTOPS-65-review.md` does not exist in this worktree or
in git history. The ticket restates the review's three concerns verbatim, so the ticket text was used
as the brief. Files touched: `testops/services.py` and the new `tests/test_credential_seams.py`
(43 tests). No case-page golden, template, fixture or contract seed changed.

## AC1 - the bare-value branch was one newline behind

The lookbehind excluded all whitespace, so `key` after a newline was "prose" and

    auth = none\nkey = hunter2
    repo=x\nkey = hunter2

were accepted. The distinguishing rule is now stated in the code, at the pattern: a bare key pair is
refused where it **begins a line** of configuration - start of value, after a newline (with optional
indentation), or after a separator such as `;` - and accepted where a word and a space precede it, as
in "the key: it is in the vault". The lookbehind excludes horizontal whitespace only (space, tab), so
a newline is a boundary; `re.MULTILINE` plus `[ \t]*` lets an indented settings line be read as a
line. It is not a wider whitespace class: allowing all whitespace is exactly what hid the second line.

Both directions pinned: the seven line-bound blobs (`auth = none\nkey = hunter2`, `repo=x\nkey =
hunter2`, `settings:\n  key: hunter2`, indented, after `;`, after blank lines, after another pair) are
refused with the value absent from the reason; nine prose/settings values, including "the key: it is
in the vault" and `sort_keys=True`, are accepted. The line-bound refusal is asserted to come from the
*same branch* as `key = hunter2`.

## AC2 - the camel split no longer manufactures a `Key`

`_credential_parts` split camel boundaries before the merge split, so `usbKey` arrived as
`["usb", "Key"]` and the fragment `Key` matched the bare-word rule. The normaliser now treats a
capital letter as spelling, not a word boundary: inside a word, the only cut is one a **known
qualifier** licenses (`@KEY_QUALIFIERS`), the same closed class that already decides `apikey`.
`_CAMEL_BOUNDARY` is gone.

Pinned in both directions: `the-usbKey`, `the-hotKey`, `the-turnKey`, `the-monKey`, `the-donKey` are
accepted, each equal to its all-lower-case twin and to its upper-case twin; `the-apiKey`, `the-sshKey`,
`the-privateKey` stay refused, with the same reason string as `my-key`. `_credential_parts("usbKey")
== ["usbKey"]`, `_credential_parts("apiKey") == ["api", "Key"]` (the T65 pin is kept).

## AC3 - the inline password is a floor, not a gate

`_INLINE_PASSWORD` was consulted only inside `_is_reference`, which only pair branches reach after a
credential word matched. It is now rule 0 in `_looks_like_secret`, before any vocabulary rule, so
`scheme://user:secret@host` is refused anywhere in a value, with or without a credential word. The
reason names the shape ("it embeds a password in a URL") and never the password. Both ways pinned:
five password-bearing URLs (`postgres://app:pa55word@db/qa` bare, inside a sentence, as a `dsn=`
pair, `mysql://...`, an https URL with userinfo) refused; four honest URLs (`postgres://app@db/qa`,
`https://example.com/path`, `dsn=postgres://db.example/qa`, an honest webhook) accepted.

## AC4 - the comment tells the truth

The vocabulary comment (before `_STRONG_WORDS`) now divides the value rules in two, in those words:
**shape-only** - PEM, JWT, known issued-token prefixes and truncations, base64/entropy, inline URL
password - which need nobody to have thought of the word; and **vocabulary-dependent** - the pair
rule, the instance/determiner rule, `key` qualification and the bare `key` pair - which catch only
what the list names. The old claim that the pair rule was word-free is deleted. `_looks_like_secret`'s
docstring carries the same split, so the floor's end is readable where the rules are. A test reads the
source and fails if either statement is edited away.

## AC5 - no weakening, nothing honest regressed

- Full suite: **1097 passed, 2 skipped** (157.78s). The 43 new pins are the difference.
- Contract suite `tests/contracts`: **37 passed, 2 skipped**, unchanged.
- T59's twenty ordinary values, T62's twelve refusals, T63's accepted and refused `key` sets, the
  33-row false-positive bill and the twenty collisions are all in the existing suites and still pass.
- `git status` shows only `testops/services.py` and the new test file; no case-page golden changed.

## Residual risk, named

1. **A capital letter now never splits a word.** `myPassword` is accepted where it was refused, because
   `mypassword` always was; that is AC2's principle applied consistently, not a special case. A label
   that relies on camel case alone to look like a credential is now a kind name, and the shape rules
   still catch a pasted credential.
2. **A prose line that begins `Key: ...` is read as configuration.** That is the stated rule (line
   boundary plus separator form); the sentence form ("the key: ...") is the accepted one.
3. **The inline-password pattern is a shape, not a parser.** It matches `://...:...@` on one line and
   does not decode percent-escaped userinfo beyond that shape; a password in a URL with no `:` before
   the `@` is indistinguishable from a username and is not caught by this rule (it was not before
   either).
4. **The vocabulary is still knowingly incomplete** (T65's residual), and the comment now says which
   rules do not depend on it.

## Verification

```
env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
  C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe -m pytest -q
1097 passed, 2 skipped in 157.78s

env ... -m pytest -q tests/contracts
37 passed, 2 skipped in 12.68s
```
