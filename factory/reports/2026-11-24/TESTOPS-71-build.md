# TESTOPS-71 build - the quiet fallback, the lying field, the placeholder

Ticket: `factory/tickets/TESTOPS-71.md`. Branch: `factory/testops-71-quiet-fallback`, built in the
linked worktree `C:/Users/<name>/Projects/testops-t71`. The live store and port 8791 were never
contacted: every probe is a direct call to `testops.services`, the guard in `tests/support.py`, or a
disposable git repository under `tmp_path`.

`factory/reports/2026-11-24/TESTOPS-69-review.md` does not exist in this worktree or the main
checkout, so the three faults were taken from the ticket, which states them in full.

Files touched: `tests/support.py`, `testops/services.py`, `tests/conftest.py` (docstring only),
`tests/test_guard_attribution.py` (one test's fixture and docstring) and the new
`tests/test_quiet_fallback.py` (37 tests). No case-page golden, template, fixture or contract seed
changed.

## AC1 - an unknown tracked set is not an empty one

`tracked_paths` now returns `frozenset[str] | None`. `None` means git could not answer: the state
was unreadable, or `HEAD`'s tree could not be read. `_walk` takes the optional set and, when it is
`None`, prunes nothing but `.git` and ignores nothing by name - every walked path, including
`.venv/`, `build/`, `dist/`, `__pycache__/` and `*.pyc`, is **content**. An empty set is now reserved
for a readable repository that really tracks nothing (a fresh `git init`), where the ignore policy is
the honest answer. `GitRepository.state()` also stopped treating a failed `ls-files` as a readable
empty index - that was the same conflation one layer down.

Pinned with git made unreadable (`GitRepository._git` returns `None` for every call) at both ends of
a run over a repository with a committed `generated.pyc`: the `.pyc` is in both snapshots, its
rewrite is `unreadable`/failing rather than `ignored_changed`, and `git readable: no` prints. A
separate test pins the unknown-set walk directly (`.venv/lib/vendored.py`, `generated.pyc`,
`build/out.bin` all content, ignored snapshot empty).

One existing test changed meaning and was updated rather than weakened:
`test_a_write_under_a_policy_ignored_directory_is_visible_not_attributed` used a tmp directory that
was not a git repository, i.e. the exact unknown-set case. It now runs `git init` first, so its
`build/` and `__pycache__/` files are untracked churn in a repository that is readable - which is
what the test was always about.

## AC2 - `git readable` covers the walk's lookup

`Snapshot` carries `tracked_known`; `guard_report` passes it to `attribute_differences` as
`walk_readable`, and `git_readable` is the conjunction of both states' reads, the walk's lookup and
the commit trees. A `walk_readable=False` run prints `git readable: no` and an extra summary line:
"the tracked-path lookup failed, so every walked path was treated as content and nothing was pruned
or ignored by name". Pinned both at `attribute_differences` (readable states, failed walk) and
through `guard_baseline`/`guard_report` on a non-repository directory.

## AC3 - a slot reference is accepted wherever a value is read

The `_CREDENTIAL_PAIR` loop now consults `_is_reference` for **every** strong word, not only the key
family. `?token=${TOKEN}`, `page_token=${TOKEN}`, `token=${PAGE_TOKEN}`, `api_key=os.environ["X"]`
and `key = from-env` are configuration; `?page_token=abc`, `page_token=abc` and `token=hunter2` are
still refused with the same pair-branch reason, and the reason never prints the value. The comment
at the rule states why the family limit was wrong.

## AC4 - placeholders are placeholders

`_PLACEHOLDER_VALUE` is a whole-value vocabulary: `YOUR_KEY_HERE`, `YOUR_API_KEY`, `<your-key>`,
`changeme`, `xxxx`, `***`, `REDACTED`, `TODO`, `example`. `_is_reference` treats a placeholder as a
slot like `${API_KEY}`, and `_looks_like_secret` returns early on a whole-value placeholder whether
free-standing, a pair value or a query value, so the later identifier rule cannot re-refuse what the
pair branch accepted. Pinned accepted in both a pair and a query string (15 values), and refused for
`token=hunter2`, `?token=hunter2`, a 36-character base62 body and `api_key=AKIAIOSFODNN7EXAMPLE`.

Note: `example` appears inside the AKIA test value; the placeholder vocabulary is whole-value and
anchored, so the AKIA shape is still refused by the issued-prefix rule.

## AC5 - the tab's false-positive family, stated

Written at `_BARE_KEY_PAIR` beside the TESTOPS-69 residual 6 paragraph: because a tab is a line
boundary, `notes\tkey: in the vault` is refused as configuration, and that is the price of reading
every pasted table row loudly. Pinned as behaviour and as a source paragraph (a test fails if the
paragraph is edited away).

## AC6 - no detection weakened

- Full suite: **1169 passed, 2 skipped** (1132 before + 37 new).
- Contract suite `tests/contracts`: **37 passed, 2 skipped**, unchanged.
- The credential tables in `test_credential_seams.py`, `test_credential_vocabulary.py`,
  `test_config_credential_screen.py` and `test_secret_guard.py`: 447 passed, unchanged verdicts.
- Every rule changed here only *adds* acceptance for a slot reference or a placeholder, or *adds*
  attribution for an unknown tracked set. No literal secret became accepted; no difference became
  merely reported.
- No case-page golden, template or fixture changed; `git status` shows only the five files above.

## Residual risk, named

1. **An unreadable walk is slow, not silent.** When git cannot answer, `.venv` is walked and digested
   because an unknown set licenses no pruning. That is the loud direction the ticket asks for; the
   cost is a slower baseline in a directory with a large virtualenv.
2. **A placeholder vocabulary is finite.** A template label nobody listed (`PUT_TOKEN_HERE`) is not
   recognised; the same class of residual as the credential vocabulary (TESTOPS-65 AC5).
3. **A placeholder beside a literal is not a placeholder.** `token=YOUR_KEY_HERE_AND_hunter2` is a
   literal; only a whole-value placeholder is accepted.
