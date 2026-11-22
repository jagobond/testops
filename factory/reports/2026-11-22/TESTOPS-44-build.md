# TESTOPS-44 build report — the secret guard, both ways, and a store that says what it did

Built 22 Nov 2026 on branch `factory/testops-44-secret-guard`, from HEAD `9f31ef3`
(`board: TESTOPS-38 done; TESTOPS-44 opened from its review`). Ticket: `factory/tickets/TESTOPS-44.md`.
Evidence for the finding: `factory/reports/2026-11-22/TESTOPS-38-review.md`, sections *Secrets* and
*Three sharpest concerns*.

## What was built

- `testops/services.py` — the guard now tests the base64 charset before the separator exemption, and
  judges the longest unbroken run rather than the whole value; refusals are logged with the field
  name and the reason, never the value.
- `testops/store/migrate.py` — new `starting_version()`: the version an open starts from, naming an
  unversioned store as v1 (a store that predates `schema_meta` was written by a v1 build) and a new
  file as nothing.
- `testops/store/db.py` — `connect()` prints one line to stderr, `migrated store v3 -> v4`, and only
  when this open actually changed the store.
- `tests/test_secret_guard.py` — 15 tests: AC1, AC2 (every pinned value), AC3 at unit and HTTP level.
- `tests/test_migration_notice.py` — 5 tests: AC4.
- `ROLES.md` — AC6: the Builder section now states that a build is not done without its report.
- `.gitattributes` — the rendered-page fixtures are marked `-text` (see *The suite did not pass on
  this checkout, and not because of this ticket* below).

## The rule, and why it is set where it is

`_looks_like_secret` keeps its first check (a credential word in the value) and then, for values of
32+ characters with no whitespace that are not `http(s)://` URLs, asks two questions in this order:

1. **Is it base64?** `^[A-Za-z0-9+/]+={0,2}$` over the whole value, with entropy ≥ 4.3 bits per
   character. This runs *before* any exemption, so a blob that happens to contain `/` is refused.
   The reviewer's AWS key: 40 characters of the alphabet, 2 slashes, 4.663 bits/char → refused as
   `it looks like a base64-encoded secret (40 characters of the base64 alphabet)`. A deterministic
   stand-in for a random 40-byte secret: 56 characters, 3 slashes, 5.151 bits/char → refused.
2. **Is it one long unbroken run?** Split on `/ \ - . _ :` and judge the longest part. A token is a
   long run (`ghp_…` → 36+ characters in one part → refused); a structured key or a UUID is written
   in short parts (`COTW-PROJ-KEY-0123456789-ABCDEFG` → longest part 10; a UUID → longest part 12 →
   both accepted). The existing entropy floor (3.5) and hex rule are unchanged and now apply to that
   run rather than to the whole value.

The 4.3 floor is a measured threshold, not a proof, and it is recorded as such in the code. Measured
on this build: word-shaped configuration sits below 4.1 bits/char (`SomeOrg/SomeVeryLongRepositoryName2`
= 4.023, `mnt/data/testops/blobs/2026/11/22/abcdef` = 3.874, `src/main/java/com/example/SomeClass` =
3.794); base64 of arbitrary bytes at 32+ characters sits above 4.4. The gap is what the floor sits in.

## Criterion by criterion

| id | verdict | evidence |
|----|---------|----------|
| AC1 | SATISFIED | `tests/test_secret_guard.py::test_base64_is_refused_even_though_it_contains_a_slash[aws-key]` and `[forty-random-bytes]` — both assert the probe contains `/` (or the test is worthless), then that it is refused as base64. `::test_the_reviewers_aws_key_is_no_longer_stored` — the AWS key posted to a free-text field leaves no service row. |
| AC2 | SATISFIED | `::test_real_configuration_is_accepted[repo-owner/repo]`, `[board-COTW-PROJ-KEY-0123456789-ABCDEFG]`, `[host-https://jira.example.com]`, `[project-PROJ]`, `[correlation_id-3f2504e0-…]`, `[label-thunderstorm]`; `::test_all_pinned_configuration_is_accepted_together`; and end-to-end through the page: `::test_the_configuration_page_accepts_a_structured_key_and_stores_it` (board key + host stored), `::test_the_configuration_page_accepts_a_repository_coordinate` (`owner/repo` stored). |
| AC3 | SATISFIED | `::test_a_refusal_logs_the_field_and_the_reason_but_not_the_value` (log has `board` and `base64`, not the value); `::test_the_refusal_page_names_the_field_and_the_reason_but_not_the_value` (HTTP 400, body has `board` and `base64`, not the value, no row written, log likewise). |
| AC4 | SATISFIED | `tests/test_migration_notice.py::test_migrating_a_v3_store_prints_one_line_naming_the_change` (exactly one line, `migrated store v3 -> v4`, stderr, stdout empty); `::test_a_store_opened_for_reading_prints_nothing`; `::test_a_v1_store_names_the_version_it_came_from`; `::test_a_new_store_is_created_without_a_migration_notice`; `::test_a_store_from_a_newer_build_is_refused_naming_both_versions` (both versions named, no notice printed). |
| AC5 | SATISFIED | 459 passed, 0 failed, 0 skipped. CotW pinned run: `tests/test_case_scan.py` asserts 94 claims / 90 distinct / 1 unplaced / 1 gap / 2 review and 94 actions. ReqOverflow: `tests/test_duplication_v2.py` asserts 17 claims / 17 cases / 17 findings / 17 pages. Pages: `tests/test_projects_services.py::test_every_case_page_and_the_indexes_are_byte_identical_after_the_migration` compares 23 files byte-for-byte against the pre-ticket baseline. Live store `data/testops.db` SHA-256 before and after this build: `99f30117419ce8a2e7baba5bc11b66e7b795040828a7ce777e782e865d488d65` (identical to the hash the TESTOPS-38 review recorded). |
| AC6 | SATISFIED | `ROLES.md`, Builder section: "A build is not done without its report…". That section is the standing builder prompt; per-ticket `factory/prompts/build-*.txt` files are Lead-authored and none exists for this ticket, so the standing text is where a builder actually reads it. |

