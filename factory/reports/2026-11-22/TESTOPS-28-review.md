# TESTOPS-28 review — 2026-11-22

## Verdict — PASS

The classification is deleted outright, all 21 smuggled tails (the two reviews' 16 distinct probes
plus five of my own) reach the page word-complete, the 94 real actions render whole with no content
word lost anywhere in the block, the verdicts are pinned and unchanged, the T26 lint is untouched
and did not fire, and the only cost is visible wordiness the ticket declared in advance.

## Criteria

- AC1 — HOLDS. `action_line` (`testops/web/app.py:441`) returns the whole stored action, split at
  semicolons only by `_sentences`, capitalised and full-stopped by `_as_sentence`. Nothing is
  classified or cut. Proven below over the probes and the real corpus: every content word of every
  stored action appears on the page.
- AC2 — HOLDS. `git grep` for `INSTRUCTION_VERBS`, `CONTINUATION_OPENERS` and
  `second_half_is_instruction` returns nothing in product or test code (the only hits are
  historical factory reports and this review's own prompt, which must name them to describe the
  past). The build report confirms the whole apparatus — `ORDER_CUES`, `IRREGULAR_FORMS`,
  `INSTRUCTION_FORMS`, `_inflections` and friends — went with it. Nothing dormant survives.
- AC3 — HOLDS. All 94 actions of `cotw-levels-20261122T011316` render in full (verified from the
  store directly, read-only sqlite, not from test output). The repetitiveness is reported in
  "The cost" below, not tidied away.
- AC4 — HOLDS by absence: the T26 plain-English lint (`testops/web/lint.py::repeated_clause`,
  unchanged in the diff) fired on **none** of the 94 blocks with tails kept, so there is nothing to
  record as a finding. The lint was not silenced and no cut was reintroduced; the diff to
  `testops/` removes 141 lines and adds no classifier.
- AC5 — HOLDS. Every rendering on the real corpus is one or two sentences, each with an initial
  capital and one full stop; no run-on was found. `"No change: keep this step where it is. This
  level is the cheapest one that establishes it."` is the canonical shape.
- AC6 — HOLDS. Store read directly: 94 claims, 90 distinct, 1 unplaced, 1 gap, 2 review, and the
  suite pins `PINNED_RUN` by id (fixing the query-selected-run risk from the first review). Suite
  green on the clean invocation: **315 passed** (`.venv`, Python 3.12.5,
  `env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1`).

## Nothing lost

Method: each probe tail was appended to a real corpus-shaped head (`Rewrite this step to call the
HTTP client instead of the browser; <tail>`), rendered through the real `action_line`, and every
content word of the stored string was checked against the rendered page. The two earlier reviews
between them smuggled 16 distinct tails (8 + 8; no overlap), all of which had leaked or survived
under the classifier. All are listed, all reach the reader now.

| probe (source) | result |
|---|---|
| `this should be split into two steps and the second deleted` (R1) | KEPT — whole tail on the page |
| `move it and rename it` (R1) | KEPT |
| `one copy to keep` (R1) | KEPT |
| `keep it if the page does not need it` (R1) | KEPT |
| `you should delete the second one` (R1) | KEPT |
| `instead, delete the duplicate` (R1) | KEPT |
| `the second copy should be deleted` (R1, DROPPED under T27) | KEPT |
| `it is worth keeping one copy` (R1) | KEPT |
| `the duplicate is deletable` (R2, DROPPED) | KEPT |
| `removal of the copy is advisable` (R2) | KEPT |
| `ought to be removed` (R2) | KEPT |
| `would be better gone` (R2) | KEPT |
| `the second one can go` (R2, DROPPED) | KEPT |
| `there is no need for this copy` (R2) | KEPT |
| `both copies are unnecessary` (R2) | KEPT |
| `it must not be kept` (R2) | KEPT |
| `the copy would be deleted by whoever owns it` (R2 extra, DROPPED) | KEPT — my five below, all new shapes |
| `delete it twice and the suite wastes a run` (mine) | KEPT |
| `one of the copies should go before the release` (mine) | KEPT |
| `the duplicate is removable once the assertion moves` (mine) | KEPT |
| `getting rid of the copy had better be merged into the first` (mine) | KEPT |

So 16 earlier probes (15 listed in the brief; the two reviews' union is 16 distinct tails, and the
seventeenth shape from review 2, `the copy would be deleted by whoever owns it`, is included too)
plus 5 of mine: 0 content words lost anywhere.

Real corpus, whole block: for each of the 94 claims I rendered `wrong_sentence` + `action_line`
together and asserted every content word of the stored `proposed_action` appears in the block.
Result after HTML-unescaping: **0 missing words**. The only words absent from the action box itself
are the quoted step's own words in 94 of 94 actions — that is the T26 step-reference swap
(`"keep this step where it is"`), and the step's words render verbatim in the wrong sentence
immediately above, on the same page. This was accepted in both earlier reviews as the only
permitted shortening; nothing beyond it exists.

## The cost

The quoted example renders exactly as the brief says: `Rewrite this step to call the HTTP client
instead of the browser. The response decides everything the browser is being used for.`

Measured over the 94 real actions:

- **2 of 94** actions repeat a content word between the two sentences of their own action box —
  precisely the two `review`-verdict claims, which share the word `browser` between the order and
  the restatement.
- **0 of 94** tails are pure restatements of the head: every tail adds at least one content word
  the head does not carry.
- The other 92 tails (e.g. `this level is the cheapest one that establishes it.`) repeat the
  analyser's reasoning boilerplate across *different* blocks, which is a cross-block analyser
  finding, not a same-block repetition, and belongs to the follow-up ticket on `proposed_action`
  strings, as AC4 anticipated.

**The trade is worth it.** Three review passes produced three different leaks at the same boundary;
the asymmetry in the ticket is correct — a dropped clause is invisible, a kept clause is wordy, and
wordiness here costs one short sentence in 2 of 94 blocks. The follow-up ticket's measured size is
**2 actions** (the two review claims whose second sentence restates the browser argument), plus the
cross-block boilerplate tails if the Lead wants the wider tidy in the same ticket.

## Residual risk

1. **The step-reference swap is still a shortening.** 94 of 94 boxes read "this step" where the
   store quotes the step; correctness depends on `wrong_sentence` always naming the quote above.
   Both earlier reviews accepted this and it is asserted, but a future change to `wrong_sentence`
   would silently orphan the reference.
2. **Two sentences is the only structural guarantee.** `_sentences` splits at semicolons only; a
   future analyser writing two orders joined by ", and " or " — " renders as one long sentence, not
   a run-on by the lint's definition. AC5 holds today; the shape is unguarded.
3. **The possessive check is cosmetic in HTML.** `rich_prose` escapes apostrophes (`&#x27;`), so a
   naive word check on raw HTML would report `fact's` as lost. It is not lost after unescaping;
   anything that ever strips entities before rendering would change this.
4. The pinned-run fix moves the query-selected pin to a constant, but the store itself is still a
   build artefact; a fresh re-run of the analyser writing new `proposed_action` strings will need
   the follow-up ticket, not a renderer change — correctly out of scope here.
