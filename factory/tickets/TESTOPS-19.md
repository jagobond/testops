---
id: TESTOPS-19
title: The case page opens with the answer, and shows the code
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-18
---

# TESTOPS-19 — Summary first, code inline

## Why

Two findings from the Product Owner's review of
`case-demo-product-levels-20261122T011316-03`:

> "It needs a summary at the top which includes a finding statement and a proposed solution. A user needs to
> be able to do a quick scan of the case to determine if it's worth their time."

> "Where there is code reference as evidence, present those code snippets in the case page. I want to see the
> code in question in this case page; I should only need to click on the link if I want to see the code in the
> context of the rest of the codebase."

Today the page opens with a verdict badge and then six sections; a reader must assemble the argument themselves.
And evidence is a set of links, so the reader leaves the tool to find out whether the case is worth reading.

## Part 1 — the summary block

Above section 1, before anything else:

1. **What this is** — one sentence, the claim's own statement, whole and untruncated.
2. **What to do** — one sentence, the claim's proposed action.

Two sentences, then the six sections as they are. The summary is derived from stored rows (`claim.statement`,
`claim.proposed_action`), never re-worded in the template, so it cannot drift from section 4.

## Part 2 — code inline

For a v2 claim, the page shows at these coordinates, in the page itself:

- the **asserting step's source lines** from the feature file, ±2 lines of context, line numbers, the asserted
  line marked;
- the **step definition's body** that runs it, up to ~10 lines with its file and line, marked as the step that
  is asserted;
- each snippet carries a "view in repository" link for context. The link is for context; reading the code must
  not require it.

Blobs are content-addressed (`testops/blobs.py`, `artefact.blob_sha`), so this is offline by construction.
A snippet the store cannot produce says so — "the source was recorded but its content is not in this store" —
rather than showing a broken box or silently omitting the evidence.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The summary block is the first content on the page, before the verdict badge and before section 1, and contains the claim's statement and its proposed action, verbatim from the store. |
| AC2 | The summary fits within the first screenful at 1280×800 for every case in the corpus: a test renders each and asserts the summary's offset plus height is under 800px in the DOM-free HTML layout sense, or — if a browser is unavailable in tests — asserts the summary is the first block and contains no more than two sentences plus labels. State which you did and why. |
| AC3 | A claim with no proposed action (v1, duplication) renders a summary that says what is missing rather than inventing one, and the page still opens with the finding statement. |
| AC4 | No truncation mid-sentence: if the statement is longer than the summary allows, the summary shows its first sentence complete; section 4 always holds the full text. |
| AC5 | The asserting step's source appears inline with line numbers and the asserted line marked, read from the stored blob at the claim's own commit. |
| AC6 | The step definition that runs the assertion appears inline with its file:line, marked as the step that is asserted. |
| AC7 | Every snippet is HTML-escaped: a feature file containing `<script>` and quotes renders as text. Test with a hostile fixture, both in the feature snippet and the step-definition snippet. |
| AC8 | A claim whose blob is missing renders the "recorded but not stored" sentence; no exception, no empty box. |
| AC9 | No network access at render time; the page still renders from the store alone. |
| AC10 | Verdicts unchanged: 94 claims, 90 distinct, 1 unplaced, 1 gap, 2 review. |

## Notes

- The point of the summary is a go/no-go scan in about five seconds. If it needs a heading of its own, it is
  too long.
- Do not put the decision form in the summary: a decision made from two sentences without the evidence is how
  a team silences a finding it never read. Summary first, evidence next, decision last.
