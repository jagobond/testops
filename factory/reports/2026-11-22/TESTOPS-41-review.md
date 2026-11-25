# TESTOPS-41 review — skipped is not consulted

Reviewed 2026-11-22 against branch `factory/testops-41-skipped-is-not-consulted` (149477b), tree clean.
Suite: `env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1 .venv/Scripts/python.exe -m pytest -q` →
**428 passed** in 69.7s. All evidence below is from my own probes and queries against the live store
read-only; none of it is copied from the build report.

## Verdict — PASS

The old lie is gone from every path I could construct: a skipped file can no longer be counted as
consulted, the three capability states render three different sentences, counts come only from
fetched files, and Demo Product/DemoService pages are byte-identical to the pre-change render.

## Sentences rendered — the four scenarios

I built each scenario as an in-memory GitHub tree through the real collector and the real
pipeline `_readings`, then rendered `Registry.assess(...).sentence()`:

1. **Legitimate zero vs skip-driven zero.** An empty product tree (nothing fetched, nothing
   skipped) beside a test arm gives state `found`: "Assessed: code and test code were consulted and
   returned 2 items." — and assessing `code` alone on that record gives the real-zero sentence
   ("consulted and returned nothing. That is a real zero"). A tree of 142 `.java` files gives state
   `not_assessable`: "Cannot assess this claim: code was not read: 142 .java files in the product
   repository were skipped because .java is not a kind this collector reads (unsupported kind), so
   no product code file was fetched; test code was consulted and returned 2 items." The two
   sentences differ, as required.
2. **Every file an unsupported kind.** 3 `.java` + 1 `README`: "Cannot assess this claim: code was
   not read: 3 .java files in the product repository were skipped because .java is not a kind this
   collector reads (unsupported kind), along with 1 more in 1 other kind, so no product code file
   was fetched; test code was consulted and returned 2 items."
3. **Size-cap sweep drops everything.** Five `.cs` files over `MAX_FILE_BYTES`:
   "Cannot assess this claim: code was not read: 5 .cs files in the product repository were skipped
   because they are over the 512 KB size cap (size cap), so no product code file was fetched; test
   code was consulted and returned 1 item."
4. **One kind skipped out of five.** A product repo holding `.py` (fetched) plus `.java`, `.rb`,
   `.go`, `.rs` (all unsupported) reads `found`: "Assessed: code and test code were consulted and
   returned 2 items." — see concern 3 below.
5. **Backwards compatibility (the required fifth).** A registry record with no `readings` and
   `observed: 48` renders exactly the old sentence: "Assessed: code and test code were consulted
   and returned 48 items." An old snapshot renders as it always rendered; the store test pins the
   same for the live Demo Product record.

## Arithmetic

For snapshot `demo-booking-levels-20261122-262404a9-r3` (run `demo-booking-levels-20261122T204917`),
queried directly: the registry record holds `code` observed **None** with the `.java` skip attached
(142 files, all named in the record) and `test_code` observed **48**, arms `{product: 27, test: 21}`.
I then counted the artefacts the snapshot actually stored: 6 `feature` + 42 `stepdef` = **48** —
the number in the sentence equals the artefacts actually fetched, not the tree (the tree also held
142 `.java` and 169 other skipped files, none counted). The product arm's own record fetches 27
files, all counted as `test_code`, and `code` is 0 — so no skipped or misfiled file leaks into the
code count. Demo Product r11: `code` 45 (product) + `test_code` 50 (test) = 95, and the rendered sentence
is "Assessed: code and test code were consulted and returned 95 items." — consistent.

## Nothing else moved

I created a worktree at 2171e90 (pre-change) and rendered pages with **both** codebases from the
same read-only store: index, /runs, three run pages (`demo-product-levels-20261122T204947`,
`demo-service-dup-20261122T164254`, `demo-service-dup-20261122T205100`) and three case pages
(DemoService cases 01–03) — 8 pages. After normalising only the relative-age string
("N hours ago" → AGE), all 8 were **byte-identical** between old and new code. Verdict counts
re-queried: Demo Product 94 claims = 90 distinct / 1 unplaced / 1 gap / 2 review; DemoService 17 claims,
17 cases — matching AC5.

## The confessed mislabelling

The sentence "test code was consulted and returned 48 items" is now true about *what was read*, but
27 of the 48 are front-end `.js`/`.ts` assets from the **product** repository, misfiled as step
definitions by the kind table (TESTOPS-39's finding, deliberately left to TESTOPS-42). The page
carries the arm split in the store (`readings[].arms`) but renders it nowhere: a reader of the run
page cannot tell that more than half of the "test code" came from the product repository. The page
is honest about the zero; it is not yet honest about the composition of the 48. That is within the
ticket's declared scope (AC4 asks for the `code` sentence, not the vocabulary), so it does not
block this ticket — but the debt is real and TESTOPS-42 must pay it.

## Three sharpest concerns

1. **The aggregate FOUND sentence can still hide a capability-level zero.** In my legitimate-zero
   scenario the combined sentence reads "code and test code were consulted and returned 2 items"
   even though `code` returned 0; a reader is not told which capability supplied the 2. Only the
   per-capability record (or assessing `code` alone) reveals it. The old lie is fixed; a smaller
   opacity remains.
2. **`_skip_reason` reports only the biggest skipped kind by count** (`pipeline.py:83`). With one
   dominant kind it names "169 more in 17 other kinds" — fine — but a reader is never told what
   those kinds are on the sentence line, and the "Files this run could not read" list is suppressed
   unless an unread capability is explained. A run that skips, say, 500 `.sql` files but reads its
   code fine records the skips in the store and renders nothing about them on the page.
3. **Partial reads are invisible in the sentence.** In the one-of-five scenario the four skipped
   kinds do not appear in the sentence at all (state `found`, skips recorded only in the snapshot).
   "Consulted" remains true, but a repository where 80% of kinds were unreadable looks in the
   sentence like a fully read one. The per-capability arms and skips exist; the sentence for a
   *read but partially skipped* capability does not surface them.
