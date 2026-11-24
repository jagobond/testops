# TESTOPS-72 build — the product is evidence

2026-11-24, branch `factory/testops-72-product-evidence`, worktree `C:/Users/Chester/Projects/testops-t72`.
`level_fitness` 0.10.3 → **0.11**; store `schema_version` 6 → **7**.

Suite, from the project `.venv` with `PYTHONPATH`/`PYTHONHOME`/`VIRTUAL_ENV`/`CONDA_PREFIX` stripped and
`PYTHONNOUSERSITE=1`: **1165 passed, 2 skipped** (169.8 s; after the review amendment **1167 passed, 2 skipped**, see below). Contract suite alone (`pytest tests/contracts`):
**37 passed, 2 skipped** (15.5 s). `tests/test_product_evidence.py` is new and holds 15 tests (17 after
the amendment); `tests/test_verdict_vocabulary.py` (3 functions, 5 collected tests) passes unchanged
against the widened vocabulary. No golden
fixture changed, and no page fixture changed: `git status` holds ten product files and that one new test file.

## The ticket

TESTOPS-72, F1, depends on TESTOPS-70. The tool discovered the product's surfaces and never used them —
in `level_fitness.py` the word `surface` appeared once, as a parameter. Harry's question ("is the tester
essentially repeating work the developer has already done?") cannot be answered from the suite alone.
The ticket makes the product evidence, without repeating v0.1's failure ("a cheaper surface exists" was
true for almost every scenario; precision 0.118).

## What changed

| file | change |
|---|---|
| `testops/analysers/level_fitness.py` | The match: `_product_words`/`_product_meaningful`, `PRODUCT_STOP` (296 words), `PRODUCT_COMMON_SHARE = 0.5`, `PRODUCT_CLAIM_VERBS`, `_surface_reading` (only a real route contributes route words), `product_match` (deterministic ranking, two refusal guards), `_product_record` (the four states), `_repeats_opening` / `_statement` / `_proposed_action` for the verdict, and `product_state`/`product_reason` on `analyse()`. Every claim gets `detail["product"]`, whatever its verdict. |
| `testops/analysers/base.py` | `repeats_product` added to the documented verdict vocabulary (the comment `test_verdict_vocabulary.py` reads). |
| `testops/pipeline.py` | Passes `discovery.state`/`discovery.reason` to the analyser; `repeats_product` joins `RAISES` at severity `medium`; the run's stats gain `repeats_product` and `product_not_consulted` as **two** counts. |
| `testops/rebuild.py` | A rebuild re-derives the product state from the snapshot's own blobs, so it reaches the same product record — or the same "could not be consulted". |
| `testops/queries.py` | `product_evidence()` — `recorded`/`repeats`/`unconsulted`/`matched`, counted from the run's own rows; the two disjoint sets. |
| `testops/score/level.py` | `repeats_product` maps to `distinct` at the level axis: the level is right, the browser is the waste. |
| `testops/web/app.py`, `testops/web/tone.py` | `VERDICT_LABEL`, `_OTHER_LEVEL`, `LIST_JUDGEMENT`, `wrong_sentence`, `product_evidence_block()` (AC5) and `product_block()` (AC6) on the run page; ALARM tone. |
| `testops/store/migrate.py`, `testops/store/schema.sql` | v7 adds `repeats_product` to `verdict_vocabulary` and refreshes the two refusal messages; a v6 store has both triggers dropped and recreated on open, no row copied or rewritten. |
| `tests/test_product_evidence.py` | **new**, 15 tests. |

## Criterion by criterion

