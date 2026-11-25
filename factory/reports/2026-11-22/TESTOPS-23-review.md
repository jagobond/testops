# TESTOPS-23 + TESTOPS-26 review — 2026-11-22

## Verdict — PASS

The page reads as one argument said once, all four verdicts carry an action, the lint demonstrably
bites, the verdicts are unchanged (94/90/1/1/2) and the suite is green on both interpreters; the
reservations below are about durability, not correctness.

## Criteria

**TESTOPS-23**

| AC | Verdict | Note |
|----|---------|------|
| AC1 | HOLDS | Each fault is pinned by a named test (`tests/test_case_argument.py`): no repeated quote, no "the words", no fragment headings, one actor, verdicts state what is true, context grouped. |
| AC2 | HOLDS | The scan block answers checked / what is wrong / what to do, in order. |
| AC3 | HOLDS | Provenance is a labelled footnote under the quote ("Where this comes from:"), not a numbered section; the page is five sections. |
| AC4 | HOLDS | The quote carries the Gherkin keyword from the stored feature line. |
| AC5 | HOLDS | No analyser narration in any of the 94 rendered pages; `established_by` and `statement` are no longer rendered. |
| AC6 | HOLDS | Context steps are one introduced group; the intro says they are not evidence. |
| AC7 | HOLDS | Labels: "Checked", "Checked, but over-tested…", "Not proved — nothing runs a browser", "Cannot tell". Zero codes on the page; the footnote keeps the shorthand. |
| AC8 | HOLDS | The lint runs as a test over the real fixture pipeline run and over the stored 94-claim corpus; 0 failures, and my seeded violations (below) fail it. |
| AC9 | HOLDS | Store query confirms `cotw-levels-20261122T011316`: 90 distinct, 1 unplaced, 1 gap, 2 review. |
| AC10 | HOLDS | 273 passed on `.venv` (re-run by reviewer); 269 passed, 4 skipped on 3.11 (re-run by reviewer); the 4 skips are the pre-existing pre-3.12 checks. |

**TESTOPS-26**

| AC | Verdict | Note |
|----|---------|------|
| AC1 | HOLDS | Three parts in every scan block: bold judgement, one wrong-sentence, action on its own row with the "What to do" label. |
| AC2 | HOLDS | Step quoted once, in `code.ident`; the action refers to "this step" (`_without_step`). |
| AC3 | HOLDS | `repeated_clause` over the opening block; my seeded 6-word repeat failed it. |
| AC4 | HOLDS | `code.ident` for identifiers; `bare_identifiers` fails prose `data-fact-id` and `HTTP client`. |
| AC5 | HOLDS | `straight_quotes` fails any straight quote outside code spans; corpus clean. |
| AC6 | HOLDS | Every word in `BANNED` has a rejection test; my seeded "dearer" produced exactly that failure. |
| AC7 | HOLDS | See the four cases below; `distinct` says plainly "No change: keep this step where it is." |
| AC8 | HOLDS | Same store, same counts, verified independently. |
| AC9 | HOLDS | Same two interpreter runs as above. |
| AC10 | HOLDS | Markup check (`detached_punctuation`) plus a CSS guard test that pins padding against negative margin, so the paint defect cannot silently return. |
| AC11 | WEAK | Screenshots exist and the CSS carries a measured, commented fix (.51/.8/.69rem with the reason); I could not view the images in this session, so the visual claim rests on the build report's measurements. |

## Four cases, read aloud

Taken from the stored run `cotw-levels-20261122T011316`, rendered through `app.case_page` into a
scratch copy of the store (the product store was never written). One of each verdict; opening
blocks verbatim, comma after the code span as the markup holds it.

**distinct**

> Checked
> The test asserts Then there is one sheet per entity, and the response the server sends settles it.
> What to do No change: keep this step where it is.

Reads clean. The judgement is a statement; the action exists and says nothing needs doing, which
satisfies T26 AC7's hard case. One stiffness: "The test asserts Then there is…" collides two verbs
where a reader wants "The test asserts that there is…". Tolerable — the quote must carry its
keyword — but it is the least fluent sentence on the page.

**unplaced**

> Cannot tell
> The test asserts Then that count is correct for the store it was run against, but nothing in it says what it is compared with, so nothing settles it.
> What to do Rewrite this step to say what it is compared with — the value, the row or the report it should agree with — then re-run.

Good. Every word is about the test; the action is concrete and needs no footnote.

**gap**

