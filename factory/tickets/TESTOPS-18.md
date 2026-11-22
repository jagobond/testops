---
id: TESTOPS-18
title: The response is not the store's mouthpiece
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-12
---

# TESTOPS-18 — Two wording defects from the TESTOPS-12 review

TESTOPS-12 was returned NEEDS-FIX. Both findings are in product code and both are about a sentence
claiming more than the label it carries.

## Defect 1 — a raw label leaked into a sentence

On the two scenarios that carry more than one label in a verification pass, the pass note interpolates the
label itself:

> "…one is about settled by the response the server sends…"

That is a template placeholder filled with a UI label, and the sentence is no longer English. The reviewer
found it; a reader would have found it too, and would have concluded the tool was unfinished.

## Defect 2 — "that answer says what is stored" promotes the response into the store

For an I1 claim (about data as stored) judged `distinct` because an HTTP response reports it, the sentence
reads:

> "The run only reads the responses the server sends, and that answer says what is stored, so the
> assertion is checked."

The label is honest — "settled by the response the server sends" claims only the wire. The sentence is not:
a handler can return cached state or computed values without touching the store, and "says what is stored"
grants the response authority over the disk. As the reviewer put it: a disclosure the reader must undo is
not a disclosure, it is the claim wearing its caveat as a footnote inside the same sentence.

The honest wording already existed in this codebase — run `cotw-levels-20261121T230858` carried the label
"settled by the data as stored, read through the response the server sends" — and was dropped.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | No statement contains a raw `interaction_label` string. A test asserts that no label value appears verbatim inside any statement produced by the corpus. |
| AC2 | The pass note for a multi-label scenario reads as English with no placeholder artefacts; a test covers the two-label and three-label cases and asserts the rendered sentence is grammatical (no label interpolation, no doubled prepositions). |
| AC3 | An I1 claim checked through an HTTP response names the inference as an inference: "takes that answer as the report of what is stored… as far as the response speaks for the store" or wording of equivalent meaning. It must not assert that the response *is* the store. |
| AC4 | The same discipline applies to KP and I2 sentences: each says what the instrument establishes and where the inference stops. I2 may say "the response is the thing asked about"; I1 may not. |
| AC5 | A test asserts the I1 sentence contains the inference marker and that a regression to "says what is stored" (or any phrasing that confers store authority on the response) fails. |
| AC6 | Six real statements from the corpus, printed in the report, read as English with no label leakage and no overclaim. |
| AC7 | Verdicts unchanged: 94 claims, 90 distinct, 1 unplaced, 1 gap, 2 review. Wording must not move a verdict. |
| AC8 | Suite green on both interpreters. |

## Notes

- The reviewer's proposed wording is a model, not a straitjacket: keep the sentences readable to a tester,
  not to a logician. But the direction is not negotiable — the response may be *evidence about* the store,
  never *the store*.
- Do not weaken the disclosure to avoid the overclaim. The fix is to name the inference, not to delete it.