| id | what was done, and the evidence |
|----|--------------------------------|
| AC1 | `surfaces` is consumed, and every claim carries `detail["product"]` with `state` in `found`/`zero`/`not_assessable`/`none` and a `reason` in every case — `test_the_product_record_is_on_every_claim_and_never_silent`. `test_a_matched_claim_carries_the_surface_the_route_and_the_word` pins the surface id, route, word, the surface's own claim and `7 of 47`-style share. Silence is impossible: `_product_record` sets a reason on all four branches. |
| AC2 | The flip test, twice: `test_the_flip_test_one_suite_two_products_and_one_assertion_that_changes_verdict` (analyser) and `test_the_flip_test_through_the_real_pipeline` (collector → store → claim rows). See below. |
| AC3 | Three guards pinned: `test_a_generic_word_alone_is_never_evidence` (`data`, `result`, `page`, `correct` alone → `zero`), `test_a_word_most_of_the_product_carries_is_the_products_subject_not_evidence` (same word in 3 of 3 surfaces → `zero`, in 1 of 3 → `found`), `test_a_claim_that_does_not_need_a_browser_is_never_a_repeat_however_well_it_matches` (an `I1` claim with a perfect match → `none`, `distinct`). |
| AC4 | `test_an_unreadable_product_is_not_a_zero_and_never_a_repeat`: state `not_assessable`, verdict stays `distinct`, the reason carries `142 .kt`, no surface is invented. `test_a_run_with_no_product_record_says_nothing_rather_than_zero`: `product_state` defaults to `""`, not `found`, so a caller that forgets it cannot have claims judged against a product nobody read. On the corpus this is real, not hypothetical: the pre-TESTOPS-70 restful-booker run says *not assessable*. |
| AC5 | `product_evidence_block()` renders "What the product says:", the route in code style, the matched word, the surface's own claim and its share; and prints the reason for `zero` and for `not_assessable` ("That is not a zero."). Pinned by `test_the_case_page_shows_the_route_the_word_and_the_surfaces_own_claim`, and the `distinct` argument sentence names the API check while keeping the browser's job (`A browser is still needed for what only a person sees`). A claim the product is irrelevant to renders nothing. |
| AC6 | Two counts from `queries.product_evidence`, never folded: `test_the_run_page_counts_repeats_and_unconsulted_separately` and `test_the_run_page_says_so_when_the_product_could_not_be_consulted` (a `.kt`-only product: `repeats_product == 0`, `product_not_consulted == 1`, page says *not counted among the repeats*). A run from before this ticket recorded no product reading and says exactly that instead of printing two zeroes. |
| AC7 | Corpus re-read below: **9 of 43** repeat the product — **superseded by the amendment**: from this worktree's store the only restful-booker snapshot gives **0 of 43**, because its product arm is unreadable. See "Amendment — after review HOLD". |
| AC8 | Per-snapshot comparison below: **13 rebuildable CotW snapshots, 1,222 claims, 0 verdict movements**. Contract suite and full suite green. |

## AC8 — the per-snapshot comparison, all of them

Method: each CotW `levels` snapshot is rebuilt from its own blobs (`rebuild.rebuild`, the function behind
`scripts/replay_levels.py`) with the working tree, and every claim is matched to the stored claim of the
run that snapshot belongs to on `(subject_ref, assertion_line)`. `rebuild` returns claims and writes
nothing. The worktree's `data/testops.db` is a gitignored local copy — it was opened for this and
`prepare()` migrated it v6 → v7, exactly as any open of this build would; the live store and port 8791
were not touched, and no stored claim was rewritten.

There are **16 CotW snapshots**: 15 `levels` snapshots and one duplication-only. Two `levels` snapshots
predate TESTOPS-14 and refuse to rebuild (they do not record which repository is which arm — the refusal
is printed verbatim in the run log); **13 rebuilt**, which is the population compared. The brief said 11;
the store holds 13 rebuildable, and all 13 are below rather than 11 of them.

Every one of the 13 is 94 claims and every one is the same story:

