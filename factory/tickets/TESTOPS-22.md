---
id: TESTOPS-22
title: A quiet run is not a resolved case
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-21
---

# TESTOPS-22 — What actually happened in this run

## Why

The Product Owner opened `case-demo-product-dup-20261120T194032` and asked:

> "Is this resolved because of a test of the application? If so, I find no information here about what was
> actually done, which I would expect. Otherwise, it looks like another application defect."

He asked a fair question of a page that gives him no way to answer it. The run had **zero findings** — the
duplication analyser found no duplicate coverage in 41 scenarios — and the page says:

> **Resolved** — "This case is resolved: the analysis raised nothing to act on. That is a result, not an
> error — and not a claim that the code is clean, only that nothing in this run fell short."

Three problems in that:

1. **"Resolved" is a decision word.** `case_state.resolved` means a person decided to stop reporting this
   claim. A run that raised nothing has had no decision taken. Using the same word for both means the page
   cannot tell the reader whether a human acted, and a reader will assume someone did.
2. **Nothing says what was analysed.** No feature count, no scenario count, no `.csproj` exclusions, no commit
   context beyond the freshness line — so "nothing to act on" is unfalsifiable.
3. **Nothing says what the run could not consult**, so a reader cannot tell "no duplicate coverage exists" from
   "we could not look at two thirds of the suite".

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A run with no findings renders a heading and sentence that describe the run, not a decision: "No findings in this run" plus one sentence saying what was analysed. |
| AC2 | "Resolved" appears only where a `case_state` row with state `resolved` exists, and the page then names who resolved it, when, and the note. The two states never share wording, and a test covers both from stored rows. |
| AC3 | The quiet page states what was examined: features, scenarios, exclusions (counted from the `.csproj`, by the same reader the analyser uses), and the analyser's own coverage of those scenarios. |
| AC4 | The quiet page states what the run could not consult, from the recorded registry state — never from a config re-read at render time. |
| AC5 | The quiet page keeps the freshness line (last analysed at which commit) and the analyser name. |
| AC6 | A test builds a run with zero findings and a run whose case was genuinely resolved, and asserts the two pages differ in heading, body and state badge. |
| AC7 | No verdict changes; level-fitness corpus numbers untouched. |
| AC8 | Suite green on both interpreters. |

## Notes

- The distinction is the same one TESTOPS-16 and TESTOPS-17 drew for evidence and sources: two different
  facts must not wear the same word. A quiet run is a fact about the code; resolved is a fact about a decision.
- Do not claim coverage percentages. State counts that the store can prove.