> Not proved — nothing runs a browser
> The test asserts Then each fact's citation is in an element reachable by an accessible name, but nothing short of a browser settles it, and the test drives the HTTP API instead.
> What to do Move this step into a test that drives a browser, or delete it.

Good. The headline states the fact, not the absence; the action offers the two real choices.

**review**

> Checked, but over-tested for what it asserts
> The test asserts Then every rendered fact sits in an element carrying a data-fact-id, but the page the server sends settles it, and the test drives a browser to read it.
> What to do Rewrite this step to call the HTTP client instead of the browser.

Good, and it is the Product Owner's original case: the argument and the action no longer repeat
each other, and "dearer" is gone. No sentence needed the footnote to be understood on any of the
four.

## The lint

**What I seeded** (via a scratch test reusing the ticket's own seeding helpers, then deleted):

1. `proposed_action` containing "Take the dearer path first…" — failed with
   `'dearer' is not plain English; write 'more expensive'`.
2. An action restating the wrong sentence's clause — failed with
   `the scan block repeats a 6-word clause: 'the page the server sends settles'`.

The lint has been seen to fail, by me, on both the banned-word arm and the repeated-clause arm.

**What the lint may have broken:** nothing that I can find in the corpus. I grepped the 94 claims
for evasion patterns ("more expensive", "make use of", "supposedly", and the rest of the banned
neighbours) — zero hits, and the actions read as engineers wrote them, not as synonyms dodging a
filter. No sentence was split into fragments to dodge the 45-word limit; the action tail-drop
(after the semicolon) is a deliberate restatement cut, and in this corpus every tail was a
restatement. The margin of safety: a writer could paraphrase in 5-word windows and pass, and
`action_line` will silently discard a second genuine instruction after a semicolon.

## Three sharpest concerns

1. **`action_line` is lossy by design.** It keeps only the clause before the first "; ". Today
   every stored tail is a restatement, so the cut is right — but if an analyser ever writes two
   instructions in one action string, the second is dropped without a trace. The rule deserves a
   comment or an assertion that the tail is redundant, not just trusted.
2. **"The test asserts Then…"** — the Gherkin keyword reads as a second verb. A reader manages, but
   this is the one sentence in all four blocks where I re-read. Consider "The test asserts the step
   `Then …`" or an em-dash before the quote.
3. **AC11 is trusted, not verified, by this review.** The screenshots exist and the CSS carries the
   measured numbers with the reason, but I had no way to view the images in this session. Whoever
   merges should look once at
   `C:\Users\<name>\Pictures\testops-screenshots\TESTOPS-26-case-cotw-levels-20261122T011316-03-scan-block-2x.png`.

## Demo

**The problem.** The case page narrated the analyser: the claim said three times, a numbered
section on heading provenance, sentences about "the words" a rule read, fragment headings, three
names for one actor, an absence badge ("Browser not needed"), and a summary whose action hid in the
third sentence of one paragraph.

**What changed.** The page is now one argument in five sections: a scan block (judgement, one
wrong-sentence, action on its own labelled row), the step and its definition, the scenario's other
steps introduced together as context, what could not be checked, and the decision form. Provenance
is a footnote under the quote. The analyser's own copy (`statement`, `established_by`) is no longer
rendered; the page states the fact the rule found. Two lints — T23's anti-narration lint and T26's
plain-English lint — run as tests over every claim of a real run. Code spans carry a CSS fix so the
comma sits against the word, and the action box's padding is measured, not even by accident.

**How we know it works.** 273 passed / 269 passed + 4 skipped on the two interpreters, re-run by
this reviewer with the clean invocation. The store query reproduces 90/1/1/2 for
`cotw-levels-20261122T011316`. All 94 rendered pages pass both lints, and both lints were
demonstrated to fail on seeded violations (above). Four cases — one per verdict — were read aloud
as a reader; each states a judgement, an argument and an action, with the `distinct` case saying
plainly that nothing needs doing.

**What it does not solve.** The stored analyser copy (`statement`, `established_by`,
`proposed_action`) is still analyser prose; the page curates it rather than fixing it, which
belongs to the analyser tickets. `action_line` can drop a future second instruction. The
typography of AC11 rests on the build report's measurements and the CSS comments; the padding
numbers are font-dependent.

**Where to look.** `testops/web/app.py` (`verdict_label`, `wrong_sentence`, `argument_block`,
`action_line`, `code.ident` and `p.action` in the CSS), `testops/web/lint.py`,
`tests/test_case_argument.py`, `tests/test_case_scan.py`, and the stored run
`cotw-levels-20261122T011316` in `data/testops.db`.
