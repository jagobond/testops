# TESTOPS-54 — review: every page leads somewhere

Reviewed on branch `factory/testops-54-navigation`, worktree `C:/Users/<name>/Projects/testops-t54`
(build commit 9cd8c83). Every check below was run against a **copy** of `data/testops.db` served on
127.0.0.1:8477 (`TESTOPS_DATA` pointed at the copy); the live store and port 8791 were never
written. One process note, disclosed in full: the first server launch silently fell back to the
repo's `data/` directory (env quoting), and for a few minutes two servers were double-bound on the
same port (Windows SO_REUSEADDR), which made early probes inconsistent. I killed both and re-ran
every stateful check against the single clean server on the copy. The first accidental exposure was
read-only crawling; no request in this review wrote to the live store.

## Verdict

**PASS** — with one wording amendment to make in this ticket before merge (see ## The wording), and
one latent dead end recorded as a concern rather than a failure (see ## Three sharpest concerns).
All five acceptance criteria hold on the evidence below, including the every-page crawl the brief
asked for and the build's own tests did not attempt.

## The nav, on every page (crawled 242 pages)

Crawl from `/` following `<a href>` links only, HTML parsed with `html.parser`, nothing
constructed: **242 distinct pages**, every one HTTP 200. On **every** page the footer nav is
present with all three anchors and their exact visible texts (`← all cases` → `/`,
`all runs` → `/runs`, `projects and services` → `/config`). nav_missing: none.

Every internal href seen anywhere on the crawl was then fetched individually: **zero non-200s**.
The GitHub links were excluded as the brief excludes them.

The pages a link-follow can never reach were checked directly, since they are exactly the ones a
per-template implementation would forget:

- `/case/definitely-not-a-case` — 404 page: nav present, all three anchors.
- `/run/definitely-not-a-run` — 404 page: nav present.
- The config-refusal page (a case naming an analyser this build does not register, tested by
  setting a copied row's analyser to `legacy_unknown`): 404, refusal prose intact, nav present.

The build's structural claim is true: the nav lives in `page()`, so no page can be rendered
without it.

## The case-to-run link

Verified on real cases from all three projects in the store (demo-product, demo-service, demo-booking) and
both registered analysers (`level_fitness`, `duplication`) — three project/analyser combinations,
each checked live:

- `case-demo-product-levels-20261120T194425` → `/run/demo-product-levels-20261120T194425`
- `case-demo-service-dup-20261120T153431` → `/run/demo-service-dup-20261120T153431`
- `case-demo-booking-levels-20261123T132456-01` → `/run/demo-booking-levels-20261123T132456`

The anchor text is the run id inside the sentence "Raised by the run <id> — what that run analysed,
and what it could not consult." That is not a bare "back" and not a bare id: the sentence names
what the link is. Judged as a reader: the link says what it is and where it goes.

The promise fails honestly where the build said it already held: all four no-finding rows in the
store (e.g. `case-demo-product-dup-20261120T153507`) also link their run, under the TESTOPS-34 sentence
"This row raised no finding, so it is not a case. The run it recorded is <id>." Unchanged by this
ticket, and carrying the link.

## Round trip and the stale case

Programmatic round trip on two runs (`demo-product-levels-20261122T000930`,
`demo-product-levels-20261121T215534`): run page → first `/case/...` href parsed from it → case page →
`/run/...` href parsed from that → **the same run URL** both times, and the run page still lists
the case. No URL was constructed at any step.

Then I tried to break it. The store holds no case whose run is gone (retention deletes the case,
its findings and the run together, and the schema's foreign key blocks a hand edit through the
product), so I manufactured the state in the **copy** only (foreign keys disabled): a case row
whose `run_id` names a deleted run. Result: the case page renders **200** and links
`/run/run-deleted-forever`, which returns **404**. That is a dead end the promise does not survive
— the link is emitted on `row.get("run_id")` alone, without checking the run is still in the
store. I record this as a concern, not a failure: the state is unreachable through the product's
own writes today (the TESTOPS-24 deletion path removes case and run together, and the FK refuses
anything else). But the page has no guard, and the guard is one line. The genuine stale-case page
(a case id the store does not hold, and the unregistered-analyser refusal) links no run, says
plainly why the evidence is gone, and carries the nav — no dead end there.

## Goldens

Visible-text diff of all 15 regenerated goldens against the pre-ticket tree (`HEAD~2`), extracted
with `html.parser` and compared token by token: **additions only, nothing removed, on every
golden**. The added text is exactly:

- every page: `← all cases · all runs · projects and services` (the nav line)
- case pages with findings: `Raised by the run <id> — what that run analysed, and what it could
  not consult.`
- `case-page-09.html`, the no-finding row: the nav line only — confirming the build's claim that
  the no-finding sentence and its run link predate this ticket.

No other text moved on any page.

## Contract suite

Run with `TESTOPS_BASE=http://127.0.0.1:8477` against my copy (never bare; TESTOPS-53 has not
landed): **2 failed, 24 passed, 3 skipped** — exactly the expected shape. All three P05 tests pass
(`front_reaches_run_and_run_reaches_case`, `case_links_back_to_its_run`,
`config_page_is_reachable_from_the_front_page`); P07 and P10 fail as before, outside this ticket.
The product suite excluding contracts: **697 passed**.

## The wording

Judged as a reader who has never seen the tool: **"projects and services" does not say that this
is where configuration lives.** It names what the page is *about*, not what you can *do* there,
and a reader looking for "settings" or "configure" will not follow it. AC2 asks for a link a
reader can see **and understand**; the seeing is proven, the understanding is half-earned. The
build is right that naming the page's content beats a bare "config", but the fix costs one word:
"configure projects and services", or "projects and services (configuration)". Per the brief this
is small enough to fix here rather than in a follow-up — it is one string in `SITE_NAV` and a
golden regeneration, and I would not merge the ticket without it.

## Three sharpest concerns

1. **The wording above.** "projects and services" hides the configuration behind a noun phrase;
   one word ("configure …") fixes it and belongs in this ticket.
2. **The unguarded run link.** The case page emits `/run/<run_id>` whenever `run_id` is set,
   without checking the run exists. Unreachable through product writes today, but a hand-imported
   row or a future retention change turns it into a 200 page linking a 404 — the exact dead end
   this ticket exists to forbid. A one-line existence check (or linking only when
   `queries.run_read` finds it) closes it permanently.
3. **AC4's blindness to forms.** The dead-end sweep (in the build's test and in mine) follows
   `<a href>` only; the decision form's `action` URLs and the POST paths under `/config` are
   outside it. A malformed form action would pass AC4 today. Not a regression of this ticket —
   the sweep was always link-shaped — but the next nav-adjacent ticket should widen the sweep to
   form actions.
