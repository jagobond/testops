# TESTOPS-10 review — 2026-11-21

## Verdict — PASS

The headline number survives independent re-measurement: I re-ran the analyser over the same
snapshot myself and got 94 claims, 0 `unplaced`, 1 `gap` (unchanged), 2 `review`, 91 `distinct`
— and the hand-label fixture disagrees with the analyser in one place, which is what an honest
fixture looks like.

## Criteria

- **AC1 HOLDS.** `scripts/replay_levels.py --baseline-run demo-product-levels-20261121T215534` (run by me,
  this session): 94 claims, verdicts distinct 91 / review 2 / gap 1 / unplaced 0. Baseline was 43
  distinct / 48 unplaced / 2 review / 1 gap. 48 formerly-unplaced claims all reclassified; 47 show
  in the move list because two assertions share one text.
- **AC2 HOLDS.** `gap` is 1 before and 1 after — the same accessibility claim. Nothing was
  manufactured.
- **AC3 HOLDS (19/20 = 95%).** Computed independently from the fixture with
  `classify_with_instrument`. The one recorded miss: "no finding names the unapproved proposal"
  labelled I1, analyser says I2.
- **AC4 HOLDS.** Every claim in my re-run dump carries `established_by` naming the deciding rule;
  the 4 instrument-fallback claims are marked "the words place it nowhere, and ...", so a reader
  can see the fallback was used.
- **AC5 HOLDS.** Statement and proposed action for the newly classified claims are plain English,
  no `I1`/`KP` codes (asserted by `test_the_newly_classified_claims_keep_reader_readable_text`);
  actions quote the step text.
- **AC6 HOLDS.** Determinism asserted per sample (`test_the_sample_analysis_is_deterministic`);
  the replay reads only store rows and blobs, so the run is repeatable.
- **AC7 HOLDS.** `90 passed in 7.34s` under the AGENTS.md-stripped environment (was 84).
- **AC8 WEAK.** There is no build-report artefact in the repo — `factory/reports/2026-11-21/`
  holds only reviews, and the commit contains none. The numbers are in the commit message
  (48→0) and are reproducible, but "sample agreement 19/20" is recorded nowhere except my own
  run of the test. Same practice as TESTOPS-4, so not a blocker; a one-paragraph report file
  would close it.

## Your own sample

Eight assertions I picked from the formerly-unplaced set, my expected interaction read from the
step text and binding, versus the analyser:

| assertion | my expected | analyser | matters? |
|---|---|---|---|
| admission is refused with an error naming the missing approver | I2 — the HTTP error names the offender | I2 | no |
| that fingerprint is not the claim text itself | I1 — a value in the stored row | I1 | no |
| the audit reports that fact, named by its fact id | I2 — the audit's output | I2 (content→response) | no |
| no finding names the unapproved proposal | I2, defensibly I1 — the detectors read the store | I2 | no — both are `distinct`, but see concern 1 |
| the three search states the page reported are all different | KP — sentences in the served page | KP | no |
| the two reports are identical | I1 — two files on disk compared | I1 | no |
| it is not an empty page with a success status | I2 — status plus body | I2 | no |
| that count is correct for the store it was run against | unplaced — the ticket itself calls this genuinely ambiguous | **distinct, I1, on the single word "store"** | yes — see concern 2 |

Seven of eight agree, and the one disagreement is the exact assertion the ticket warned about.
None of my eight were reclassified into `distinct` merely because the instrument was
identifiable — the vocabulary genuinely carries them — except the count claim above.

## Three sharpest concerns

1. **One claim, two interaction labels in the same feature.** "the pass fails" and "the overall
   result is a failure" are engine-fallback I1 whose `why` says the engine's own answer settles
   them, yet their `interaction_label` reads "settled by the data as stored", and the sibling
   assertion "the clean store exits with the success status" in the same file is I2 "settled by
   the response the server sends". Same verification pass, same answer, three inconsistent
   wordings on one case page. Verdicts are unaffected; labels mislead.
2. **"that count is correct for the store it was run against" went `distinct` on the word
   "store".** The new STORE regex added `stores?`, and that one token flipped a claim the ticket
   explicitly held up as genuinely ambiguous. `distinct` means checked; a claim checked only in
   name is worse than an honest `unplaced`. This is precisely the ticket's forbidden move done
   through vocabulary instead of the title. The fallback discipline itself is clean — all four
   fallback claims are defensible (subjectless "says the approval...", "not returned as a valid
   cited fact", and the two pass-result claims are all settled by the instrument the step really
   uses, and the scenario title is never consulted) — but the vocabulary route has no such
   restraint.
3. **AC3 is measured against a reconstruction, not the corpus.** The agreement test feeds each
   assertion to `classify_with_instrument` in isolation with the fixture's recorded
   `binding_layer`, ignoring the recorded `uses_browser` and the real scenario around it. It is
   still a fair yardstick, but a future builder could pass AC3 while the real run disagrees.

## Demo

**The problem.** On the real Demo Product pair, 48 of 94 claims said nothing: the keyword vocabulary knew
a handful of nouns, so half the specimen was `unplaced` and any coverage report built on it
understated the truth.

**What changed.** v0.7: the content/store/HTTP/presentation vocabularies widened to what a claim
about a store, report, sheet or response actually says; page claims no longer require a person
acting; and when the words place nothing, the assertion's own step binding decides (I4/I2/I1 by
layer), with the fallback recorded in `established_by`. A subjectless clause ("And says ...") is
quoted as the step instead of breaking the sentence. `scripts/replay_levels.py` rebuilds the
analyser's inputs from store blobs so the ticket's "re-run over the same snapshot" is actually
possible.

**How we know it works.** My own re-run: 94 claims, unplaced 0, gap 1 (was 1), review 2, distinct
91. Hand-label agreement 19/20 = 95% against a fixture whose sample rule was fixed before
labelling and which contains one label the analyser misses. 90 tests pass in the stripped
environment, up from 84.

**What it does not solve.** The "distinct in name only" risk (concern 2), the interaction-label
inconsistency around engine results (concern 1), the absent build-report artefact (AC8), and the
fact that the level snapshot still does not record its own test-arm artefacts, forcing
`--tests-snapshot` substitution — a product gap the script's docstring itself reports.

**Where to look.** `testops/analysers/level_fitness.py` (CONTENT/STORE/HTTP regexes,
`classify_with_instrument`, `_assertion_phrase`), `scripts/replay_levels.py`, the fixture
`tests/fixtures/level_sample_20.json`, and `factory/reports/2026-11-21/TESTOPS-10-review.md`.
