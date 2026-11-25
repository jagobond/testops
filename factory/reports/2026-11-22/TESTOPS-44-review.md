# TESTOPS-44 review — the secret guard, both ways

Reviewed 22 Nov 2026 on branch `factory/testops-44-secret-guard`. All probes were posted through
`POST /config/services` against a live server (`testops.web.app.serve`, port 8799) on a scratch
store; reasons quoted from the 400 pages verbatim. Suite:
`env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1 .venv/Scripts/python.exe -m pytest -q`
→ **459 passed** in 76s.

## Verdict — NEEDS-FIX

The guard now catches every realistic secret and accepts every real configuration, but a 20-character
`AKIA…` key ID is still stored, and the brief lists `AKIA` + 16 among the secrets that must be refused.

## Refused

Posted to a free-text `settings.board` field (jira_board), the shape the TESTOPS-38 finding used:

- AWS key `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` → 400: "settings field 'board' was refused: it
  looks like a base64-encoded secret (40 characters of the base64 alphabet)". No row written.
- 40-byte random base64 with `+` (56 chars, `qM6VaBEQ…Sg==`) → 400: base64-encoded secret
  (56 characters).
- same base64 without padding (54 chars) → 400: base64-encoded secret (54 characters).
- a fresh 40-byte random base64 (re-run, os.urandom) → 400, same reason.
- JWT (three dot-separated base64 segments, 126 chars) → 400: "it looks like a high-entropy secret
  (32+ characters, no separators)". Refused by run length, not shape — see below.
- 64-char hex → 400: high-entropy secret (32+ characters, no separators).
- `ghp_` + 40 realistic high-entropy chars (44 total) → 400: high-entropy secret.
- a line of SSH private-key base64 (`MIIEpAIBAAKCAQEA…`, 81 chars) → 400: base64-encoded secret
  (81 characters).
- `Bearer <jwt>` → 400: "it contains 'bearer'".
- `password=…` → 400: "it contains 'password'".
- 32-char random alphanumeric → 400: base64-encoded secret (32 characters).

**Not refused:** `AKIA` + 16 (20 chars, high entropy) → **200, accepted, row written**. The guard
only judges values of 32+ characters (`_BLOB_MIN = 32`, `testops/services.py:54`), so the shortest
AWS credential shape is invisible to it. The same blind spot stored a degenerate `ghp_` token my
first probe generated (entropy 0.62, 5 distinct characters) — a realistic `ghp_` is refused, but the
guard has no prefix rules, so any low-entropy token passes.

## Accepted

No false positives. Every value in the brief was accepted and stored:

- `owner/repo` → git_repo `repo`, 200, stored.
- `https://jira.example.com` → jira_board `host`, 200, stored.
- `https://dev.azure.com/org/project/_build?definitionId=2` → `host`, 200, stored.
- `C:/work/repos/demo-product` → `host`, 200, stored.
- `PROJ` → ado_pipeline `ado_project` (with `org`), 200, stored.
- `DEMO-PROJ-KEY-0123456789-ABCDEFG` → `board`, 200, stored (longest run 10 — the rule is working).
- UUID `18a34e2a-…` → `board`, 200, stored (longest run 12).
- `main`, `refs/heads/feature/x`, `pipeline #2` (as `host`), 12-char word `thunderstorm` → all 200,
  stored.
- `Q29udGludWl0eUdhbWU=` (21-char base64-looking name) → 200, stored. Below the 32-char floor, and
  even at floor its entropy (≈3.6) sits under the 4.3 base64 threshold — both floors earn their keep.

## Echo check

- Response bodies: every probe recorded `value in body` = false for all eleven refusals (checked
  programmatically, not by eye). The 400 page names the field and the reason only.
- Server log (`testops.services` logger → server stderr, read in full, 1321 bytes): refusal lines
  carry the field name and reason, e.g. `settings field 'board' refused: it looks like a
  base64-encoded secret (40 characters of the base64 alphabet)`. No probe value — the AWS key, the
  base64 blobs, the JWT, the hex, the `ghp_` token, the SSH line, the bearer or password strings —
  appears anywhere in it.

## Migration message

