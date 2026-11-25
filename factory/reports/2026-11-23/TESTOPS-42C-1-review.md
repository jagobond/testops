# TESTOPS-42C-1 review — the cucumber-js parsing floor

Reviewer: independent scan over the stored blobs with a scratch scanner written for this review
(not the product module, not `tools/ecosystem_inventory_counts.py`); behavioural probes against
`testops/extract/ecosystems/cucumber_js.py` and `testops/extract/stepbindings.py`; full suite run
from the project `.venv` with `PYTHONPATH`, `PYTHONHOME`, `VIRTUAL_ENV`, `CONDA_PREFIX` stripped
and `PYTHONNOUSERSITE=1`: **596 passed in 116.78s**.

## Verdict

**ACCEPTED.** The counts are exact, both layouts parse, the matcher change is pinned, suite
scoping is measured rather than assumed, and nothing is half-wired. Three concerns are recorded
below — one of them (the concatenation probe) should be picked up by T42C-2 or T42C-3, and one
(the inventory's stem-rule sentence) needs a corrections note in the document Harry costed from.

## Counted from blobs

My own scan (regex of my own writing, reading the five `kind='stepdef'` blobs out of
`data/testops.db` via their blob hashes, plus a close-brace walk I wrote myself):

- **44 declarations in 5 files** — `login` 10, `room-management` 5, `booking` 11, `contact` 13,
  `background` 5.
- **When 26, Then 13, Given 5** — matches AC1 exactly.
- **Same-line 28, next-line 16** — matches AC2 exactly.
- **43 distinct patterns**; all 44 single-quoted; **0 regex literals**, 0 double-quoted,
  0 template literals, 0 `this.`-style.
- The duplicate is `Visitor will get validation/mandatory error message: {string}`, declared at
  `booking.stepdef.js:80` and `contact.stepdef.js:63` (the near-twin
  `User will get validation/...` in `room-management.stepdef.js:68` is a different pattern, not a
  duplicate).

Every number in the build report reproduces.

## The 16

The point of the ticket. Two probes the build did not run:

1. **Two newlines plus leading whitespace** between `Given(` and the quote
   (`Given(\n\n  'I have a {string} room', …)`): **parses**. The gap class in `DECLARATION` is
   `[ \t\r\n]*`, so any run of blank lines and indentation is consumed and the layout is recorded
   `next-line`. The implementation is genuinely not line-oriented — it survives a shape harder
   than any of the corpus's 16.
2. **Pattern split across a concatenation** (`When('Visitor will get validation/' +
   'mandatory error message: {string}', …)`): **parses but truncates silently** — the declaration
   comes back with pattern `Visitor will get validation/` and the `{string}` half of the sentence
   is dropped without any error or flag. Nothing in this corpus concatenates (0 interpolations,
   44 single string literals), so this is not a defect against AC1–AC4, but it is exactly the
   failure mode the ticket exists to prevent — a quiet undercount — arriving by another door.
   Judged: **a fragility that will bite on the next corpus**, not a legitimate limitation. The
   module already has the right pattern for this: refuse loudly. After the closing quote, if the
   next non-whitespace character is `+` (or the declaration ends without a comma/function body
   shape), the scanner should refuse that declaration the way it refuses regex literals. Raise
   with T42C-2 or T42C-3; it does not block this part.

## Regex literals

This corpus has 0, and the build makes `bindings()` raise `UnsupportedEcosystem` on one. Verified:
a synthetic `Then(/^a regex$/, …)` raises, the message names `path:line`
(`cypress/e2e/x.stepdef.js:1` — checked by string match), and `detect()` carries the evidence line
"1 regex-literal declarations; regex-literal patterns are unsupported by this build".

Judged: **the right behaviour for this part, the wrong behaviour forever.** AC3 requires
"explicitly reported as unsupported in the record — never silently skipped"; the raise satisfies
that, and while `supported` is `False` nothing ever calls `bindings()`, so the raise costs the
corpus nothing. But when T42C-3 wires placement, a suite with one regex literal among 43 string
declarations would go from 43 placeable claims to zero — the raise throws away a readable suite
because one file uses a form the module cannot handle. The evidence line already carries the
information AC3 asks for, so T42C-3 should move to record-and-continue (the regex declaration
refused, the other 43 returned) and keep the raise only if it wants a hard stop. Not a defect
here; a decision T42C-3 must make explicitly.

## Duplicate both ways

Verified by calling the module on the real blobs: 44 bindings, five suites
(`booking`, `contact`, `login`, `management`, `support`), duplicate carried by
`booking.stepdef.js` (suite `booking`, line 80) and `contact.stepdef.js` (suite `contact`,
line 63). `match_step` on the duplicate text:

- suite `booking` → **`booking.stepdef.js`** ✓
- suite `contact` → **`contact.stepdef.js`** ✓
- suite `login` (owns neither) → falls back, landing on `booking.stepdef.js` (first carrier in
  file-sorted order). This is the any-suite fallback AC5 specifies; acceptable, but note the
  winner is whichever carrier sorts first, not a semantic choice — fine while the two patterns are
  textually identical, wrong the day they drift.

## The stem-rule claim

**The build is right; the inventory is wrong.** Verified independently:

- `stepbindings._suite_of('booking.stepdef.js')` strips `js` and stops — it returns
  **`bookingstepdef`** (same for `loginstepdef`, `backgroundstepdef`, …). The suffix loop has no
  `stepdef` entry, and after stripping `js` the stem no longer ends in any listed suffix. Measured
  against the corpus: **0 of 5** step-definition files produce a suite any feature can match.
- The rule that works is the directory: `suite_of_path` applies `suite_of` to the containing
  directory and gives `booking`, `contact`, `login`, `management`, `support` — **5 of 5 files**,
  and all features resolve (`book-a-room.feature` → `booking`, `contact-hotel.feature` →
  `contact`, `login.feature` → `login`, `room-management.feature` → `management`; the two
  two-feature directories each resolve both their features).

So the inventory's §7 line — *"today's stem rule already works on 5 of 5 files"* — is false, and
`docs/ecosystem-inventory-cucumber-js.md` **needs a corrections note** in the manner of the
TESTOPS-50 corrections section: the stem rule fails on this corpus (0 of 5), the co-location
directory rule is what works, and the 0.25-day scoping estimate is unaffected because the
directory rule is the cheaper of the two. I have not edited the document; that is the Lead's
hand.

## No half-wiring

- `git diff 7f3ef4e..HEAD` touches only `testops/extract/ecosystems/cucumber_js.py`,
  `testops/extract/stepbindings.py`, two test files, and factory documents. **No pipeline or
  analyser file changed.**
- `detect()` on the corpus returns `supported is False` with the evidence lines and the refusal
  reason; `drivers()` raises `UnsupportedEcosystem`.
- `tests/test_ecosystems.py::test_the_demo-booking_corpus_is_not_assessable_and_not_lied_about`
  is in the green suite: the corpus run is still `not_assessable` with zero claims.

## .NET parity

The only shared-code change is in `pattern_to_regex`: `{int}` now becomes `\d+` before the generic
placeholder substitution (which also had its closing-brace escape tightened). `.NET` patterns use
`{string}` and `(.*?)`, not `{int}`, and `{int}` got *narrower*, so the risk was only ever a
dropped match. The pinned proofs all pass in the green suite: Demo Product **94 claims, 90 distinct, 1
unplaced, 1 gap, 2 review** (`test_action_prose.py`), DemoService **17/17** (`test_action_prose.py`,
`test_duplication_tables.py`, `test_duplication_v2.py`), and the case-page goldens are asserted
**byte-identical** against the fixture HTML (`test_projects_services.py`:
`rendered == (FIXTURES / f"{case_id}.html").read_bytes()`). No .NET pattern regressed.

## Three sharpest concerns

1. **Silent truncation on a concatenated pattern.** `When('a/' + 'b {string}', …)` yields pattern
   `a/` with no error. Same failure class as the 16 missed declarations — a quiet undercount.
   Refuse loudly, as the regex arm does. (Probe evidence above; not present in this corpus.)
2. **The inventory's stem-rule sentence is false and Harry costed from that document.** §7 claims
   the stem rule works on 5 of 5 files; it works on 0 of 5 (`bookingstepdef`). The build's
   replacement (directory co-location) is correct and measured. The document needs a corrections
   note; the estimate survives.
3. **The regex-literal raise is a T42C-3 decision, not a settled one.** Raising is honest now and
   free now; wired, it converts one unreadable declaration into zero claims for the whole suite.
   The evidence record already satisfies AC3 — record-and-continue is the better end state, and
   T42C-3's ticket should say which it wants rather than inherit the raise by default.
