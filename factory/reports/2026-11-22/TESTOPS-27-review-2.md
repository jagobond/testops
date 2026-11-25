# TESTOPS-27 review (second pass, Addendum AC7–AC9) — 2026-11-22

## Verdict — NEEDS-FIX

The eight original probes and the over-correction check both hold (all eight kept; the store's 94
real tails still drop, 94 before / 94 after), but two of the five new probes are genuine orders the
rule still silently drops — "the duplicate is deletable" and "the second one can go" — and a third
shape outside the mandated list ("the copy would be deleted by whoever owns it") is lost the same
way, so AC7/AC8 are not yet met for the morphology an analyser could plausibly write.

## The eight probes — result now

All eight reach the reader; rendered on a duplicate-claim-shaped action, all show the tail as its
own sentence on the page, not merely `True` from the helper:

| probe | result | page rendering |
|---|---|---|
| `this should be split into two steps and the second deleted` | KEPT | `… assertion. This should be split into two steps and the second deleted.` |
| `move it and rename it` | KEPT | `… assertion. Move it and rename it.` |
| `one copy to keep` | KEPT | `… assertion. One copy to keep.` |
| `keep it if the page does not need it` | KEPT | `… assertion. Keep it if the page does not need it.` |
| `you should delete the second one` | KEPT | `… assertion. You should delete the second one.` |
| `instead, delete the duplicate` | KEPT | `… assertion. Instead, delete the duplicate.` |
| `the second copy should be deleted` | KEPT | `… assertion. The second copy should be deleted.` |
| `it is worth keeping one copy` | KEPT | `… assertion. It is worth keeping one copy.` |

The tests exist (`tests/test_action_line.py::test_every_probe_the_reviewer_smuggled_reaches_the_reader`,
parametrised over all eight, asserting the rendered page) and they bite: mutating the vocabulary in
memory (removing the `deleted` form from `INSTRUCTION_FORMS`) fails two tests —
`test_an_instruction_verb_is_recognised_in_every_inflection[deleted-delete]` and
`test_a_passive_or_modal_order_is_an_instruction[the second copy should be deleted]`. (The eight-probe
test itself still passes under that particular mutation because the `should` cue alone keeps the
tail; the inflection and passive tests are the ones that catch the arm.)

## New attacks — each probe and the exact rendering

| probe | result | page rendering |
|---|---|---|
| `the duplicate is deletable` | **DROPPED — order lost** | `Raise this with the team: this copy repeats an assertion.` |
| `removal of the copy is advisable` | KEPT (fails open: "removal" is not a continuation opener) | `… assertion. Removal of the copy is advisable.` |
| `ought to be removed` | KEPT (fails open: "ought" is not a continuation opener) | `… assertion. Ought to be removed.` |
| `would be better gone` | KEPT (fails open) | `… assertion. Would be better gone.` |
| `the second one can go` | **DROPPED — order lost** | `Raise this with the team: this copy repeats an assertion.` |
| `there is no need for this copy` | KEPT | `… assertion. There is no need for this copy.` |
| `both copies are unnecessary` | KEPT | `… assertion. Both copies are unnecessary.` |
| `it must not be kept` | KEPT (the `must` cue correctly overrides the be-passive) | `… assertion. It must not be kept.` |

Beyond the mandated list, extra probes found two more shapes worth recording: `one of the copies
should go` (kept, by the `should` cue even though "go" is not in the vocabulary — the cue saves it),
and `the copy would be deleted by whoever owns it` — **DROPPED**. "Would" is a polite order and is
absent from `ORDER_CUES`, so the participle `deleted` is misread as a descriptive passive
(`descriptive_participles == ['deleted']`). `getting rid of the duplicate is advisable`,
`it requires deleting`, `is supposed to be removed`, `had better be merged`, `is bound to merge` are
all kept.

## Drop counts — before and after, measured

Measured from the store (`data/testops.db`, run `demo-product-levels-20261122T011316`, read read-only from
sqlite directly, not from test output): 94 tails, all with a `"; "` split.

- Before (the bare-stem rule, reproduced in the probe script): **94 dropped / 0 kept**.
- After (the current `second_half_is_instruction`): **94 dropped / 0 kept**. No real tail flipped.
- Verdict counts unchanged from the same store read: 90 distinct, 1 unplaced, 1 gap, 2 review.

AC9 holds: the morphology fix did not turn the corpus into kept noise. (The reason is visible: the
real tails' only vocabulary words are descriptive participles — "is being used", "cannot be checked"
— which the be-passive-without-obligation carve-out correctly excludes.)

## Residual risk — what a future analyser could still write that would be lost

A drop requires the tail to open with a continuation word AND carry no instruction verb in any
inflection AND no `ORDER_CUES` word. What still walks past it, all observed in this pass:

1. **Deverbal adjectives.** "The duplicate is deletable" — the order is carried by an -able/-ible
   adjective the vocabulary does not see. Same family: "removable", "dispensable".
2. **The verb "go" and other non-vocabulary order verbs.** "The second one can go" — "can" is
   deliberately not an order cue (it also appears in descriptions), and "go" is not an instruction
   verb, so nothing fires. "One of the copies should go" survives only by accident of "should".
3. **"Would" as a polite modal.** "The copy would be deleted by whoever owns it" is read as a
   descriptive be-passive because "would" is absent from `ORDER_CUES` — the participle is even
   classified as descriptive. A "would" cue risks over-keeping ("this would be used by…"), so it
   needs the same descriptive/out-of-obligation judgement the be-passive got, not a blind add.
4. By construction the rule still only looks at the clause after the first `"; "` — two orders
   joined any other way (", and ", " — ") are out of scope here, as the first pass already noted.

Suite on the clean invocation: **345 passed** (Python 3.12.5 `.venv`).
