# TESTOPS-80 review — the routes tag answers from the surface reader

Reviewer: independent, worktree `C:/Users/<name>/Projects/testops-t80`, branch
`factory/testops-80-band-truth` at `c7ca1c9`. Nothing outside this worktree was touched; the store
was copied to scratch and served on 127.0.0.1:8793 (8791 never approached).

## Verdict

**Changes requested — one defect, fix before merge; the substance of the ticket is right.**

The fix is the right fix: the band's routes tag is now computed from the snapshot's own
`surfaces` record (`queries.product_routes_tag`), the test-ecosystem detector is out of the band,
the count is the reader's own, and the real demo-booking page — rendered by me on a copied store —
says `142 .java parsed, 25 routes, consulted` with no `169` and no `reqnroll` anywhere. The
contradiction the ticket was written for is gone on every case of run
`demo-booking-levels-20261124T114627`, and store-wide: zero case pages pair a repeats-product
sentence with a not-consulted routes tag.

The defect: the block that appends the routes tag is indented **inside the `for claim in claims:`
loop** (`testops/queries.py:689-697`). Verified by execution, not by reading alone:

- a case with **two claims** renders the Product routes tag **twice**;
- a case with **zero claims** (but a product arm and `code` in the analyser's needs) renders **no
  routes tag at all** — the tag the fix exists to write is silently dropped.

Every case in the copied store and every test in `tests/test_case_source_band.py` has exactly one
claim, so neither shape is exercised anywhere. That is the same class of fault the ticket names: the
page not saying what the verdict rests on. The fix is mechanical — dedent the block one level out of
the claim loop (it reads only `meta`, `examined`, `needs`, `product_repo`) — plus a two-claim and a
zero-claim test. Everything else below is sound.

## The three states, pinned or not

Each state's sentence, as rendered by this branch (my own renders against constructed snapshots
carrying the real-shaped `surfaces` record, and for `found` against the real store):

- `found` — `Product routes | example-org/demo-booking-platform | 142 .java parsed, 25 routes | consulted`
- `zero` — `Product routes | o/p | 142 .java parsed, no routes found | consulted`
- `not_assessable` — dimmed `tag unconsulted`: `not consulted` + the reader's reason verbatim
  (`the product repository holds no file it can read: 23 .ts, 4 .js`)

Pinned **by page tests**: `test_the_routes_tag_reads_the_surface_reader_and_says_what_it_parsed`,
`test_a_reader_that_read_the_files_and_found_no_route_says_so`,
`test_a_product_the_surface_reader_could_not_read_keeps_the_readers_reason` — each builds a
snapshot fixture that genuinely carries a `surfaces` record, renders the real `app.case_page`, and
asserts the exact sentence. That satisfies AC1's "pinned per state" as AC5 defines the pin (a page
test per state). Not a FAIL.

But the reviewer's suspicion is half-right and worth stating plainly: **no checked-in golden pins
any of the three states.** All 14 goldens under `tests/fixtures/projects_services/` render from
fixture snapshots that predate the `surfaces` record — of the 31 snapshots in this worktree's
copied store, 26 predate it, and the golden fixtures are of that generation — so
`test_every_case_page_and_the_indexes_are_byte_identical_after_the_migration` exercises only the
fourth state (no record → no tag). The states are tested, not golden-pinned; a future rendering
regression in exactly these three sentences would be caught by the three tests, never by the
byte-identical golden. If the Lead's bar is golden-pinning, that is a gap to close in a follow-up,
not in this ticket.

## The real page

Snapshot `demo-booking-levels-20261124-fe8537db`, run `demo-booking-levels-20261124T114627`,
13 cases, 1 claim each. Copied store served on port 8793;
`/case/case-demo-booking-levels-20261124T114627-05` renders:

    Product routes   example-org/demo-booking-platform   142 .java parsed, 25 routes   consulted

