# TESTOPS-59 review — the screen now looks inside the value, and the boundary states itself

Reviewer run, 2026-11-24. Worktree `C:/Users/<name>/Projects/testops-t59`, branch
`factory/testops-59-prose-scan`, HEAD `4b11e27`. Interpreter everywhere:
`env -u PYTHONPATH -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1
C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe`.

Every probe below was run by me, not taken from the build report. Function-level probes called
`_looks_like_secret` / `_names_a_credential` directly with `PYTHONPATH` pinned to this worktree;
the HTTP battery ran against a copy of `data/` served by an in-process `ThreadingHTTPServer` on an
ephemeral port with `TESTOPS_DATA` pointed at the copy. The live store was never written and port
8791 was never contacted: `data/testops.db` hashed `6b0d38bd…c47c` before and after my whole
session — identical to the build's record.

## Verdict

**PASS — mergeable, with one finding worth a ticket.** The leak the ticket exists for is closed at
every shape I tried, over HTTP and in the function, with the value echoed nowhere and nothing
stored. The twenty ordinary values I pushed through the Name field were **all accepted — zero
refusals of ordinary prose**, which is the direction this ticket's fix could have broken and did
not. The grammatical rule is genuinely structural and better than what it replaced, but it is not
purely grammatical in one direction: my best counterexample slips past it. Every real token of
every covered format is still refused; contract suite 36 passed / 3 skipped; full suite 829 passed
/ 3 skipped; no case-page golden changed (the diff touches only `services.py`, three test files
and `factory/`).

## The leak, closed

All refused over HTTP through the service **name** field (a 400 page, value absent from the
response body, absent from the copied SQLite file, service rows 12 → 12):

| Probe (real body inside a sentence) | Result |
|---|---|
| `the key is ghp_<36>` | 400, names `ghp_` |
| `aws id AKIA<16>` | 400, names `AKIA` |
| `the jwt is <3-segment JWT>` | 400, names the JWT shape |
| PEM block inside a sentence | 400, names the PEM block |
| `notes: name=token=abc123` | 400, names the `token=` pair |
| `the key is ghp_<40>` (legacy body) | 400 |
| `bot xoxb-<real segments>` / `pat glpat-<20>` / `pat github_pat_<22>_<59>` | 400, all three |
| `the key is ghp_<36>.` (trailing period) | 400 |

The reason strings name the prefix or the shape, never the value. Raw scan of the copied store
afterwards: 0 occurrences of every token body and of `abc123`. The mechanism is as the build
claims: rules 1, 2 and 4 all `search`/`finditer` now; nothing depends on position 0 or on the
absence of whitespace, and the authorisation-scheme rule requires the value to be the whole
remainder, which is what lets "Bearer token rotation work continues" through.

## Overreach, my twenty

All twenty through the Name field over HTTP. Every one **accepted (303)**:

