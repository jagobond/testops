---
id: TESTOPS-32
title: A duplicate claim never shows the copy it names
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-31
---

# TESTOPS-32 — Show the other test

## Finding (Product Owner)

> "It does not, however, give any evidence of the additional scenario that asserts the same thing. Rather, it
> shows me other scenarios around it, never claiming that any of them are the duplicate assertion."

For `case-demo-service-dup-20261122T115216-18` the statement names
`DemoService.Specs.Controller/Features/Question/QuestionSuggestions.feature:17` as the copy that already asserts
this thing — and that file:line never appears on the page. What appears is section 3, "the other steps in this
scenario, for context", which is about the claim's *own* scenario and is correctly labelled as not-evidence.

So the page withholds the one piece of evidence the claim rests on, and shows context in its place.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | For a `duplicate` claim, the page shows a section naming the counterpart: its `file:line`, its scenario title, its steps, and the step definition that runs the asserted step there. It is labelled as the copy the claim names, not as context. |
| AC2 | The counterpart's own table rows / doc strings are shown, so a reader can see for themselves whether the two assertions are the same. Where rows differ, the difference is what makes or breaks the claim, and the page must not hide it. |
| AC3 | The evidence resolves from the claim's recorded coordinates (`established_by` names `file:line`), not by re-parsing the corpus at render time; a missing blob renders the "recorded but not stored" sentence. |
| AC4 | Section 3's context list never appears in place of the counterpart; a duplicate page shows both, and the counterpart comes first. |
| AC5 | A test renders a duplicate case and asserts the counterpart's file:line and at least one of its rows appear in the page text. |
| AC6 | Verdicts unchanged for level fitness; duplication counts change only as TESTOPS-31 dictates. |

## Notes

- If TESTOPS-31 finds the pair is not in fact a duplicate, this ticket still stands: a duplicate page that names a
  copy and does not show it is unfalsifiable, and the reader has no way to check the claim.