- The band's snapshot meta: `surfaces` = `{state: found, parsed: 142, surfaces: 25, languages:
  [.java 142, .ts 23, .js 4]}` — the tag's numbers are exactly the record's.
- `169` absent, `reqnroll` absent from the page. The only `not consulted` occurrence on the page is
  inside a CSS comment.
- The verdict sentence `already declares POST /` is present, beside a consulted routes tag. No
  contradiction.
- All 13 cases of the run: no repeats-product verdict beside a not-consulted routes tag. Store-wide
  sweep over every case in the copied store: zero contradictions. The 23 Nov run
  (snapshot `demo-booking-levels-20261123-fe8537db`, `surfaces` = `not_assessable`, the run the
  reader could not parse Java on) renders the dimmed tag with the reader's own reason — honest, not
  the detector's sentence.

## Attacking the fix

- **`zero` state with a .java product arm** (`state: zero, parsed: 142, surfaces: 0`): renders
  `142 .java parsed, no routes found`, consulted. Honest — read and found nothing is a reading.
- **No product arm at all**: no routes tag, plus the sentence `Assessed against test code only: the
  product's routes could not be consulted, because the run recorded no product repository.`
  Honest — there is no routes fact to give.
- **Pre-`surfaces` snapshot (the old Demo Product runs — 26 snapshots in this store)**: no routes tag at
  all. I swept every case on every such snapshot: none carries a repeats-product verdict today, so
  nothing in the store lies. The protection is the band's `absent_note` sentence; a future old
  snapshot whose verdict rests on routes would show the verdict with no routes fact beside it —
  silence, not a lie, and the design says so rather than inventing "not consulted". Defensible.
- **Demo Product `a3f19853-r11` (has a record)**: renders `45 .py parsed, 47 routes`. The number is right
  and the word is not quite: `surfaces` in the record counts **engine-module surfaces too**
  (`discover.py:301` appends `modules` to the route list), so `47 routes` overstates routes. On
  demo-booking (25 pure API routes) the ticket's own wording happens to hold; on Demo Product it does not.
  See concerns.

## One place

One place. `queries.product_routes_tag` (and its helper `_parsed_languages`) is the only code that
answers "were the product's routes read" for the band; `source_band` only appends its result, and
`web/app.py:source_band_block` only renders tag dicts it is given. I grepped for a second
implementation: the ecosystem record is no longer consulted anywhere in the band; the other
`surfaces` consumers (`pipeline.py` run stats `surfaces_state/reason`, `queries` run-detail facts,
`level_fitness`'s per-claim product record) answer different questions and do not assemble band
facts. AC4 holds.

## Goldens

- Suites reproduced: full suite **1233 passed, 2 skipped** (2:52); contracts **37 passed, 2
  skipped** — both with the required env stripped.
- `git diff origin/main...HEAD -- tests/fixtures/projects_services/` is **empty**: no golden
  changed, confirming the build's claim. The reason is the one stated above — the fixture snapshots
  predate the `surfaces` record, so the band on every checked-in golden renders no routes tag and
  renders it identically before and after. Nothing to list, and nothing hidden: the diff is clean.

## Three sharpest concerns

1. **The claims-loop nesting (`queries.py:689-697`) is a real defect.** Two claims duplicate the
   tag; zero claims drop it while the verdict may quote routes. No test and no stored case has
   claims ≠ 1, so the suite is green and the store is clean purely by coincidence of shape. Fix and
   add the two shapes before merge.
2. **"Routes" is said where the record counts surfaces.** `surfaces` = routes + engine modules
   (`discover.py:301`); Demo Product renders `47 routes` for a count that includes module surfaces. The
   band should say what the number is (surfaces), or the record should carry the split.
3. **The three states have no golden coverage, and the fourth (no record) is the only one the
   goldens pin.** Combined with concern 1 — whose triggering shapes no test holds — the ticket's
   safety net for exactly the sentence it changed is three tests and nothing else. Cheap insurance:
   one golden with a `surfaces` record in a follow-up ticket.
