# TESTOPS-51 build — one screen for every field, and a project that can be deleted

Builder run, 2026-11-23. Worktree `C:/Users/Chester/Projects/testops-t51`, branch
`factory/testops-51-credential-screen`. Interpreter, everywhere below:

    env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1 C:/Users/Chester/Projects/testops/.venv/Scripts/python.exe

No product code was edited outside this ticket, no contract test was edited, and the live store
(`data/testops.db`) and the live server on 8791 were not touched.

## What changed

- `testops/services.py`
  - The credential rules are one screen (`_looks_like_secret`) applied at the **store boundary**:
    `validate_settings` (every settings value and every settings key) and a new
    `refuse_credential_in` (every human-entered name). Detection is a *shape*, not a word:
    a `name=value`/`name: value` pair whose name is a credential word; issued-token prefixes; a PEM
    private-key block anywhere in the value; a JWT (three dot-separated segments beginning `eyJ`);
    an `Authorization` scheme (`Bearer ...`); and a short unbroken identifier naming a credential
    (`my-password`, `an-api-token`).
  - `add_project` screens the project slug and name; `_check_service` (used by both
    `add_service` and `update_service`) screens the service name. A field added tomorrow is
    covered because the check is on the way into the store, not on the form.
  - `remove_project` now refuses a project that holds runs, snapshots or cases, naming the counts;
    `evidence_counts` is the shared count. Only a project with no evidence is removed (its services
    cascade).
- `testops/web/app.py`
  - `/config` renders a per-project "Delete this project and its services" control whose text says
    runs, snapshots and cases are never deleted here, and names the counts when the project holds
    any.
  - `POST /config/project/<slug>/delete` applies it; a refusal is the existing 400 page.
- `tests/test_config_credential_screen.py` (new, 54 tests).

## AC1 — one shared check, applied at the boundary

`_check_service` screens the name and then `validate_settings` screens every settings value; both
`add_service` and `update_service` go through `_check_service`, and `add_project` screens both its
fields. The proof that a new field cannot opt out is a test that writes to a settings key that does
not exist (`{"a_field_added_next_year": <probe>}`) and is refused for four probe shapes.

## AC2 — refusal is HTTP 400, non-blaming, and nothing is stored or echoed

The refusal reads like the `repo` one: `the service name was refused: it reads as a credential:
the name 'password' is followed by '=' or ':' and a value. …` The value is not in the page, the
listing or the log line (the field/reason are logged, the value never is). Tests assert
`PROBE not in body` and `PROBE not in get("/config")` and that the store holds no row.

## AC3 — detection

Pinned one probe per named entry: `password`, `passwd`, `pwd`, `token`, `api_key`, `apikey`,
`secret`, `bearer`, `authorization`, `private_key`, `access_key`, `client_secret` (in
`name=value`, spaced and quoted forms); `ghp_`, `gho_`, `ghs_`, `github_pat_`, `sk-`, `AKIA`,
`xoxb-`, `xoxp-`; a PEM block; a JWT. Also exercised over HTTP in the board, host, org and repo
fields.

## AC4 — false positives are pinned, one by one

All eleven values from the ticket are accepted and asserted individually (plus a service created
with three prose names). Two extra boundaries are pinned so a later tightening has to be deliberate:
`test_password_reset_flow` (a longer snake_cased label is a name) and `password-manager/tool`
(a repository coordinate is not a pasted secret). The old rule refused `test password reset flow`
because it contained the word "password"; that is now fixed, and the existing pinned refusals
(`my-password`, `an-api-token`, `Bearer abc123`, …) still refuse.

## AC5 — not bypassable through a second path

One test posts the probe to all three routes — create service, inline edit of an existing service,
create project — asserts 400 on each, and then reads the store: the only service is still named
"API tests" and the only project is still `team`. A refused value reached no row.

## AC6 — delete a project, or refuse with the counts

- No evidence: `POST /config/project/empty/delete` → 200, project gone, its services gone.
- With evidence: the test inserts one snapshot, one run and one case, posts the delete, gets 400,
  reads "1 runs", "1 snapshots" and "1 cases" in the page, and confirms the project and the run are
  still there.
- Unknown slug: `UnknownProject`, 400.
- This is the route that can retire the `contract-audit-*` accumulation the contract suite leaves.

## AC7 — contract suite

The suite has **no `--base-url` option**; it reads `TESTOPS_BASE` (`tests/contracts/…:30`). I ran it
against a **copy** of the store served on a free port, never against 8791:

    cp data/testops.db $SCRATCH/t51store/testops.db
    TESTOPS_DATA=$SCRATCH/t51store python -c "from testops.web import app; app.serve(<free port>)"
    TESTOPS_BASE=http://127.0.0.1:<port> … -m pytest tests/contracts -q -p no:cacheprovider

    before (pre-change tree): 6 failed, 20 passed, 3 skipped
    after:                    5 failed, 21 passed, 3 skipped

The delta is exactly `test_P23_password_in_free_text_field_is_refused`, which now passes. The five
remaining failures are the other promises (P04, P05 ×2, P07, P10) that TESTOPS-7 found and other
tickets own; none regressed. The live store was confirmed untouched: `contract-audit-*` rows = 0.

## AC8 — full suite and goldens

    676 passed in 146.64s

for `pytest tests --ignore=tests/contracts` (622 before this ticket + 54 new). No golden or case-page
fixture changed (`git status` shows only the two product files and the new test file).

Note on "full suite": a bare `pytest -q` also runs `tests/contracts`, which by design drives a live
server (default `http://100.121.128.21:8791`) and fails on the five promises above. That gate is
AC7's, run separately against a copy; it is not a product-suite failure.

## Red run

Stashing the two product files and running the new file against the old code:
`29 failed, 25 passed`. With the change: `54 passed`. The 29 failures are the new behaviour; the 25
that already passed are the AC4 pins and the pre-existing guard.

## Trade-off to know about

The "short identifier containing a credential word" rule still refuses a two-segment value such as
`password-manager` typed alone in a settings field (it was refused before this ticket too, by the
old substring rule). Prose, longer snake_cased labels and anything with a `/` are exempt, so the
ticket's whole AC4 list is accepted; a repository or host whose *name* starts with a credential word
should carry a `/` or a dot (which it always does in practice).
