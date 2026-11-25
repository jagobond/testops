# TESTOPS-38 review — a project is a group of services

Reviewed 22 Nov 2026, branch `factory/testops-38-projects-services`, HEAD 0b30832.
Every check below ran against copies under
`C:/Users/<name>/AppData/Local/hermes/profiles/reviewer/cache/scratch/t38/`.
The build report named in the dispatch (`factory/reports/2026-11-22/TESTOPS-38-build.md`)
**does not exist** — the directory holds no TESTOPS-38 build report. This review therefore
sits on first-hand evidence only, which is as it should be.

## Verdict — PASS

The migration is honest, reversible-in-effect and byte-neutral to every existing page, and the
secret guard and config page work as the ticket demands — with one false-negative hole in the
secret guard to close in the next ticket, not this one.

## The live store — hash before and after, what you did to copies

- `data/testops.db` SHA-256 **before**: `99f30117419ce8a2e7baba5bc11b66e7b795040828a7ce777e782e865d488d65`
- `data/testops.db` SHA-256 **after** (final re-hash at end of review): **identical**
- The live file was only ever read. All work ran on copies: `live_copy.db`, `pre_backup.db`
  (the `bak-before-projects-services-20261122` file, verified v3), `rerun.db`, `killed.db`,
  `from_backup.db`, `secret_data/`, `ac7_data/`.
- Suite: `env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1 .venv/Scripts/python.exe -m pytest -q`
  → **439 passed** in 89.89s.

## Migration safety — re-run, interrupted, from backup

- **Re-run on an already-migrated copy**: `rerun.db` (copy of the live v4 store) run through
  `migrate.prepare` again → returns 4, and the file is **byte-identical** afterwards
  (`99f30117…` both sides). `executescript` is a no-op, `_seed_projects` sees rows and leaves.
- **Interrupted**: `killed.db` (copy of the v3 backup) with the seed patched to insert a project
  and one service row and then `os._exit(9)` before any commit. Reopened: still v3, 0 project
  rows, 0 service rows, 46 runs, 2310 claims, `pragma integrity_check` ok — SQLite rolled the
  uncommitted seed back; the store stayed usable, and a clean re-run produced v4 with all
  4 projects and 12 services. Note the seed commits once, at the end, so a crash cannot
  strand a partial seed. (A separate observation: `db.connect()` migrates silently on open,
  so *opening* the live store with any build upgrades it — the forward-only refusal is the
  only guard, and it is a good one: the main checkout's code refuses a v4 store with
  `SchemaTooNewError`.)
- **From the backup**: `from_backup.db`, a copy of the v3 `bak-before-…` file, migrated
  forward → v4, projects `cotw, reqoverflow, restfulbooker, testops`, exactly 12 services
  (cotw: product+test repos, Jira COTW, ADO pipelines #2 and #4; testops: both repos + TOPS;
  the two no-Jira specimens carry their two repos each). 46 runs intact. AC1's migration is
  faithful.

## AC2 — pages compared, method, differences

Method: a v3 copy of the backup was rendered by a `git worktree` checkout of `main`
(11ee6f0, the pre-change build) at `TESTOPS_HOME` pointed at the v3 copy; the same bytes were
then migrated in place by this build and re-rendered by this build at the same store. That
avoids the two-variables trap and also keeps the old build's forward-only refusal happy —
the old build cannot read a migrated store, correctly.

Rendered and compared with `cmp`/`diff` (raw, then with the relative-time strings of
`app.age()` normalised, since two renders minutes apart cannot agree on "33 minutes ago"):
**16 case pages**, `index`, `runs`, and 5 run pages — 23 files.

- Raw: the **only** differences anywhere were `age()` sentences (`33 minutes ago` vs
  `32 minutes ago`) on `index.html`, `runs.html` and three run pages.
- With those time strings normalised: **every file byte-identical** — all 16 case pages,
  the index, /runs and all run pages. AC2 holds, by direct render rather than by trusting the
  fixture manifest (which the suite also checks, against `fixtures/projects_services`).

