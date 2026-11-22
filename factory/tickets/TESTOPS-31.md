---
id: TESTOPS-31
title: Duplication calls two scenarios the same when their tables differ
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-29
---

# TESTOPS-31 — The table is part of the assertion

## Finding (Product Owner, reviewing the live pages)

> "It tells me, 'The test asserts the step Then the suggestions list should be, but another scenario in this run
> already asserts the same thing, so the project runs it twice.' It then gives me the BDD code in question. It
> does not, however, give any evidence of the additional scenario that asserts the same thing."

Investigating that complaint found something worse than missing evidence. The two scenarios are:

**`QuestionSuggestions.feature:17`** (the copy the claim calls "already established"):

```gherkin
Then the suggestions list should be
    | title             |
    | What is Reqnroll? |
```

**`QuestionSuggestions.feature:39`** (the claim itself):

```gherkin
Then the suggestions list should be
    | title             |
    | What is Reqnroll? |
    | Question 2        |
    | Question 3        |
```

They assert **different lists**. They are not duplicates. `testops/extract/gherkin.py:117` says so in a comment:
"doc strings and tables inside steps carry no extra weight for this analysis", and `normalise()` parameterises
digits, so the signature is step *text* only. Any two scenarios with the same step wording and different data
collapse into one claim, and the page then tells the reader the project runs the same test twice when it runs two
different ones.

The claim's `assertion_text` has the same root cause: it reads "the suggestions list should be", which is not a
sentence and not an assertion, because the meaning was in the table that was dropped.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A scenario's signature includes the rows of any data table attached to a step and the text of any doc string, so two scenarios differing only in table content are **not** duplicates. |
| AC2 | `assertion_text` carries the table (rows inline, e.g. "the suggestions list should be: What is Reqnroll?", or the full table rendered as data) so the claim states something a reader can check. Never a sentence that ends in "should be". |
| AC3 | Re-running duplication on `reqoverflow` reports how many claims were previously declared duplicates on step text alone, and how many survive once the table is part of the signature. Report the before/after counts per scenario pair; state each pair's differing rows. |
| AC4 | A test pins the exact pair above as NOT a duplicate, and keeps a genuinely identical pair (same text, same rows) as a duplicate, so the fix cannot be "stop reporting duplicates". |
| AC5 | Existing duplication runs are not rewritten; only new runs carry the corrected signatures. Old pages keep their stored text. |
| AC6 | Level-fitness corpus untouched: 94 claims, 90 distinct, 1 unplaced, 1 gap, 2 review. |

## Notes

- The comment at `gherkin.py:117` was a considered decision — it kept the duplication analyser simple. It is wrong
  for this corpus, and the cost is a reader being told their project runs a test twice when it does not. Replace
  the comment with the reason tables are now included.
- Parameterising digits in `normalise()` is also part of this: "12 questions" and "3 questions" are different test
  data, and the analyser should say so rather than call them the same. If changing that floods the corpus with
  duplicates-that-are-not, report the count and stop rather than tuning until the number looks nice.