### Mutation check

Each mechanism was removed in turn and the intended test failed (all restored afterwards, diff
stat verified):

| mutation | result |
|---|---|
| base64 branch disabled | 2 failed (`test_base64_is_refused_even_though_it_contains_a_slash`, both parameters) |
| longest-run rule reverted to the whole value | 2 failed, 4 passed (`COTW-PROJ-KEY-…` and the UUID refused again) |
| refusal log line removed | 1 failed (AC3 log test) |
| migration notice removed | 1 failed (AC4 one-line test) |

## Exact numbers

- `env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 .venv/Scripts/python.exe -m pytest -q`
  → **459 passed** in 76.22s (74.26s and 74.77s on the two preceding runs). 439 before this ticket,
  20 new.
- `tests/test_secret_guard.py`: 15 collected, 15 passed. `tests/test_migration_notice.py`: 5 collected, 5 passed.

## The suite did not pass on this checkout, and not because of this ticket

At HEAD, before any change of mine, `tests/test_projects_services.py::test_every_case_page_and_the_indexes_are_byte_identical_after_the_migration`
failed with `At index 59 diff: b'\n' != b'\r'`. Cause: this checkout has `core.autocrlf=true`, the
fixture HTML is stored LF (`git ls-files --eol` → `i/lf w/crlf`), so the baseline came back with CRLF
while the build renders LF. The comparison was measuring the checkout, not the render — on a
machine with `autocrlf=false` it passes, which is how the TESTOPS-38 review saw 439 green.

I marked `tests/fixtures/projects_services/*.html` as `-text` in `.gitattributes` and re-checked the
files out; they are now `i/lf w/lf` and the test passes with no change to the fixture blobs. This is
the only change in this ticket outside the ticket's stated scope, and it is what makes AC5's "pages
unchanged" provable on a Windows checkout rather than accidentally true elsewhere.

## What I could not satisfy, and what I was tempted to do but did not

- **The guard is a heuristic, and I have written down where it stops.** A base64 blob of 32+
  characters whose entropy falls below 4.3 would pass; a slash-containing value with a 32+ character
  unbroken run and entropy ≥ 3.5 (a 39-character single-word GitHub owner, say) is now refused where
  it used to be exempt. Both are consequences of using thresholds at all. I did not tune the floor
  down to catch more base64, because every point lower starts refusing word-shaped configuration —
  which is the failure that gets a guard switched off.
- **A JWT is refused only by its longest run, not by shape.** `eyJ…` tokens contain dots and `_`;
  the last segment is long enough to be caught, but a JWT whose segments were all short would pass.
  Recognising JWT shape is a second rule, not this ticket.
- **I did not make `connect()` refuse to migrate without a flag.** The review suggested "worth a
  printed line"; the ticket asked for the line. A prompt or a `--migrate` flag would change every
  existing caller and every test that opens a fixture, and the ticket did not ask for it.
- **I did not touch the HTTP request log.** `Handler.log_message` is silenced by design; the refusal
  log is on `testops.services`, which is where the guard is. If an operator wants refusals in a file
  they need a logging configuration, which this tool has never had.

## Product problems noticed but not fixed

- `settings` has no per-field type, so the guard judges every value with the same rule and cannot
  know that `host` is a URL and `board` is a key. A per-field rule would be sharper than any
  threshold; it is a ticket of its own.
- `db.connect()` still migrates on open, silently in the sense that nothing asks first. The line is
  a notice, not consent. Anyone who runs a command in this directory with a newer build will upgrade
  the live store; the only protection remains the forward-only refusal.
