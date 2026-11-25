# TESTOPS-27 review — 2026-11-22

## Verdict

PASS — the rule is stated in code where it applies, both halves of it are proved by tests that
bite under mutation, the real corpus exercises the drop path 94 times and the keep path through
the duplication analyser's own claims, and the suite is green with verdicts unchanged.

## Criteria

- AC1 — HOLDS. The rule lives in `testops/web/app.py` immediately above the sets it uses
  (`INSTRUCTION_VERBS`, `CONTINUATION_OPENERS`), with the reasoning and the evidence needed to
  overrule it written as a comment. Kept/dropped/fail-open all demonstrated.
- AC2 — HOLDS. `test_a_dropped_tail_is_proved_a_restatement_by_showing_it_cannot_stand_alone`
  reads the head and tail from the analyser's own output, asserts the opener points back at the
  head, asserts no instruction verb anywhere in the tail, asserts the tail is absent from the
  page, and asserts the page shows exactly the proved head — naming both strings.
- AC3 — HOLDS. Kept tail renders as two sentences (`… in-process. Keep one.`), dropped tail as
  one; both shapes have helper tests and a test through `argument_block`.
- AC4 — HOLDS. `test_no_action_on_the_real_run_is_cut_into_a_stub` walks the pinned 94-claim run
  (`demo-product-levels-20261122T011316`, 90/1/1/2), asserts kept ≥ 40 unless the whole action was
  shorter, and proves the "this step" reference is the only shortening. Min kept length in the
  run: 53 characters. It bites: under a mutate-to-always-keep patch the reference-swap assertion
  fails. (It does not bite under always-drop — the cut length is unchanged by dropping; over-drop
  is caught by AC2 instead. Acceptable, noted below.)
- AC5 — HOLDS. "The test asserts the step `Then …`" is built in one place per branch across all
  four verdicts plus the not-assessable branch; the diff shows every `f"The test asserts {q}"`
  became `the step {q}`.
- AC6 — HOLDS. Suite green: 295 passed on the `.venv` (Python 3.12.5), clean invocation as
  specified. Verdicts confirmed in the store on the pinned run: 94 claims, 90 distinct, 1
  unplaced, 1 gap, 2 review.

## Smuggling attempts

| probe | result on the page |
|---|---|
| `…; this should be split into two steps and the second deleted` | KEPT — "split" is a verb the rule knows, so the order survives the continuation opener. |
| `…; move it and rename it` | KEPT — opens with an instruction verb; both orders reach the reader. |
| `…; one copy to keep` | KEPT — "one" is not a continuation opener, so the rule fails open; also contains "keep". |
| `…; keep it if the page does not need it` (lowercase, no apostrophes) | KEPT — lowercasing is applied before matching. |
| `…; you should delete the second one` | KEPT — "you" fails the opener test, fails open. |
| `…; instead, delete the duplicate` | KEPT — "instead" fails the opener test, fails open. |
| `…; the second copy should be deleted` | **DROPPED** — "the" is a continuation opener and "deleted" is not in `INSTRUCTION_VERBS` (only "delete" is). A passive-voice order is silently lost. |
| `…; it is worth keeping one copy` | DROPPED — "keeping" is not "keep". Defensible: it is not an imperative, but it does carry a preference the head does not. |

So of eight probes, six survived and two vanished. Both vanished tails are morphology, not
structure: the rule matches stems, and inflected verbs evade it.

## The drop path

Exercised heavily. In the pinned run, all 94 actions have a tail and all 94 tails are dropped —
every one a restatement (e.g. `this level is the cheapest one that establishes it.`), each proved
by AC2's overlap assertion rather than assumed. The keep path is also exercised on real data: 54
tails in the duplication analyser's runs (e.g. `…; keep one.`) are kept and render as two
sentences, verified by reading the store directly. The drop is safe because every dropped clause
contains no instruction verb and opens with a word whose subject is the head; the head itself is
never shortened below 53 characters on the real corpus, and AC4's reference-swap assertion shows
the page's shortening is exactly the step's own words.

## Three sharpest concerns

1. **Inflected verbs defeat the rule.** "…; the second copy should be deleted" is a genuine order
   and is dropped. A stem-normalising step (or adding participles to the verb set) would close
   it; today the reader silently loses a passive-voice instruction.
2. **AC4 only bites in the keep direction.** Mutating the rule to always-drop leaves the corpus
   floor passing, because a dropped tail does not change the kept length. Over-dropping is caught
   by AC2's three verdict-tail proofs, but a *new* tail shape that is wrongly dropped would only
   fail the AC2 test if someone added it there; the corpus test would not notice.
3. **The pinned run is selected by a query, not a constant.** `ORDER BY COUNT(*) DESC, run_id
   DESC` happens to pin `T011316` today; a re-run of the analyser moves the pin to a run whose
   verdicts and tail shapes may differ. A named run id would make AC4 and AC6 immovable.

## Demo

- **The problem:** `action_line` cut every stored action at the first `"; "` and trusted the tail
  to be a restatement. If an analyser ever wrote two orders in one action string, the second was
  dropped without a trace, and the reader — who believes they hold the whole instruction — cannot
  detect the loss.
- **What changed:** the cut now consults a stated rule (`second_half_is_instruction`): a tail is
  dropped only when it opens with a continuation word and holds no instruction verb anywhere;
  everything else is kept and rendered as its own sentence. The verdict sentence names `Then` as
  a step keyword consistently in all branches.
- **How we know it works:** 295 tests pass on a clean-env `.venv`. The duplicate claim that was
  being cut (`…; keep one.`) now reads `… in-process. Keep one.` from the real store. All 94
  restatement tails in the pinned level run are dropped with AC2 naming both strings; the corpus
  floor holds at min 53 characters; a mutate-to-always-keep patch makes AC4 fail, a
  mutate-to-always-drop patch makes the AC2 tests fail (per the build report; AC4's failure under
  always-keep was reproduced here).
- **What it does not solve:** inflected verbs ("should be deleted", "keeping") still cause drops;
  a run where the tail shape changes is protected only by whatever tests cover that shape; the
  38-character `No change: keep this step where it is.` line is the analyser's copy, not a
  truncation, and only an analyser copy change can lengthen it.
- **Where to look:** `testops/web/app.py` (rule comment, `second_half_is_instruction`,
  `action_line`, `wrong_sentence`); `tests/test_action_line.py` (AC1–AC3); `tests/test_case_scan.py`
  (AC4 corpus floor); `tests/test_case_argument.py` (AC5 assertion).