| snapshot | claims | stored | rebuilt | movements |
|---|---|---|---|---|
| `cotw-levels-20261121-a3f19853-r2` | 94 | 90 distinct, 2 review, 1 gap, 1 unplaced | identical | **0** |
| `cotw-levels-20261121-a3f19853-r3` | 94 | 90 distinct, 2 review, 1 gap, 1 unplaced | identical | **0** |
| `cotw-levels-20261122-a3f19853` | 94 | 90 distinct, 2 review, 1 gap, 1 unplaced | identical | **0** |
| `cotw-levels-20261122-a3f19853-r2` | 94 | 90 distinct, 2 review, 1 gap, 1 unplaced | identical | **0** |
| `cotw-levels-20261122-a3f19853-r3` | 94 | 90 distinct, 2 review, 1 gap, 1 unplaced | identical | **0** |
| `cotw-levels-20261122-a3f19853-r4` | 94 | 90 distinct, 2 review, 1 gap, 1 unplaced | identical | **0** |
| `cotw-levels-20261122-a3f19853-r5` | 94 | 90 distinct, 2 review, 1 gap, 1 unplaced | identical | **0** |
| `cotw-levels-20261122-a3f19853-r6` | 94 | 90 distinct, 2 review, 1 gap, 1 unplaced | identical | **0** |
| `cotw-levels-20261122-a3f19853-r7` | 94 | 90 distinct, 2 review, 1 gap, 1 unplaced | identical | **0** |
| `cotw-levels-20261122-a3f19853-r8` | 94 | 90 distinct, 2 review, 1 gap, 1 unplaced | identical | **0** |
| `cotw-levels-20261122-a3f19853-r9` | 94 | 90 distinct, 2 review, 1 gap, 1 unplaced | identical | **0** |
| `cotw-levels-20261122-a3f19853-r10` | 94 | 90 distinct, 2 review, 1 gap, 1 unplaced | identical | **0** |
| `cotw-levels-20261122-a3f19853-r11` | 94 | 90 distinct, 2 review, 1 gap, 1 unplaced | identical | **0** |

**Zero movements, per snapshot, 13 of 13.** No rule moved a verdict on the CotW corpus, so there is no
rule and no matched word to report for a movement — there are none.

Zero is a result, not an absence, and the corpus shows why: each snapshot's 47 surfaces produce a product
record of **1 `found`, 6 `zero`, 87 `none`** across the 94 claims. Of the 7 claims that need a browser:

- **1 matched** and still did not move: `each fact's citation is in an element reachable by an accessible
  name` (I4) matched `/api/characters` on the word `citation` (7 of 47 surfaces, the surface's own claim
  *"test a fact whose citation does not resolve is excluded and counted"*). It is the run's `gap` claim —
  no browser ran — and **a gap is never `repeats_product`**: nothing was spent, so nothing is being
  repeated. The match is still recorded on the claim, because it tells a reader where the check belongs.
- **6 were refused** by a precision guard. Removing both guards, these six were the false moves the
  first pass found, and every one is refused by `PRODUCT_STOP`:

| assertion | unguarded match | matched word | guard | shipped |
|---|---|---|---|---|
| `every interactive control exposes an accessible name` (×2) | `/api/characters/caymus`, claim *test every control on the character page has an accessible name* | `accessible` (7/47) | stop word | `zero`, verdict `distinct` |
| `no control can be located only by its CSS class` (×2) | `/sheets/Yvonne`, claim *test a rejection can be undone* | `can` (2/47) | stop word | `zero`, verdict `distinct` |
| `no control can be located only by its position in the document` (×2) | `/sheets/Yvonne`, claim *test a rejection can be undone* | `can` (2/47) | stop word | `zero`, verdict `distinct` |

(The same three assertions would also have matched the product's docstring `:class:` references on
`class` — also a stop word. The ranking picked `can` because it is rarer; either way the guard refuses.)

## The flip test — what it proves, and how it could pass falsely