## Secrets — each probe and the verdict, and which way it errs

All probes by HTTP POST to `/config/services` against a running server on a scratch copy,
verified to return HTTP 400 and to leave the store empty of the row.

| probe | result |
|---|---|
| 40-char GitHub token (`ghp_…`, 40 chars) in `settings.repo` | **REFUSED** — "looks like a high-entropy secret (32+ characters, no separators)"; row absent from store |
| base64 AWS key (`wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`) in `settings.repo` | **REFUSED** — but as a malformed repo, *not* as a secret: the value contains `/`, which is exempt from the secret check (see below) |
| the same base64 key in a free-text `settings.board` field (direct POST) | **ACCEPTED and stored** — false negative |
| value containing `Bearer ` | **REFUSED** — "it contains 'bearer'" |
| password-shaped value (`password1`) | **REFUSED** — "it contains 'password'" |
| Jira host `https://jira.example.com` | **ACCEPTED** (303, row stored with host) — required to pass |
| 32-char project key `XXXX…` (32 X) | **ACCEPTED** — required to pass |
| 32-char mixed key `COTW-PROJ-KEY-0123456789-ABCDEFG` | **REFUSED** as high-entropy — false positive on a plausible key |
| field named `api_token` (unit level) | **REFUSED** by name |

Which way it errs: **both**. It over-flags long mixed-case strings (a legitimate 32-char key is
refused), and the `/`-in-value exemption means any secret that happens to contain a slash —
which is exactly what base64 does — sails through any free-text settings field. In the shipped
form the only slash field is `repo`, which the `owner/name` regex constrains, so the practical
exposure is a hand-crafted POST or a future settings field; row id 15 in my scratch store holds
the full AWS key to prove it. Also correct: no rejected value is echoed — the refusal page and
errors name the field and reason, never the value; the token string appears nowhere in the
store file, and the server writes no request logs (`log_message` is silenced).

## Config page — injection results, and removing a service a run used

- Project named `<script>alert(1)</script> & "quoted" — dash` added via POST (HTTP 303).
  `/config` renders it as `&lt;script&gt;alert(1)&lt;/script&gt; &amp; &quot;quoted&quot; — dash`
  — escaped, quote intact, em-dash intact (UTF-8), no live markup.
- A service named `<img src=x onerror=alert(2)>` renders escaped in the summary and
  re-escaped into the edit form's `value=""` attribute.
- A 200-char name (200 A's + the script tag) is accepted and rendered escaped, layout intact.
- The index and /runs do not print project *names* (they use the slug from run/case rows), so
  the escaped `/config` render is the only surface — checked, no raw occurrence anywhere.
- **Removing a service a run used**: deleted cotw's product-repository service (id 1) via
  POST. Run count (46), claim count (2310), finding count and `foreign_key_check` all
  unchanged; the run page `cotw-levels-20261122T204947` still renders (HTTP 200) with its
  claims and its "could not consult" record, and its case page still renders. Evidence is
  not config — AC3's removal path honours that.

## Three sharpest concerns

1. **The `/` exemption in `_looks_like_secret` is a hole, not a refinement** (`services.py:80-82`).
   Base64 — the single most common credential encoding — always contains `/`. My probe stored a
   complete AWS key in a free-text field. The guard errs over-strictly on long keys while
   missing base64. Base64-aware detection (charset check before the exemption) closes it.
2. **`db.connect()` migrates the store on open.** Any command run in the repo directory upgrades
   the live store without a prompt; the only protection is the forward-only refusal of *older*
   builds. A future reader who wants to inspect a v4 store with the build of a week ago gets a
   refusal — correct — but nothing ever asks before upgrading forward. Worth a printed line
   ("migrated v3 → v4") in the eventual CLI.
3. **The build report for the largest change so far was never written.** The ticket's process
   assumed a builder report to distrust; there is none. The work turned out to be sound, but a
   change this size going unreported is the failure mode the factory exists to catch.
