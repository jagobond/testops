# TESTOPS-29 build report — 2026-11-22

Branch `factory/testops-29-action-prose`, based on `97c0fe8`. Ticket `factory/tickets/TESTOPS-29.md`
(status `blocked`, depends on TESTOPS-28), feature F1.

## Verdict — build complete

The analyser no longer writes a reason where it should write an instruction. Every level-fitness
action states the change; every duplication action states the change. The reason was never deleted:
it is in the statement, which is section 1's argument, and both are asserted. The reviewer's own
repetition measure falls from **2 of 94 to 0 of 94**, the T26 lint passes over the whole corpus with
no exemptions, and the verdicts are 94/90/1/1/2 exactly as before.

## What changed

- `testops/analysers/level_fitness.py` (0.10.1 → **0.10.2**). `_proposed_action` rewritten so each
  verdict's action is the change and nothing else:

  | verdict | before | after |
  |---|---|---|
  | review | `…to call the HTTP client instead of the browser; the response decides everything the browser is being used for.` | `…to call the HTTP client instead of the browser.` |
  | gap | `…into a test that drives a browser, or delete it; at this level nothing establishes what it asserts.` | `…into a test that drives a browser, or delete it.` |
  | unplaced (meta) | `…then re-run; a judgement with no comparison in it cannot be checked at any level.` | `…then re-run.` |
  | unplaced (unbound) | `…then re-run; nothing can be judged until then.` | `…then re-run.` |
  | distinct | `No change: keep the step "…" where it is; this level is the cheapest one that establishes it.` | `No change: keep the step "…" at the cheapest level that establishes it.` |

  The distinct row is the one deliberate exception, argued under AC2 below: its second clause is
  not in the statement (measured - "cheapest" appears nowhere else on a distinct claim's page), so
  it could be relocated nowhere. It is instead folded into the instruction, as a disposition rather
  than a justification, and is one sentence, not two.

- `testops/analysers/duplication.py` (2.0.0 → **2.1.0**). Both branches of `_claim` now write
  `Raise this with the team: keep one.` The clause between the colon and "keep one" was the
  statement restated ("this copy calls the HTTP client to establish what `<file:line>` settles
  in-process"). "keep one" stays, as AC4 requires; the statement still names the copy.

- `tests/test_action_prose.py` (new, 22 cases). The corpus arm, the per-verdict arms and the
  duplication arm described below.
- `tests/test_action_line.py` — the TESTOPS-28 renderer tests are kept, and the fixtures that were
  "the real analyser's shapes" are now labelled as *stored* actions: rows written by 0.10.1 and
  2.0.0 are still in the store and still have to render whole. One test was added for a stored
  two-clause reason tail; `test_a_real_analyser_tail_is_on_the_page_now` now renders today's
  distinct action verbatim.
- `tests/test_proposed_action.py`, `tests/test_case_scan.py` — two strings updated to the new
  vocabulary; no assertion weakened.
- `scripts/measure_action_repetition.py` — the measurement in this report, reproducible from the
  store, including the step-reference substitution that makes the count 2 rather than 5.

## Acceptance criteria

| id | result |
|----|--------|
| AC1 | Met. Every action is one instruction of at most two sentences with no clause restating its statement. Enforced by `test_every_action_in_the_corpus_is_one_instruction_of_at_most_two_sentences` (real 94 claims, rebuilt from the pinned snapshot) plus `test_the_action_no_longer_carries_the_reason_the_statement_gives` per verdict, which asserts the removed clause is absent from the action and its sentence is present in the statement. |
| AC2 | Met, with one argued exception. The three clauses that restated the statement (review, gap, unplaced meta) are gone from the action and are in the statement, unchanged - the analyser never had them in the action alone. `test_the_reason_still_reaches_the_reader_through_the_page` renders section 1 for each and asserts the reason's content is there ("browser"+"settles" for review, "browser"+"nothing" for gap, "compared" for unplaced). The unplaced-unbound tail ("nothing can be judged until then") is the same fact as the statement's "nothing can be said about whether it is checked", and is covered by the same arm. The **distinct** claim keeps its fact - see "The one exception" below. |
| AC3 | Met, measured myself: **2 of 94 → 0 of 94**. Before, from the store: `demo-product-levels-20261122T011316`, the two review claims, sharing the word "browser". After, from the same 94 assertions rebuilt from snapshot `demo-product-levels-20261122-a3f19853-r6`, and again from the fresh run `demo-product-levels-20261122T115115`: 0. Guarded by `test_no_action_in_the_corpus_repeats_a_content_word_between_its_own_sentences`. |
| AC4 | Met. Duplication actions are `Raise this with the team: keep one.` in all 18 claims of the demo-service corpus, asserted by `test_a_duplicate_action_asks_for_one_copy_and_nothing_more`; the finding stays in the statement, which is asserted to name the copy. The T26 lint (`repeated_clause`, `plain_english`, `bare_identifiers`, `straight_quotes`, `detached_punctuation`) fires **0 times over the 94 demo-product pages of the fresh run** and **0 times over the 18 demo-service duplication pages**, unexempted. It is also run per claim over the rebuilt corpus in `test_the_scan_block_of_every_claim_passes_the_no_repeat_lint`. |
| AC5 | Met. `94 claims, 90 distinct, 1 unplaced, 1 gap, 2 review` on the fresh run and on the rebuild, pinned by `test_the_corpus_still_carries_the_verdicts_the_ticket_pins`. Suite green: **337 passed** (`.venv`, Python 3.12.5) and **333 passed, 4 skipped** (Python 3.11.15; the 4 skips are the pre-existing pre-3.12 checks). |

Environment: `PYTHONPATH`, `PYTHONHOME`, `VIRTUAL_ENV`, `CONDA_PREFIX` stripped, `PYTHONNOUSERSITE=1`.

## The measurement, before and after

`scripts/measure_action_repetition.py` — the reviewer's measure, read from the action box as the page
renders it (the quoted step is "this step", so the step's own words are not counted as the action's
prose; without that substitution the count is 5 and includes three false hits inside quoted step
text, which is not what TESTOPS-28's review measured):

```
BEFORE (stored, level_fitness 0.10.1): 94 actions, 2 repeat a content word, 0 carry more than two sentences
  repeated ('browser',): Rewrite this step to call the HTTP client instead of the browser; the response decides everything the browser is being used for.
  repeated ('browser',): Rewrite this step to call the HTTP client instead of the browser; the response decides everything the browser is being used for.

AFTER  (rebuilt, working tree): 94 actions, 0 repeat a content word, 0 carry more than two sentences

after: 94 claims {'distinct': 90, 'unplaced': 1, 'gap': 1, 'review': 2}, snapshot demo-product-levels-20261122-a3f19853-r6
repetition count 2 of 94 -> 0 of 94
```

The same count over the fresh run `demo-product-levels-20261122T115115`'s stored rows: 0 of 94.

## Why the store now holds a second 94-claim run

The analyser changed, so the stored run `demo-product-levels-20261122T011316` still holds 0.10.1's strings -
and that is correct. Versions bump and artefacts are never overwritten, so the fix is a new run
(`demo-product-levels-20261122T115115`, snapshot `demo-product-levels-20261122-a3f19853-r7`), which is what the
product's pages read now. The pinned run is left exactly as it was and the corpus tests that pin the
*renderer* still read it: it is the evidence that a stored two-clause action renders whole, which no
new run can be.

**The case id in the brief therefore moved by one run id, not by content.** The claim is the same
assertion at the same commit; case numbering within a run is unchanged (01 gap, 02 first review,
03 second review). The block below is `case-demo-product-levels-20261122T115115-03`.

## The rendered scan block — `case-demo-product-levels-20261122T115115-03`

(The same claim as `case-demo-product-levels-20261122T011316-03`: `Then each fact's data-fact-id is the same
on both loads`, review.)

Reader text:

```
Checked, but over-tested for what it asserts

The test asserts the step Then each fact's data-fact-id is the same on both loads, but the page the
server sends settles it, and the test drives a browser to read it.

What to do   Rewrite this step to call the HTTP client instead of the browser.
```

Raw block as served:

```html
<section class="scan"><p class="judgement"><strong class="verdict hot">Checked, but over-tested for what it asserts</strong></p><p class="wrong">The test asserts the step <code class="ident">Then each fact&#x27;s data-fact-id is the same on both loads</code>, but the page the server sends settles it, and the test drives a browser to read it.</p><p class="action"><span class="act">What to do</span> Rewrite this step to call the <code class="ident">HTTP client</code> instead of the browser.</p></section>
```

The argument now carries the reason alone, and it is the more accurate of the two sentences that
used to be on the page: the label for this claim is *settled by the page the server sends*, and the
deleted tail said "the response decides everything" - a different instrument from the one the
analyser had just named. The restatement was not only redundant, it was the less correct half.

## The one exception: a distinct claim keeps its level fact

The distinct action used to end "; this level is the cheapest one that establishes it." Under a
literal reading of "state the change, not the reason" that goes too. It does not, for one measured
reason: **nothing else on the page says it.** A rendered distinct case contains no "cheapest"
anywhere - the statement says the run settles the assertion and never says this was the cheapest
level that could. Deleting the clause would delete information, which is the TESTOPS-27 leak in a new
place, and AC2 forbids it. It cannot be relocated to the argument without either inventing a
renderer rule (which TESTOPS-28 exists to prevent) or adding a fact to `wrong_sentence` that no
stored field carries as a reason.

So it is folded into the instruction instead of dropped:

```
before: No change: keep the step "…" where it is. This level is the cheapest one that establishes it.
after:  No change: keep the step "…" at the cheapest level that establishes it.
```

One sentence, one disposition, the fact preserved, and the action no longer reads as "keep it,
because …". `test_the_distinct_action_states_its_level_as_a_disposition_not_a_justification` asserts
it is one sentence, that it says "cheapest level that establishes it", and that the statement does
not contain the fact (which is why it cannot be moved there).

## For the Lead

1. **The distinct exception is a decision you may want to overturn at the ticket, not in code.** If
   you want all 94 actions strictly reason-free, the level fact has to go into the page's argument,
   and that is a renderer change this ticket rules out. As it stands the action box has no clause
   that restates the statement, which is AC1's own wording.
2. **The duplication action is now terse** (`Raise this with the team: keep one.`). It names no copy
   and no level, because the statement one line above names both, and AC4 asked for the restatement
   to go. If a reader is expected to act from the action alone, this is the place to say so.
3. **The corpus tests still pin `demo-product-levels-20261122T011316`.** That is deliberate: it is the run
   whose stored actions have tails, so it is the only evidence that the renderer keeps them. The
   analyser's own behaviour is measured by rebuilding that run's snapshot, not by pinning the new
   run id, so a later re-run cannot move what these tests measure.
