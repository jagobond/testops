# TESTOPS-54 — build: every page leads somewhere

Delivered branch: `factory/testops-54-navigation` (worktree `C:/Users/<name>/Projects/testops-t54`).
Build run: 2026-11-23 (system clock); report filed under the path the brief named.
Interpreters: `C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe` with `PYTHONPATH`,
`VIRTUAL_ENV`, `CONDA_PREFIX` stripped and `PYTHONNOUSERSITE=1`.

## What changed

Product code — `testops/web/app.py`, two edits:

1. **`SITE_NAV`, rendered by `page()`** (the wrapper every page goes through: front, runs index,
   run, stale run, case, stale case, config, config refusal, 404). One footer nav on every page:

   ```
   ← all cases · all runs · projects and services          (/ · /runs · /config)
   ```

   It is in the shared wrapper, not per template, so no page can be added later that forgets it.
   One affordance, the same words, everywhere (AC2).

2. **The case page names its run** (AC1). Under the badge line, for a case that carries findings:

   ```
   Raised by the run <a href="/run/<run id>"><run id></a> — what that run analysed, and what it
   could not consult.
   ```

   The link text is the run id inside a sentence that says what it is; there is no bare "back".
   The row that raised no finding already named its run since TESTOPS-34; that paragraph is
   unchanged.

Tests — new `tests/test_navigation.py` (4 tests, one per AC), plus the goldens regenerated.

## AC by AC

**AC1 — a case links to its run, across three projects.** `test_a_case_page_links_its_own_run_and_the_link_says_what_it_is`
renders a case from `cotw`, `reqoverflow` and `restfulbooker` (one per project, and both registered
analysers: `level_fitness` and `duplication`). For each it asserts the case page's parsed hrefs
contain `/run/run-case-<project>`, that the anchor's visible text is the run id, and that it never
says "back". The build registers two analysers, not three, so "a case from each analyser" is
covered as far as the build allows and the test pins that both are exercised.

**AC2 — `/config` from every page, same affordance.** `test_every_page_offers_the_same_visible_way_to_configuration`
fetches `/`, `/runs`, a run, a case, `/config` and a 404 page from a live ephemeral server and
asserts each carries a `/config` anchor with non-empty visible text, and that the set of
(href, text) pairs is **identical** on every page.

**AC3 — the round trip.** `test_run_to_case_and_back_to_the_same_run` takes the run page, follows
its first `/case/...` link, follows the `/run/...` link found on the case page, and asserts it is the
same run URL and that the run page still lists that case. It only ever follows hrefs it parsed out
of the page; nothing is constructed.

**AC4 — no new dead ends.** `test_every_internal_link_on_every_page_resolves` crawls from `/` over
every internal href, then checks the hrefs of front, runs, run, case and config individually, and
requires HTTP 200 for each. External (GitHub) hrefs are out of scope, as the brief says.

**AC5 — contract suite.** TESTOPS-53 has **not** landed (the suite still defaults to
`http://<tailnet-address>:8791`), so the suite was run only with `TESTOPS_BASE` pointed at a **copy of
the store in a scratch directory served on an ephemeral port**. Baseline and branch were run against
the *same* copy, at 63970 (HEAD) and 63796 (this branch):

| run | code under test | result |
|---|---|---|
| baseline | `git archive HEAD` tree | **4 failed** — P05 case-links-to-run, P05 config-reachable, P07, P10 — 22 passed, 3 skipped |
| branch | this worktree | **2 failed** — P07, P10 — **24 passed**, 3 skipped |

P05 both tests go fail → pass. Nothing else moves: P07 and P10 fail identically before and after,
and are outside this ticket (they are the sorted front-page counts and the per-kind read counts).

Goldens: `tests/fixtures/projects_services/*.html` regenerated (15 pages) from the same
pre-v3 store, migrated, with `age` frozen, exactly as `test_projects_services.py` renders them.
The visible-text diff of every golden is **additions only** — no removed text anywhere:

```
== case-page-01.html
   +Raised by the run
   +run-01
   +— what that run analysed, and what it could not consult.
   +← all cases
   +·
   +all runs
   +·
   +projects and services
== index.html / runs.html / case-page-09.html (the row with no finding)
   +← all cases
   +·
   +all runs
   +·
   +projects and services
```

case-page-02..08 and 10..12 read exactly like case-page-01 with their own run id. The only visible
text the regeneration adds is the new link labels and the run-origin sentence.

## Witness (the tests would have caught the fault)

The four new tests were run against the `git archive HEAD` tree (product code without this change):
**3 failed, 1 passed** — AC1, AC2 and AC3 fail with "no link to its run", "no link to /config" and
"the round trip landed on []". AC4 passes on both trees by design: it is the guard that stops *new*
dead ends, not a witness of the old ones.

