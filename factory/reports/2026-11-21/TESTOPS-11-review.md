# TESTOPS-11 review — 2026-11-21

## Verdict — PASS

The restraint rule does exactly what the ticket asked — the ticket's own example claim is
`unplaced` again, asserted at corpus level, and the correction cost the corpus almost nothing
else — and the builder's partial refusal on AC5/AC6 is sound engineering, not convenience.

## Criteria

- **AC1 HOLDS.** `META_PROPERTY` (be-verb + correct/accurate/right/wrong) sends a judging claim
  to `("U", WHY_META)` before any noun is consulted, and `classify_with_instrument` explicitly
  refuses the instrument fallback when `why == WHY_META` — a binding names a layer, never a
  comparison. The rule is narrow: `test_a_meta_claim_that_says_what_it_compares_is_placed`
  proves a claim naming its comparison is still placed, so this is not a blanket.
- **AC2 HOLDS.** My own run of `replay_levels.py --acceptance` this session printed
  `acceptance: 94 claims, 1 unplaced (max 3), 1 gap / 2 review, 'that count is correct for the
  store it was run against' unplaced - PASS`. The assertion is checked in the corpus replay,
  not only a fixture.
- **AC3 HOLDS.** Exactly 1 claim is `unplaced` after the change, and it is the meta claim the
  ticket wanted back. No formerly-distinct claim regressed.
- **AC4 HOLDS.** gap 1, review 2 — identical to the TESTOPS-10 run. Restraint removed one false
  positive and manufactured nothing.
- **AC5 WEAK — pushback accepted in substance, not in full.** The builder did not implement
  "one label per suite"; it made the label derive from the instrument, so the no-server
  canon_verification suite now carries one label across all twelve claims (verified: I1 and I2
  claims there both read "settled by the engine's own answer about the stored data"). But
  api suites still carry two or three labels per scenario, because an I1 store claim and an I2
  response claim read differently even when the same HTTP call settles both. Forcing one label
  there would erase a real distinction, so the literal criterion is unsatisfiable without
  lying — the refusal is sound. The second half (`_reads` consistent with the label) holds for
  every instrument in the corpus: engine↔"only talks to the engine", api↔"the response the
  server sends" are now the same story.
- **AC6 WEAK — pushback accepted.** Label and statement now come from one table, so the
  TESTOPS-10 contradiction is structurally closed: the api-layer store claim is labelled
  "settled by the data as stored, read through the response the server sends", which is what
  its statement always said. Residual looseness: a KP claim in an api suite is labelled "the
  page the server sends" while its statement says "reads the responses the server sends" —
  harmonious, not contradictory, but the page/response wording seam is patched per instrument
  rather than generally.
- **AC7 HOLDS.** `94 passed in 7.73s` under the AGENTS.md-stripped environment (90 existing
  plus 4 new; the ticket's "90 tests" describes the suite before this ticket's own additions).
  Statements and actions in my samples carry no codes. Determinism covered by the existing
  per-sample test; the replay is store-driven and repeatable.

## Your own samples

Six claims I picked across verdicts, printed verbatim from my own corpus run:

1. `that count is correct for the store it was run against` — unplaced.
   Statement: "This step says "that count is correct for the store it was run against", which
   calls it correct without saying what it is compared with, so nothing can be said about
   whether it is checked."
   Label: "unclear what would settle it".
   Action: "Rewrite the step "that count is correct for the store it was run against" to say
   what it is compared with - the value, the row or the report it should agree with - then
   re-run; a judgement with no comparison in it cannot be checked at any level."
   Reads as honest restraint, and the action tells a developer exactly what to write.

2. `that fingerprint is not the claim text itself` — distinct, I1/api.
   Statement: "This test asserts that that fingerprint is not the claim text itself. This test
   only reads the responses the server sends, which settles that, so the assertion is checked."
   Label: "settled by the data as stored, read through the response the server sends".
   Action: "No change: keep the step "that fingerprint is not the claim text itself" where it
   is; this level is the cheapest one that establishes it."
   Accurate — and note the new label fixes TESTOPS-10's complaint that a store claim pretended
   the response was irrelevant.

3. `the pass fails` — distinct, I1/engine.
   Statement: "This test asserts that the pass fails. This test only talks to the engine, which
   settles that, so the assertion is checked."
   Label: "settled by the engine's own answer about the stored data".
   Action: "No change: keep the step "the pass fails" where it is; this level is the cheapest
   one that establishes it."

4. `the clean store exits with the success status` — distinct, I2/engine (same file as 3).
   Statement: "This test asserts that the clean store exits with the success status. This test
   only talks to the engine, which settles that, so the assertion is checked."
   Label: "settled by the engine's own answer about the stored data" — same as claim 3, which
   is the one-verification-pass outcome AC5 wanted.
   Action: "No change: keep the step "the clean store exits with the success status" where it
   is; this level is the cheapest one that establishes it."

