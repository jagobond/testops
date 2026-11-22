---
id: TESTOPS-33
title: The case list says "the suggestions list should be", which is not a case
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-32
---

# TESTOPS-33 — A headline a reader would click

## Finding (Product Owner, on the dashboard)

> "On the main dashboard the claim text is, 'the suggestions list should be'. As a user, I would not click on that
> link, as it is neither descriptive of the case claim, nor is it a complete sentence."

The list is rendering the raw `assertion_text` fragment. Even once TESTOPS-31 puts the table back, a bare step
text is not a headline: it says what the step reads, not what the case is about.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Each row shows a one-line headline of the form `<judgement> — <subject>`: the judgement from the verdict vocabulary ("Not proved", "Checked, but over-tested", "Already asserted elsewhere", "Checked") and the subject as the scenario title, falling back to a normalised step text only when no scenario title exists. |
| AC2 | The headline is a complete phrase with no trailing punctuation fragment: a test refuses any headline ending in a preposition or a stopword in a list ("should be", "at", "with", "the"). |
| AC3 | No headline exceeds 90 characters; longer subjects are trimmed at a word boundary and never mid-word. |
| AC4 | The full `assertion_text` remains on the case page; the list does not replace evidence with summary, it stops pretending the fragment is a title. |
| AC5 | The list groups by project and shows the verdict badge, so an `unplaced` claim never reads as confidently as a `distinct` one. |
| AC6 | A test renders the case list for a real run and asserts no row's link text is a raw assertion fragment. |

## Notes

- The same wording rule as the case page applies: a judgement, not a category. "duplicate" is a code; "Already
  asserted elsewhere" is a statement.