## Suite

`pytest -q --ignore=tests/contracts`: **697 passed**, exit 0. The contract file is excluded from the
plain run for the reason above — until TESTOPS-53 lands, a bare `pytest` still points the contract
suite at the live server, which this ticket must not add to.

## Disclosed incident

Before switching to a copied store, the first exploratory `pytest` on HEAD (not this change) let
`tests/contracts` run against the live server on 8791 and it created one empty project,
`contract-audit-20261123144427` (no services, no runs, no snapshots, no cases). It was removed with
the product's own `services.remove_project`; the live store now lists only
`cotw, reqoverflow, restfulbooker, testops`. No other live write was made. This is the hazard
TESTOPS-53 exists to close, and the reason every contract run here was on a copy.

## Files

- `testops/web/app.py` — `SITE_NAV` + footer in `page()`; the case page's run line.
- `tests/test_navigation.py` — new, 4 tests (AC1–AC4).
- `tests/fixtures/projects_services/*.html` — 15 goldens, links only.

## Amendment (review, 2026-11-24) — three changes, nothing else touched

The review passed the ticket with three amendments. All three are made here; the contract suite's
assertions are untouched, and every run below used a temp store on an ephemeral port.

**(1) Wording: "configure projects and services".** The nav read "projects and services", which
named the page's content rather than the action. One string in `SITE_NAV`; all 14 goldens
regenerated (`index.html`, `runs.html`, `case-page-01..12.html`) from `before_v3.db` with `age`
frozen, exactly as `test_projects_services.py` renders them. Visible-text diff, extracted with
`html.parser` and compared token by token against the committed goldens: **one token added per
page, nothing else added or removed**:

```
== case-page-01.html: 385 tokens -> 386
   +configure
```

…and identically for the other 13 pages (`case-page-02` 387→388, `case-page-09` 171→172, and so
on). No page changed in any other way.

**(2) The unguarded run link.** `case_response` now asks the store whether the run is still there
(`queries.run_read`) and emits the `/run/<id>` anchor only when it is:

```
run_present = bool(row.get("run_id")) and queries.run_read(conn, row["run_id"]) is not None
```

The findings branch and the "this row raised no finding" branch both consult it. When the run is
gone the page still answers 200 — the case row is what the address is about — and says the run is
not in the store any more, in place of the link, so a reader is never sent to a 404.

New test `test_a_case_whose_run_is_gone_says_so_instead_of_linking_a_dead_page` manufactures the
orphan exactly as the review did: it seeds two cases (one with findings, one without), then points
both `run_id`s at `run-deleted-forever` with `PRAGMA foreign_keys = OFF` on a connection to the
temp store. It asserts each page answers 200, carries no `/run/run-deleted-forever` href, names the
run, says it is gone, and that **no href on either page answers anything but 200**.

Witness: with `testops/web/app.py` stashed (product code as merged before this amendment) the test
fails on `assert '/run/run-deleted-forever' not in hrefs(body)` — the reviewer's exact finding.

**(3) AC4 now sweeps form actions.** `test_every_internal_link_on_every_page_resolves` keeps the
href crawl and adds a form sweep: every `<form action>` on every page the crawl reached (plus the
five fixed pages) must be an internal address, and a GET on it must not be 404 or 5xx — a POST-only
target may answer 405, since the address exists and only the method does not.

That required one product change to be true rather than merely asserted: the POST-only addresses
(`/config/projects`, `/config/services`, `/config/service/<id>`, `/config/service/<id>/delete`,
`/config/project/<slug>/delete`, `/case/<id>/state`) previously answered **404** to a GET. They now
answer **405** with `Allow: POST`, from one tuple of patterns (`POST_ONLY`) beside `Handler`.
Nothing about the POST behaviour itself changed; `do_POST` still dispatches on the same paths.

Witness: with `app.py` stashed, the form sweep fails with six lines of the form
`the page /config posts a post form to /config/project/cotw/delete, which returned HTTP 404`.

**Suite after the amendment:** `pytest -q --ignore=tests/contracts` → **698 passed** (the 697 from
the build plus the new orphan test). No contract test was run against any live server.

**Files touched by the amendment**

- `testops/web/app.py` — nav wording; the `run_read` guard on both run-link branches; `POST_ONLY`
  and the 405 answer for a GET on a form target.
- `tests/test_navigation.py` — `_Forms`/`form_actions` parsers, the `served` fixture split so a
  test can manufacture the orphan (the `live` fixture now takes its URL), the form sweep in AC4,
  and the orphan test.
- `tests/fixtures/projects_services/*.html` — 14 goldens, the word "configure" only.