5. `every rendered fact sits in an element carrying a data-fact-id` — review, KP/ui.
   Statement: "This test asserts that every rendered fact sits in an element carrying a
   data-fact-id. The page the server sends settles that, but this test drives a browser, so it
   pays for a browser that decides nothing extra."
   Label: "settled by the page the server sends".
   Action: names the browser-for-payment rewrite (unchanged in shape from TESTOPS-10).

6. `the page claims no character name contains "Qqqzzx"` — distinct, KP/api.
   Statement: "This test asserts that the page claims no character name contains "Qqqzzx".
   This test only reads the responses the server sends, which settles that, so the assertion is
   checked."
   Label: "settled by the page the server sends".
   Action: "No change: keep the step ... where it is; this level is the cheapest one that
   establishes it."

None of these is machine output and none repeats itself. One wording flaw recurs: claims whose
clause opens with "that" produce "asserts that that fingerprint..." / "asserts that that fact
..." — grammatical but clumsy, and it appears in at least two statements. Cosmetic.

## Three sharpest concerns

1. **AC5 is honoured only where it was easy.** Eleven scenarios in the corpus still carry two
   or three different labels in one verification pass (I1/I2/KP mixtures in api suites). The
   builder's reasoning for not forcing one label there is right — a store claim and a response
   claim genuinely settle differently — but the ticket's criterion is now met by redefining
   "one verification pass" as "one no-server suite". The next ticket should either rewrite AC5
   or finish the job at the label table.
2. **The restraint rule is a narrow pattern, not a concept.** It catches be-verb +
   correct/accurate/right/wrong with no comparison word. "It verifies the count", "the report
   checks out", or a compound sentence ("the stored hash is correct and the response returns
   200") evade it — the compound case is swept to `unplaced` wholesale because the meta rule
   runs before all splitting, so one judging half-sentence can unplace a genuinely checkable
   sibling assertion. Not exercised in this corpus; will be exercised by the next one.
3. **The label-change count in the build message does not match a naive reading of the replay
   output.** I measure 39 label changes (26 I1/api, 10 I1/engine, 2 I2/engine now carry
   instrument-derived labels) plus 1 verdict move — which reconciles exactly with the claimed
   "39 labels changed and 1 verdict moved", but only after recomputing; `replay_levels.py`
   prints "moved 46" because it counts claims from the pre-TESTOPS-10 baseline run, a different
   denominator. Two numbers, one word, no definition of which baseline each counts.

## Demo

**The problem.** TESTOPS-10 fixed coverage by widening the vocabulary, and the vocabulary then
did the forbidden thing on its own: "that count is correct for the store it was run against" —
the very sentence the ticket had held up as genuinely ambiguous — went `distinct, I1` because
one token, "store", was now known. A claim checked only in name is worse than an honest
`unplaced`, because a reader trusts it. The same case page also told three different stories
about one verification pass: "the pass fails" and "the overall result is a failure" read as
"settled by the data as stored" while "the clean store exits with the success status" read as
"settled by the response the server sends".

**What changed.** level_fitness 0.8.0, two moves. Restraint: a claim whose words judge
something correct/accurate/right/wrong without naming a comparison is placed by nothing — no
noun in it, and no instrument fallback, because a binding names a layer and never a
comparison — so it returns to `unplaced` with a statement and action that say what to write
instead. Labels: the reader's phrase for what settles a claim now comes from the instrument
the suite actually runs, from the same table that writes the statement's "this test only
talks to the engine" clause, so a label and a statement cannot name different instruments.

**How we know it works.** I ran both checks myself this session, in the stripped environment.
`pytest -q`: 94 passed. `replay_levels.py --acceptance` on
cotw-levels-20261121-a3f19853: PASS — 94 claims, 1 unplaced (the meta claim, max 3), gap 1 and
review 2 unchanged, distinct 90. Compared with the stored pre-TESTOPS-10 baseline run, 46
claims moved from unplaced to distinct; 39 claims carry newly instrument-derived labels. The
two canon_verification wordings that disagreed in TESTOPS-10 now share one label while keeping
their honest I1/I2 codes.

**What it does not solve.** Multi-label api scenarios (concern 1), the narrowness of the meta
pattern and its compound-sentence overreach (concern 2), the double-"that" phrasing, the
undefined "moved" denominator in the replay output (concern 3), and the still-absent
build-report artefact noted in the TESTOPS-10 review.

**Where to look.** `testops/analysers/level_fitness.py` (`META_PROPERTY`, `COMPARISON`,
`WHY_META`, the `why != WHY_META` guard in `classify_with_instrument`, `_label`,
`_SETTLED_BY`), `scripts/replay_levels.py --acceptance`,
`tests/test_level_fitness.py` (four new tests), and
`factory/reports/2026-11-21/TESTOPS-10-review.md` for the predecessor findings this ticket
answered.