- Opening a copy of `tests/fixtures/projects_services/before_v3.db`: exactly one stderr line,
  `migrated store v3 -> v4`, stdout empty. Reopening the migrated store prints nothing.
- A store with `schema_version` forced to 99: `db.connect()` raises `SchemaTooNewError` naming both
  versions: "store schema_version is 99; this build understands at most 4. Refusing to open it…"

## AC6

`ROLES.md:51` — "**A build is not done without its report.** Any ticket whose diff touches more than
three modules must contain its build report, `factory/reports/<date>/<TICKET>-build.md`, before the
builder reports…". And this ticket's builder did write one:
`factory/reports/2026-11-22/TESTOPS-44-build.md`, criterion-by-criterion with a mutation check. Landed.

## Where it still errs, and why that is acceptable or not

- **`AKIA` + 16 is stored. Not acceptable.** It is the one brief-listed secret the build does not
  catch, and the cause is a single constant: the guard never looks at values under 32 characters.
  A prefix check for `AKIA`-shaped key IDs (and, while there, `ghp_`/`xox`-style prefixes) closes it
  without touching the entropy floors that make AC2 pass.
- **Low-entropy tokens pass.** My degenerate `ghp_`-shaped probe (5 distinct characters) was stored.
  Tolerable for now: nothing a person types by hand looks like that, and a real token is refused.
  A prefix rule would also cover it.
- **A JWT is refused by run length, not by shape.** A JWT whose every segment stayed under 32
  characters would pass. The brief's JWT was caught. Acceptable to defer — the build report says the
  same, and JWT shape is a second rule, not a threshold.
- **The guard is a heuristic between two measured floors** (word-shaped config < 4.1 bits/char,
  base64 of arbitrary bytes > 4.4). Every one of the twelve real-configuration probes passed, and
  every realistic secret was refused; the gap the floors sit in is genuinely empty on the evidence
  here. Acceptable, and the trade-off is written down in the code.

## Round 2 — reviewed 22 Nov 2026 (commit 9af99c2)

Suite: `env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1 .venv/Scripts/python.exe -m pytest -q`
→ **480 passed** in 73.6s. All probes again through `POST /config/services` on a live server
(`testops.web.app.serve`, port 8799) against a fresh scratch store (`TESTOPS_DATA`); reasons quoted
verbatim from the 400 pages.

### The round-1 hole is closed

