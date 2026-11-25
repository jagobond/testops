# TESTOPS-42C-3 review — round 2

Reviewer: independent review of the TESTOPS-42C-3 build. Round 1 ran out of iterations before
writing a file; this round finished all four items and wrote the report. Environment for every
command: `env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1
C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe`.

## Verdict

**PASS.** All four review items resolved with evidence. AC7's question is closed: T42C-3 is
innocent, and the `proposed_action` diffs round 1 saw are a stale stored run, not a regression.
Full suite re-run by this review: **622 passed in 116.71s**.

## 17 of 43, independently produced (round 1's result, restated)

Reproduced as a persisted run (not just a test assertion) — run
`demo-booking-levels-20261123T132004` in a scratch store, from the stored blobs of
`m-pujic-levi9-com/cypress-cucumber-e2e-tests@262404a9` and product arm
`example-org/demo-booking-platform@efe2deb`. Claims: 43 — 13 distinct, 4 review, 26 unplaced.
Placement record: `asserting 43, placed 17, unplaced 26, layers {ui: 17}, unreadable []`.
Rendered pages saved under `factory/reports/2026-11-23/`.

## AC7 baseline (main vs branch vs stored)

Method: `rebuild.rebuild` of snapshot `demo-product-levels-20261122-a3f19853-r11` run twice against copies
of the store — once with the branch code (`testops-t42c3`, 09c99da), once with main's code
(`C:/Users/<name>/Projects/testops`, d69881e, which does not contain T42C-3) — each compared
claim-by-claim (subject_ref + assertion_line) with the `proposed_action`, `statement` and `verdict`
rows of every stored demo-product levels run.

Result:

- Branch rebuild vs main rebuild: **identical** (all 94 claims, byte-equal actions).
- Branch and main vs the newest stored runs (`demo-product-levels-20261122T120603` on snapshot r10,
  `demo-product-levels-20261122T204947` on r11): **0 differences in all 94 claims.**
- Branch and main vs the older stored runs (`demo-product-levels-20261122T011316`, the pinned run, and
  `demo-product-levels-20261121T215534`): **all 94 actions differ**, in exactly the form round 1 saw:
  - stored: `No change: keep the step "…" where it is; this level is the cheapest one that
    establishes it.`
  - rebuilt: `No change: keep the step "…" at the cheapest level that establishes it.`

Conclusion: **T42C-3 is innocent.** The prose change is commit bf13261 (TESTOPS-29, 2026-11-22
11:55, present in main too) — "the action states the change, the statement states the reason" —
and the stored runs at 01:13 and earlier were simply never re-run after it. The TESTOPS-29 build
report itself records this ("the stored run `demo-product-levels-20261122T011316` still holds 0.10.1's
strings"). What should be done: nothing in code — the two runs since TESTOPS-29 already carry the
new prose — but the old runs are misleading as pinned baselines. Recommendation: a retention/
migration note (or a re-run-and-supersede pass) marking pre-TESTOPS-29 demo-product levels runs as
superseded so no future review or `measure_action_repetition.py` run picks `T011316` as "before".

## The persisted run, in the reader's words

Run page (`persisted-run-page.html` in this directory), verbatim after tag-stripping:

- Ecosystem sentence: "The test repository o/tests was read as cucumber-js (44 cucumber-js
  step-binding declarations in 5 files; declaration syntax: 44 single-quoted strings; 0 declared as
  this.<Verb>(...); 28 same-line, 16 with the pattern on the following line; 0 regex-literal
  declarations; … 11 Cypress custom commands (6 api, 5 ui))."
- Placement line: "The suite was read as cucumber-js. Of its 43 asserting steps, 17 were placed on
  a layer (17 ui) and 26 matched no step binding."
- Why the 26: "The 26 matched no binding because no binding matches these words: they name
  messages the suite never declared. The two nearest patterns are User will get
  validation/mandatory error message: {string} and Visitor will get validation/mandatory error
  message: {string}; each unplaced case names the step it could not place. Every declaration in
  the suite was readable."
- No "unsupported" sentence anywhere on the page (checked).

Placed claim's case page (`persisted-claim-case-page.html`, case
`…-20261123T132004-01`, verdict "Checked, but over-tested for what it asserts", step
"Then User is redirected to Rooms Management Page"), its "What placed this claim" block verbatim:

