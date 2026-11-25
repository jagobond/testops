# TESTOPS-52 review — verdicts wear a declared tone

## Verdict

**PASS.** The tone table does what the ticket says: declared once, exhaustive over every name the
store accepts, raised-not-guessed on an undeclared name, and rendered consistently on the served
pages. The live-store hazard is not fixed here and is not claimed to be — it is TESTOPS-53's to
fix, and this review verifies it is still present. The one genuine half-truth in the ticket's
story is the soft badge: it is defined, tested, and witnessed nowhere on a served page (see
below). That does not block the ticket — the tone contract is witnessed — but the record should
not claim the soft treatment has been seen end-to-end, because it has not.

## Tone, verified on served pages

The goldens (`factory/reports/2026-11-23/persisted-claim-case-page.html`,
`persisted-run-page.html`) show the rendered contract: every judgement headline and verdict badge
carries exactly the class suffix the tone table declares — `verdict` plain for settled,
`verdict hot` for alarm, and the visible text is byte-identical to what the pre-52 build rendered
(the tone work changed classes and colour, never words). The dashed/muted soft treatment is
CSS-defined in `app.py` and mapped in `tone.py` but appears as applied markup on none of the
served pages examined — see "The soft badge, unwitnessed".

## The 522 vs 542 (density)

Reconciliation, honestly: it is **not** simply crawl depth, and it is not a clean contradiction
either.

- Build's count: 522 malformed attributes across 46 pages = **11.35 per page**.
- This review's count: 542 malformed attributes across 258 pages = **2.10 per page**.

If the difference were purely crawl depth over the same population, the two densities would
agree; they differ by roughly 5×. So the two crawls sampled materially different page
populations — the build's 46 pages were far more malformed per page than the broader 258-page
sample. Both crawls therefore over-count *and* under-count different things, and neither absolute
number means anything on its own: **any absolute count of malformed attributes is
crawl-dependent**. The record should cite density, not a headline total — and even density must
be stated with its sample ("11.35/page over the 46 pages the build served; 2.10/page over the
258 pages this review crawled"). The shared, depth-independent finding both agree on: malformed
markup exists on served pages, in volume, on every sample either side took.

## Exhaustiveness

`tone_of` maps all 8 names the store accepts — 5 current (`distinct`, `review`, `gap`,
`duplicate`, `unplaced`) and 3 retired (TESTOPS-9's `necessary`, `optimal`, `overbuilt`), because
stored evidence can still carry the old names. No fallback: an undeclared name raises `KeyError`
with a message naming the verdict and pointing at `testops/web/tone.py`. `tests/test_verdict_tone`
iterates the store's own vocabulary, so a new store-accepted name cannot ship untinted.

## Goldens

Identical in visible text on all 14 pages against the pre-ticket render; the only diffs are class
tokens (`verdict hot` / `verdict soft` / plain `verdict`) plus their CSS. No prose moved, no
sentence reworded. This is the right shape of change for a tone-only ticket.

## Contract suite

21 passed / 5 failed / 3 skipped. **P4 (tone contract) passes.** The 5 failures are not new:
none of them is a sixth failure introduced by the tone work, and the live-store hazard (below)
is the known owner of this debt, tracked as TESTOPS-53.

## Analysers untouched

The analysers pin: 46 passed, unchanged. No analyser output changed, as expected for a
presentation-layer ticket.

## The live-store hazard (unfixed)

Not fixed by this ticket, and this review confirmed it survives the merge. TESTOPS-53 owns the
fix. The read-only verification below shows the store is in the post-scrub state the build
described — the hazard is that the live store's rows are one careless write away from being
unrewindable, not that the store is currently dirty.

## The soft badge, unwitnessed

The `soft` badge is CSS-defined (`.badge.verdict.soft`, dashed and dimmed) and unit-tested via
the tone table — but **no served page in the store copy exercises it**. The mechanism is in the
code: only claims whose verdict is in `RAISES = {"review", "gap", "duplicate"}` (`pipeline.py:36`)
become findings and therefore cases and pages. `unplaced`, the one current verdict whose declared
tone is soft, never becomes a case; a soft-toned page can only appear when a *raiseable* claim's
assessment was `not_assessable`, and no such claim exists in this store.

The store copy does hold the raw material — 351 `unplaced` claims — so the data is not the gap;
the case-formation rule is. To witness `badge.verdict.soft` end-to-end you need either:

1. a store row that forms a case carrying an `unplaced` verdict (requires changing the case
   formation rule — its own ticket), or
2. a case whose claim's assessment state is `not_assessable` with a verdict in `RAISES`
   (achievable with a crafted store, without code changes).

This review did not build either. Consequence stated plainly: **the tone work is only
half-witnessed.** The alarm and settled tones are witnessed on served pages; the soft tone is
witnessed only at the unit boundary. The verdict stays PASS because the ticket's contract (a
declared tone for every stored verdict name) is proven; the unwitnessed rendering should be the
first acceptance criterion of whichever ticket closes it.

## Live store, read-only verification

Opened `C:/Users/<name>/Projects/testops/data/testops.db` with `mode=ro` (URI-flagged; no write
possible):

- `project` holds exactly **4 rows: `cotw`, `testops`, `reqoverflow`, `restfulbooker`** — the two
  stray rows are gone, exactly as the build claimed.
- `run`: 47 rows, project values limited to `reqoverflow`, `cotw`, `restfulbooker`.
- `case_`: 208 rows, same three projects. The `testops` project is an empty shell (no runs, no
  cases) — expected, it is the product's own self-record.
- Claim verdicts present: all 8 vocabulary names. Write-checked by opening the connection
  read-only; nothing was written.

## Three sharpest concerns

1. **The soft tone has never been seen by a reader.** Defined, tested, mapped — and rendered on
   zero served pages, structurally unreachable because `unplaced` never becomes a case. Anyone
   quoting TESTOPS-52 as "every tone witnessed" is wrong; the record must say half-witnessed.
2. **The malformed-attribute numbers can't be quoted.** 522 and 542 are both true and both
   meaningless outside their crawl; even the densities disagree 5×, so the page populations
   differ. Only density-with-sample ("2.10/page over 258") is citable, and any future count must
   name its crawl.
3. **The live-store hazard is open and its ticket must actually land.** The read-only check shows
   a clean, post-scrub store — which is exactly the state that cannot be restored if the next
   scrub is a bad write. TESTOPS-53 is not optional follow-up; it is the standing risk this
   ticket deliberately left open.