| Value | Result | Right for a real user? |
|---|---|---|
| `the token is validated in middleware` | accepted | yes — a sentence |
| `our password policy is documented` | accepted | yes |
| `Bearer tokens are refreshed hourly` | accepted | yes — the old `^\s*bearer\s+\S+` rule would have refused this; the fix is real |
| `secrets are rotated weekly` | accepted | yes |
| `jwt.decode lives in lib/auth.py` | accepted | yes |
| `no token needed for this endpoint` | accepted | yes |
| `docs/how-to-reset-your-password.md` | accepted | yes |
| `pat-notes.md` | accepted | yes |
| `gh_workflows/` | accepted | yes |
| `akia-notes` | accepted | yes — lower-case lookalike, correctly exempt |
| `xox-not-a-slack-token` | accepted | yes |
| `the private key is in vault` | accepted | yes |
| `my-password-manager` | accepted | yes — head is `manager`, not the credential word |
| `session-token` | accepted | yes — the T56 wrong refusal, fixed |
| `vault-token` | accepted | defensible and argued (HashiCorp's own phrase); same grammatical shape as `session-token`, so consistent |
| `password-list` | accepted | yes |
| `passwords-list` | accepted | yes — decided with its singular, not by accident |
| `token-refresh-service` | accepted | yes |
| `the-token-service` | accepted | yes |
| `my-secret-store` | accepted | yes — head is `store` |

A scanner that finds a "token" in every sentence gets turned off; this one found none. The
overreach risk this ticket created is, on this evidence, not realised.

## The grammatical rule, judged

`_names_a_credential` (services.py:177) and `_DETERMINERS` (services.py:170): refuse a bare
credential word; refuse a name that ends in a credential word and opens with a determiner or
possessive; accept every other compound. I judge this **mostly genuinely structural**: the
determiner set is a closed grammatical class, not a vocabulary list, and `session-token` /
`vault-token` / `token-bucket-limiter` / `password-manager` all land on the accepted side by one
stated principle (the credential word is the head of a compound *noun* naming a kind of thing,
not a particular instance) rather than by membership. That is a real improvement over T56's
"last part, at most three parts" rule, which was a list wearing grammar.

But it is not a different list in only one direction — the checks I ran show the asymmetry:

* **Wrong-refusal counterexample: `this-is-not-a-password`.** It ends in a credential word and
  opens with `this`, so it is refused — yet it is a five-word sentence-name, the kind of joke
  repository name that exists in the wild, and it names no credential at all. The rule reads the
  first and last word and nothing between; a long name can carry a determiner at position 0
  without being an instance.
* **Wrong-acceptance counterexample: `acme-their-password`.** The rule checks only `parts[0]`,
  so a possessive in any other position is invisible. `acme-their-password` is accepted, yet it
  names a particular credential exactly as plainly as `my-password` does — the possessive is
  grammatical, just not first. (The documented `prod-db-password` residual is the same family:
  head is the credential word, no determiner, accepted as a "type name" when it can equally be
  an instance label.)

Neither is a safety hole — a real pasted credential is caught by rules 1, 2 and 4 wherever it
sits, so the identifier rule is a politeness boundary, not the screen — and the cost of a wrong
verdict is a rewording, never a leak. But the rule claims to state itself, and these two are the
cases it cannot state.

## False negatives

Real shapes, lengths asserted before judging (refused means refused by the screen, whichever rule):

| Real format at its real body | Result |
|---|---|
| `ghp_` + 36 base62 / + 40 base62 / `ghu_` + 36 | refused (all) |
| `github_pat_` full 82 (22 + `_` + 59) | refused |
| `AKIA` + 16 uppercase base32 | refused |
| `xoxb-` realistic (12/13-digit segments + 24 tail) | refused |
| `glpat-` + 20 | refused |
| JWT, 3 segments | refused |
| RSA PEM block | refused |
| `sk-` + 48 | refused |

Variations:

| Variation | Result | Right? |
|---|---|---|
| `ghp_` 36, one character changed | refused | yes — still an indistinguishable format-shaped paste |
| `ghp_` body 35 | refused | yes — caught by the high-entropy blob rule (32+), not by the prefix rule; a nice second net |
| `ghp_` body 30 | accepted | correct — below the entropy floor, reads as a name |
| `AKIA` body, one char changed | refused | yes — still format-shaped |
| `AKIA` body 15 | accepted | correct — not the format's body length |
| `github_pat_` truncated to 22 | accepted | the stated truncation limit; correct per AC4 and stated in the residual note |
| `glpat-` body 19 | accepted | correct |
| `xoxb-` short tail (20) | accepted | correct — below the format's 24-32 tail |
| JWT with a shortened signature | refused | yes — still three `eyJ`-shaped segments |
| `sk-` body 31 | accepted | correct — below the 32 floor |

No real token of any covered format is accepted by its own predicate. The floor/ceiling pair does
what AC4 asked without losing a single real shape.

## Editing

Every settings field of every service kind, create → edit → read back on `/config`, over HTTP on
the copy:

| kind | fields | create | edit | read-back |
|---|---|---|---|---|
| `git_repo` | `repo` | 303, stored | 303, revised value on page | yes |
| `jira_board` | `board`, `host` | 303, both stored | 303, both revised values on page | yes |
| `ado_pipeline` | `org`, `ado_project`, `pipeline_id` (int) | 303, all three stored | 303, revised values incl. `pipeline_id` 42→43 | yes |

No legitimate field refused, none dropped, nothing stored unscreened. An unknown key
(`a_field_added_next_year=value`) posted alongside a valid service returns **400** with a page
that says the configuration was *refused* rather than saved without it — refused, not dropped.

## Contract suite

- `tests/test_config_credential_screen.py` alone: **143 passed**.
- Contract suite alone: **36 passed, 3 skipped** (the three skips are the standing environment
  skips; the former P07/P10 failures from T51/T56 are gone).
- Full suite: **829 passed, 3 skipped** in 141s.
- `git diff 5112dc6..HEAD --name-only`: only `testops/services.py`, three test files, and
  `factory/` documents — **no case-page golden changed**.
- Live store hash identical before and after my session; the copy was used for all writes.

## Three sharpest concerns

1. **The grammatical rule is half-structural.** It reads the first word and the last part and
   nothing in between, so `this-is-not-a-password` is refused (a sentence-name no user would
   expect a scanner to call a credential) and `acme-their-password` is accepted (a possessive
   anywhere but position 0 escapes, and the name names a particular credential as plainly as
   `my-password`). The fix is small — check every part for a determiner/possessive, not only the
   first, or require the compound to be short (≤3 parts) for the refusal — but as written the
   claim "the rule states itself" overstates by exactly one rule.
2. **The truncation limit is a silent accept at the format's most recognisable prefix.**
   `github_pat_` + 22 is accepted as a truncation. It is stated in the residual note and the
   ticket allows it, but a user pasting a cut-off fine-grained token gets a green tick with no
   hint. A warning-grade signal ("looks like the start of a `github_pat_` token") would cost
   nothing and would close the only accepted real-prefix shape on the board.
3. **`vault-token` is accepted on an appeal to HashiCorp's vocabulary, which is a fact about a
   vendor, not about grammar.** The consistency argument (same shape as `session-token`) is the
   load-bearing one and holds; the vendor sentence in the comment and docstring is decoration and
   will age. Say the grammatical reason everywhere and drop the vendor appeal — otherwise the
   next reviewer inherits a word list wearing the grammar's coat, which is the exact defect this
   ticket exists to remove.