> the cucumber-js extractor read the step binding at
> cypress/e2e/features/admin-panel/login/login.stepdef.js:33, which reaches the ui layer. The
> chain it followed: cy.contains. This scenario also runs the step definition at
> cypress/e2e/features/admin-panel/login/login.stepdef.js:5 (Tries to login with valid username
> and password), which reaches the ui layer: — cy.loginViaUI() at
> cypress/support/custom-commands/login.js:21, and its own body reaches cy.get, .type, .click,
> enterUserName(), enterPassword(), clickLogin().

One unplaced claim's statement, verbatim (from the run's claim rows; the run page summarises the
26 collectively rather than listing each statement on the page):

> The step reads "User will get mandatory error message: 'Room name must be set'", but no binding
> matches these words. The two nearest patterns are "User will get validation/mandatory error
> message: {string}" and "Visitor will get validation/mandatory error message: {string}".

Minor observation, not a defect: the run page says "each unplaced case names the step it could not
place", but unplaced claims raise no case (only the 4 review claims do), so an individual
unplaced step text is visible in the store, not as a page of its own.

## AC5 guard seen failing

A scratch copy of the whole `testops`/`tests` tree was made outside the worktree, and per-file
layer inference was reintroduced into
`testops/extract/ecosystems/cucumber_js.py::bindings` (the file's name decides the layer, the
.NET reader's way, overriding the per-body/per-command resolution). Running the placement tests
against that copy:

- FAILED `tests/test_cucumber_js_placement.py::test_per_file_layer_inference_cannot_be_reintroduced`
  — assertion at line 101: `assert rows["through the API"].layer == "api"` →
  `AssertionError: assert 'ui' == 'api'`. A file that holds both an API call and a browser call
  got one layer for both steps from the file's name.
- The sibling guard `test_a_cy_request_command_in_a_ui_named_file_is_api` still passed under this
  particular reintroduction (its file is not ui-named); the mixed-file test is the one that
  catches the defect class.

The guard works: per-file inference cannot come back silently.

## AC9 and AC6

Run against a copy of the build store (`data/testops.db` copied to scratch; 29 snapshots present,
store opens and analyses):

- **AC9** — one regex-literal and one concatenated declaration in a suite, analysed hands-on:
  - `cypress/e2e/front/booking/booking.stepdef.js:1`, kind `regex-literal`, reason "the
    declaration is a regular-expression literal, which this build cannot turn back into a step
    pattern; nothing is placed for it";
  - `cypress/e2e/front/booking/booking.stepdef.js:2`, kind `concatenation`, reason "the pattern is
    split across a string concatenation, so only its first half is readable and that half would
    match nothing; nothing is placed for it".
  The rest of the suite was still analysed: bindings `('a readable step', When, ui)` and
  `('the room is visible', Then, ui)` were placed. The run is a claim set, not a refusal.
- **AC6** — a synthetic duplicate pair (identical scenario "the room exists" in two suites, one
  backed by `cy.request`, one by a browser assertion) produced exactly **1 duplication claim**,
  verdict `duplicate`: "The scenario \"the room exists\" at cypress/e2e/contact/contact.feature:3
  drives a browser to assert \"the room is available\", which cypress/e2e/booking/book.feature:3
  already establishes over HTTP." (`extractor: cucumber-js, layer: ui, cheapest: api, suite:
  contact`.) So the 0 duplication claims on the real corpus mean "no two scenarios share a
  normalised signature", not "the analyser silently did nothing".

## What I did not verify

- The 622-test suite passes (re-run by this review, 116.71s), but I did not re-verify the
  byte-identical .NET goldens line-by-line myself beyond what the suite pins.
- The product arm's ecosystem sentence ("read as no ecosystem this build recognises") is accurate
  for `demo-booking-platform` but I did not audit whether a Node backend could fairly be read
  as anything; the ticket does not require it.
- I did not verify the DemoService corpus numbers (17/17) beyond the suite's pin.
- The unplaced statements are visible in the store, not as individual pages; I did not test
  whether any other UI surface lists them (the runs index and run page do not).
- I did not confirm whether the superseded-runs recommendation needs a ticket of its own; that is
  the Lead's call.