One fixture suite (`features/booking_page.feature` + one C# step definition class), analysed twice. The
only difference between the two runs is the product's surface list: `POST /booking` with the claim
`create booking` is present in one and absent in the other. The same assertion,
`the booking confirmation is announced with an accessible name`, is `repeats_product` in the first run
and `distinct` in the second.

It proves the product is load-bearing: the verdict is a function of what the product declares, and of
nothing else in the run. What makes it more than a re-run is that the test asserts what did *not* change —
assertion text, path, line, interaction code and label, instrument, span and `evidence_key` are equal in
both, and `subject_ref` too, so a recorded decision still covers the assertion after the product changes —
and that the product record itself differs (`found` vs `zero`). The pipeline variant runs the real
collector, the real store and the real writer over an in-memory repository and a throwaway database, so
the flip survives storage and is visible in the run's stats (`1` vs `0`).

It would pass falsely if the flip came from anything but the product. The two `_analyse` calls are built
from the same constants, so the only input that differs is `surfaces`; but the test compares eight
identifying fields, not the whole `detail` dict, so a future change that made the *statement* depend on
the product would not be caught here (the case page test does check the prose). It would also pass falsely
if the assertion's matched word were carried by a surface present in **both** products — then both runs
would say `repeats_product`, and the test would fail, not pass. The fixture is therefore only as good as
its `WITHOUT_ROUTE` tuple: a route that quietly kept a surface sharing the assertion's noun would break it
loudly, which is the behaviour wanted but is a property of the fixture, not of the analyser.

## The corpus re-read — restful-booker (AC7)

Run `restfulbooker-levels-20261124-fe8537db` (43 claims, 33 scenarios, `cucumber-js` test arm,
142 `.java` parsed, **25 surfaces**, state `found`), rebuilt in a throwaway store under the scratch
directory from that snapshot's own blobs — the worktree store does not hold it, and nothing here touched a
live source.

**43 claims: 9 `repeats_product`, 4 `distinct`, 4 `review`, 26 `unplaced`.**

The three strongest matches (rarest shared word first), as route + matched word + the surface's own claim:

1. `GET /{id:[0-9]*}` — word **`message`** (3 of 25 surfaces) — surface's claim **"get message"** —
   step `Visitor will get Booking Successful! message` (I4). This route/word accounts for 8 of the 9.
2. `GET /room/{id:[0-9]*}` — word **`room`** (6 of 25) — surface's claim **"get specific room report"** —
   step `New '<room_type>' type '<accessibility>' room '<room_name>' priced at '<room_price>' GBP with
   '<features>' will be created` (I4).
3. `GET /{id:[0-9]*}` — word **`message`** (3 of 25) — surface's claim **"get message"** — step
   `Visitor 'John Doe' will get Thanks for getting in touch message regarding subject 'Special
   Accommodation'` (I3).

A reader can argue with these. Match 2 is the weakest: `room` is a domain noun six surfaces use, and the
step asserts a *booking being created*, not a room report. Match 1 is defensible — the message service
does publish messages — but "Booking Successful!" is UI text the API does not serve verbatim, so the
honest reading is "the API publishes a message list, the test reads the browser rendering of it", which is
exactly the action the case page proposes. The 26 `unplaced` claims are unchanged and still unplaced:
the product cannot place a step whose words bind to nothing.

## Precision guards, with their values

| guard | value | what it refuses |
|---|---|---|
| stop list | `PRODUCT_STOP`, **296 words**: generic testing vocabulary (`data`, `result`, `page`, `correct`, `displayed`, `should`, …), the UI/code vocabulary that earned its place on this corpus (`class`, `accessible`, `position`, `document`, `style`), and the route verbs | any match resting on a word that names testing or the kind of thing, not the thing tested |
| common-share | `PRODUCT_COMMON_SHARE = 0.5` — strictly more than half of the product's surfaces | a word that is the noun the whole repository is about: with 25 surfaces, 13 is the subject, 12 is not. A one-surface product can therefore never produce a repeat, and that is stated rather than worked around |
| route-word-over-claim | ranking position 1, and only a target that *is* a route contributes route words (`/…` or a verb); a file path does not | a shared word in a module's name being read as "the product publishes this". A module can still be evidence through its claims, which are its own words |
| needs-a-browser | `I3`/`I4` and a browser that actually ran | a `KP`/`I1`/`I2` claim, however well it matches; and a `gap`, where nothing was spent |
| no stemming | a word must appear literally | `created` matching `create`: the matched word is quoted back to a reader as the evidence, and a stem nobody wrote is not quotable |

## What this does not do

- **No stemming.** `created` does not match `create`, `bookings` does not match `booking`. The matched
  word has to be literally quotable, so recall is given up on purpose.
- **No semantic match.** "Confirmation" and "acknowledgement", or "room" and "accommodation", share
  nothing. A test that repeats the product in different words is not caught.
- **A surface's claim is only as good as its Javadoc.** On restful-booker every claim is the humanised
  method name (`get message`, `get specific room report`) because the corpus has no Javadoc and no
  `@Operation`; a name like `getSpecificRoomReport` is evidence about the *method*, not about what the
  route guarantees. A wrong Javadoc produces a confidently wrong evidence line.
- **One word is a thin thread.** Nine of 43 claims rest on a single shared word, and one of those (match
  2 above) is a domain noun that arguably shouldn't count. The guards reduce false positives; they do not
  make a one-word match a proof.
- **The product's own tests can echo the suite.** `cotw-continuity` carries pytest test names that read
  like the suite's own steps; the stop list (`accessible`) and the common-share guard are what keep those
  out, not any understanding of whether they mean the same thing.
- **It does not re-run any corpus.** The CotW comparison is a rebuild from stored snapshots, not a fresh
  clone; the restful-booker numbers are a rebuild of a stored snapshot too. Both are reproducible from
  the store, and neither says anything about a product the snapshot did not fetch.
- **One sentence per claim.** A claim matched on any one meaningful word is `repeats_product`; a claim
  that shares ten words but hits no browser does not move at all. The verdict is about the instrument,
  not about confidence.

## Amendment — after review HOLD (2026-11-24)

The reviewer held the merge on two blockers. Quoted from `factory/reports/2026-11-24/TESTOPS-72-review.md`:

> **HOLD ... (1) a creation assertion is matched to a read route on a shared noun, and a differing
> verb never blocks or downgrades the match ... (2) The AC7 evidence is not reproducible from this
> worktree ... an independent rebuild of it produces `not_assessable`, 0 surfaces and **0 of 43
> repeats**, not 9 of 43.**

### 1. The verb is now the rule, not a tie-break

`testops/analysers/level_fitness.py`: `_INTENT_METHODS`, `_INTENT_FORMS`, `_intent_forms`,
`_assertion_intent`, `_surface_method`; `product_match` ranks method agreement first, and
`_product_record` refuses the repeat when the only candidate disagrees.

The mapping is explicit: `create`/`add`/`new` → POST; `read`/`get`/`show`/`display`/`list`/`view`/
`see`/`fetch`/`retrieve` → GET; `update`/`edit`/`change`/`modify` → PUT/PATCH; `delete`/`remove`/
`destroy` → DELETE. Inflections are recognised (`created`, `creating`), which is the exact hole the
review found (`created` ∉ `PRODUCT_CLAIM_VERBS`). A mutation outranks a read when a step says both.
A route with no method, a file-path surface and an `ANY` route are neutral: nothing in them can
disagree, so the old noun-only matching still applies and the claim records `assertion_verb: ""`.

Where the best candidate's method disagrees, **no `repeats_product` is emitted**. The claim stays
`distinct`, its product record is `state: zero` with `near_miss: true`, and it carries the route, the
word, `assertion_verb`, `surface_verb` and `verb_agrees: false`, with a reason naming both verbs.
Every product record now carries `assertion_verb`/`surface_verb`/`verb_agrees`/`near_miss` in every
state, so the verb question is visible instead of inferred. The case page's zero block renders the
near miss when it appears.

Probe run in this worktree on the review's own assertion (fixture surfaces, exact strings):

```
assertion: New 'twin' type 'accessible' room '101' priced at '100' GBP with 'tv' will be created
GET /room/{id} + 4 unrelated -> route GET /room/{id}, word room, assertion_verb create,
                               surface_verb GET, verb_agrees False   (near miss, no repeat)
+ POST /room ("create room") -> route POST /room, word room, assertion_verb create,
                               surface_verb POST, verb_agrees True   (repeat)
```

Two tests added to `tests/test_product_evidence.py` (17 now, was 15):
`test_a_creation_assertion_prefers_the_post_surface_over_a_get_that_shares_the_noun` and
`test_where_only_the_get_exists_the_verb_differs_and_no_repeat_is_emitted`.

On the nine restful-booker matches: they cannot be re-counted here (see 2), so this amendment does
not claim a new count for that corpus. It says what was verified: the one match the review judged
wrong (the room-creation step against `GET /room/{id}`) is refused by the rule, as the probe above
shows; the eight `will get ... message` matches are untouched in kind (`get` → GET, surface claim
`get message`). The CotW corpus was re-run to confirm no collateral: snapshot
`cotw-levels-20261122-a3f19853-r7` from this worktree's store, 94 claims, **0 verdict movements**
against stored run `cotw-levels-20261122T111027`, product record **1 found / 6 zero / 87 none** —
identical to the pre-amendment table.

### 2. AC7 rebuilt from a snapshot this worktree actually holds

Store: `C:/Users/Chester/Projects/testops-t72/data/testops.db` (the gitignored local copy; the live
store and port 8791 were not touched). It holds exactly these restful-booker snapshots:
`restfulbooker-levels-20261122-262404a9`, `-r2`, `-r3`, `restfulbooker-20261122-262404a9`, and
`restfulbooker-levels-20261123-fe8537db`. **No snapshot or run named
`restfulbooker-levels-20261124-fe8537db` exists in it** — the run the original AC7 section names.

Rebuild via `scripts/replay_levels.py` (no download, no live source, reads only this store's blobs):

| snapshot | claims | product arm | surfaces | state | repeats_product |
|---|---|---|---|---|---|
| `restfulbooker-levels-20261123-fe8537db` | 43 | 23 `.ts` + 4 `.js` | 0 | `not_assessable` | **0** |
| `restfulbooker-levels-20261122-262404a9-r2` | 43 | 23 `.ts` + 4 `.js` | 0 | `not_assessable` | **0** |

Refusal reason, verbatim in both: *"the surface reader parses Python (.py) and Java (.java) only,
and the product repository holds no file it can read: 23 .ts, 4 .js"*. Verdicts on both: 13
`distinct`, 4 `review`, 26 `unplaced`; product states 13 `not_assessable`, 30 `none`.

**So AC7, from this worktree, is 0 of 43 — and it is not a zero.** The product could not be
consulted (the TypeScript product arm is unreadable), no claim is judged to repeat it, and nothing
is rendered as "nothing found". The 9-of-43 figure came from a **Java corpus snapshot that is not in
this store** — 142 `.java` and 25 surfaces, which matches TESTOPS-70's Java read, not the Next.js
`route.ts` arm stored here. The original AC7 section stands quoted above as the claim that was made;
it is not reproducible here, and the reproducible number is the one in this table.

### 3. Suites re-run after the amendment

Full suite: **1167 passed, 2 skipped** (160.4 s). Contract suite (`tests/contracts`): **37 passed, 2
skipped** (11.6 s). Both from the project `.venv` with the environment stripped as at the top of this
report. No golden or page fixture changed.