- The configuration page's refusal message is long and correct, but a person who typed a legitimate
  value and got it back will still be tempted to work around the guard. Nothing in the page explains
  what the guard accepts; the pinned list in `tests/test_secret_guard.py` is the only such document.

## Fix round — 22 Nov 2026 (review: NEEDS-FIX, one finding)

The reviewer found exactly one thing the brief listed and the build missed: an `AKIA` + 16-character
AWS key ID (20 characters) was **accepted and stored**, because every rule in the guard sat behind
`_BLOB_MIN = 32` and a prefix is a shape, not a length. The review's second note — a degenerate
`ghp_` token (5 distinct characters) also stored — had the same root cause.

### The change

`testops/services.py`: a new `_TOKEN_PREFIXES` tuple and a check that runs on the stripped value at
**any** length, immediately after the credential-word check and **before** the entropy floors:

    AKIA, ASIA, ghp_, gho_, ghu_, ghs_, github_pat_, xoxb-, xoxp-, glpat-, sk-, eyJ, "-----BEGIN "

Matching is `str.startswith` and case-sensitive. Case-sensitive because these prefixes are
case-sensitive in the formats themselves, and because the lower-case lookalikes are real
configuration: `skipton-branch` starts with `ski`, `masking/x` with `ma`, `task-akia-review` with
`ta`. Matching the prefix rather than a substring is what keeps `task-akia-review` and
`risk/sk-learn-docs` accepted. The refusal names the prefix only — never the value — so the new rule
is not a second way to print a secret.

**Nothing else moved.** `_BLOB_MIN`, `_BASE64_ENTROPY`, the base64 branch, the separator split and
both entropy floors are byte-identical; the prefix loop is inserted above them, so every value the
old rules accepted but no prefix matches behaves exactly as before.

### Tests — `tests/test_secret_guard.py`, 15 → 36 (+21)

- `test_a_known_token_prefix_is_refused_at_any_length` — 13 parameters, one per prefix, each at its
  shortest realistic value (`AKIA2E0A8F3B244C9986`, 20; `ASIAY34FZKBOKMUTVV7A`, 20; `ghp_…` and the
  other GitHub/Slack/GitLab/`sk-`/`eyJ` forms; `-----BEGIN RSA PRIVATE KEY-----`, 31). Every probe
  asserts `len(token) < _BLOB_MIN`, so the test fails if it is ever rewritten into a value the
  entropy floors would have caught anyway.
- `test_a_value_merely_containing_the_letters_is_accepted` — 5 parameters: `skipton-branch`,
  `task-akia-review`, `masking/x`, `risk/sk-learn-docs`, `COTW-akia-review-board`.
- `test_a_low_entropy_github_token_is_refused` — `ghp_aaaaaaaaa`, the review's degenerate probe.
- `test_the_short_aws_key_id_is_not_stored` — HTTP 400, body and log name the field and `AKIA`, the
  value appears in neither, and no service row is written.
- `test_the_configuration_page_still_accepts_a_branch_named_like_a_prefix` — `skipton-branch` posted
  through `/config/services` and stored.

### Verification

- `env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 .venv/Scripts/python.exe -m pytest -q`
  → **480 passed** in 78.60s (459 before; 21 new, 0 changed or removed).
- All twelve pinned real-configuration probes re-checked individually: `owner/repo`,
  `https://jira.example.com`, `https://dev.azure.com/org/project/_build?definitionId=2`,
  `C:/work/repos/cotw`, `PROJ`, `COTW-PROJ-KEY-0123456789-ABCDEFG`, the UUID, `main`,
  `refs/heads/feature/x`, `pipeline #2`, `thunderstorm`, `Q29udGludWl0eUdhbWU=` — all `None` (accepted).
- Mutation check: `for prefix in _TOKEN_PREFIXES:` replaced with `for prefix in ():` → **15 failed,
  21 passed** (all 13 prefix parameters, the low-entropy `ghp_` test, the AKIA end-to-end test);
  restored and re-run → 36 passed. Diff stat restored to `25` added, `1` moved in `services.py`.

### What the new rule costs, stated plainly

- A legitimate value that *begins* with one of these prefixes is refused. `sk-learn/docs` as a
  repository coordinate is the realistic casualty; a board key that genuinely starts `AKIA` (as
  opposed to containing it) is another. Both are rarer than the credential shapes they buy, and the
  alternative — exempting short prefixes — reopens the finding.
- `sk-` is the broadest entry. It is two characters plus a hyphen, so it will occasionally fire on a
  value a person meant innocently. If that proves noisy in use, the fix is a per-field rule (host vs
  key vs path), which is still the ticket this build flagged and did not take.
- The rule is a false-negative fix, not a proof. A credential with none of these prefixes and fewer
  than 32 characters still passes; the entropy floors remain the backstop they always were.