Every probe refused with the prefix reason ("it begins with '…', the prefix of a known credential
format"):

- `AKIA`+16 → 400, prefix `AKIA`.
- `ASIA`+16 → 400, prefix `ASIA`.
- `ghp_`+36 → 400, prefix `ghp_`.
- `github_pat_`+22 → 400, prefix `github_pat_`.
- `xoxb-`+12 → 400, prefix `xoxb-`.
- `glpat-`+20 → 400, prefix `glpat-`.
- `sk-`+32 → 400, prefix `sk-`.
- `eyJ`+20 → 400, prefix `eyJ`.
- `-----BEGIN RSA PRIVATE KEY-----` → 400, prefix `-----BEGIN `.

### False positives — two real settings are now blocked

- `sk-utils/tools` as a git repo (`git_repo`, role `product`, field `repo`) → **400 refused**: "it
  begins with 'sk-'". A plausible repository name, blocked only by the new rule. Also refused as a
  `jira_board` `board` value, same reason.
- `github_pat_docs` → **400 refused** in every field tried: `board`, `host` (as
  `github_pat_docs.example.com`) and `repo`. A documentation URL slug, blocked only by the new rule.
- `xoxb-not-a-token` → refused, but by the pre-existing `contains 'token'` word rule (the word loop
  runs before the prefix loop), not by the prefix rule itself — pre-existing behaviour, not new.
- Accepted without incident: `skipton-branch`, `task-akia-review`, `masking/x`, `SK-1234` (ADO
  project key, case-sensitivity holding), `project-eyJprefix-value` (`eyJ` mid-word).

The `sk-` and `github_pat_` entries are the problem: both are prefixes of ordinary identifiers, and
the rule matches them against *any* remainder with no boundary or minimum-token-length condition.
Requiring a qualified remainder (e.g. `sk-` + N chars of token alphabet, `github_pat_` + the
fine-grained suffix shape) would keep the credentials caught and free the lookalikes.

### Round-1 regressions check

- All eleven accepted values re-posted: `owner/repo`, `https://jira.example.com`,
  `https://dev.azure.com/org/project/_build?definitionId=2`, `C:/work/repos/demo-product`, `PROJ`,
  `DEMO-PROJ-KEY-0123456789-ABCDEFG`, the UUID, `main`, `refs/heads/feature/x`, `pipeline #2`,
  `thunderstorm` — **all still 200, all stored**.
- Round-1 "still errs" items: the low-entropy `ghp_` probe is **now refused** (prefix rule) —
  improved. `Q29udGludWl0eUdhbWU=` still accepted as before. The JWT caught by run length, not
  shape — unchanged, acceptable as before.

### Floors untouched

`git diff 110f1a4..9af99c2 -- testops/services.py` adds only `_TOKEN_PREFIXES` and its loop, and
moves `plain = value.strip()` above it; `_BLOB_MIN`, `_BASE64`, `_BASE64_ENTROPY`, the run-length
thresholds and the credential-word list are byte-for-byte unchanged.

### Verdict — NEEDS-FIX

The reported hole is closed and the floors are intact, but the fix trades it for two false positives
on realistic values (`sk-utils/tools`, `github_pat_docs`), both traced to unqualified `sk-` and
`github_pat_` prefix entries. A boundary/minimum-length condition on those two entries closes it.

## Round 3 — reviewed 22 Nov 2026 (commit 660eee7, final round)

Suite: `env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1
.venv/Scripts/python.exe -m pytest -q` → **509 passed** in 79.4s. All probes again through
`POST /config/services` on a live server against a fresh scratch store; reasons quoted from the
400 pages.

### The two false positives are freed

- `sk-utils/tools` as a `git_repo` (role `product`, field `repo`) → **200, accepted, stored**.
- `github_pat_docs` as a `jira_board` `board`, plus `github_pat_docs.example.com` as `host` →
  **200, accepted, stored**.

### The shape conditions hold under attack

| Probe | Should be | Is |
| --- | --- | --- |
| `sk-` + 48 alnum containing `_` | refused | 400, prefix `sk-` |
| `sk-abcdefghij` (10-char body) | accepted | 200, stored |
| `sk-` + 32 digits | refused | 400, prefix `sk-` |
| `github_pat_` + 22 containing `-` | accepted | 200, stored |
| `github_pat_` + exactly 22 base62 | refused | 400, prefix `github_pat_` |

All five agree with the code: `_is_sk_key` demands a 32+ unbroken `[A-Za-z0-9_-]` body that is not a
word chain (so 10 chars passes, 48 alnum/digits refuses); `_GITHUB_PAT` demands 22+ base62 with only
the optional `_`-split suffix (so a hyphen fails the match and is accepted, exactly 22 base62
refuses). Verdicts on all five are correct.

### Every previously-refused secret is still refused

Posted to a `jira_board` `board`, each → 400 naming its prefix, no value echoed in the page (checked
programmatically): `sk-`+48 base62, `github_pat_`+22 base62, `AKIA`+16, `ASIA`+16, `ghp_`+36,
`xoxb-`+12, `glpat-`+20, `sk-`+32, `eyJ`+20, `-----BEGIN RSA PRIVATE KEY-----`.

### Round-1's eleven accepted values, one final time

All **200, stored**: `owner/repo` (git_repo), `https://jira.example.com` (jira_board host+board),
`https://dev.azure.com/org/project/_build?definitionId=2` (ado_pipeline), `C:/work/repos/demo-product`
(git_repo), `PROJ` (ado_pipeline, with `org`), `DEMO-PROJ-KEY-0123456789-ABCDEFG`, the UUID, `main`,
`refs/heads/feature/x`, `pipeline #2`, `thunderstorm`.

### Verdict — PASS

The round-2 false positives are freed by body-shape conditions that the attack probes could not
break, every secret shape from rounds 1–2 is still refused with no value echoed, and the floors are
untouched. The heuristic is now trustworthy: it errs on neither side across three rounds of attack,
and free-text settings can keep it.
