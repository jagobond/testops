---
id: TESTOPS-11
title: Restraint — a claim is not checked because one of its words is familiar
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-10
---

# TESTOPS-11 — Restraint in classification

## Why

TESTOPS-10 took `unplaced` from 48 to 0. The reviewer's independent sample agreed 7 of 8 — and the
one disagreement is instructive:

> "that count is correct for the store it was run against"

The ticket held that sentence up as the example of a claim that is **genuinely ambiguous**, and
allowed up to ten to stay unplaced. The analyser now classifies it `distinct, I1` because the
vocabulary learned the word "store". `distinct` means *checked*; a claim checked only in name is
worse than an honest `unplaced`, because a reader trusts it.

That is the ticket's forbidden move — loosening until the number looks good — arrived at through the
vocabulary instead of through the scenario title. The reviewer also found the same case page telling
three different stories about one verification pass:

> "the pass fails" and "the overall result is a failure" carry the label "settled by the data as
> stored", while "the clean store exits with the success status" in the same file carries "settled by
> the response the server sends" — same run, same answer, three wordings.

## Scope

`analysers/level_fitness.py` only. No schema change, no UI, no pipeline change.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A claim that asserts a *meta* property — that a count is correct, that a report is accurate, that a result is right — is not classified from a generic noun alone. It requires the assertion to say what it compares, or it stays `unplaced`. |
| AC2 | "that count is correct for the store it was run against" is `unplaced` again, and this is asserted in the corpus-level replay, not only in a fixture. |
| AC3 | No other formerly-unplaced claim regresses to `unplaced`: the count stays at or below 3 of 94. A restraint rule may not become a blanket. |
| AC4 | `gap` and `review` verdicts are unchanged at 1 and 2 — restraint must not remove a real finding, and must not add one. |
| AC5 | One verification pass yields one label: assertions settled by the same instrument in the same suite carry the same `interaction_label`, and `_reads(instrument)` is consistent with `interaction_label` for the same claim. |
| AC6 | The label and the statement never contradict each other on one claim — a claim labelled "settled by the data as stored" may not have a statement saying only the server's response was read. |
| AC7 | Suite green (90 tests), determinism unchanged, statements still carry no codes. |

## Notes

- Restraint is the point, not coverage. If AC2 and AC3 fight, AC3 loses: three honest `unplaced`
  claims are better than one false `distinct`.
- The generic nouns to distrust are the ones that appear in almost any sentence: "store", "data",
  "result", "count", "correct". A claim built on one of those alone says nothing about what is
  compared.
- Concern 5 from the TESTOPS-10 review (`_reads` uses the scenario's instrument while
  `interaction_label` uses the claim's) is the likely root of AC5/AC6; fix it at that seam rather
  than papering over the strings.
