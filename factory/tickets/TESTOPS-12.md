---
id: TESTOPS-12
title: Labels finish the job, and restraint stops being a be-verb pattern
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-16
---

# TESTOPS-12 — Classification polish

## Why

Three defects, all recorded by reviewers on earlier tickets rather than guessed at here.

**1. One verification pass, several labels.** TESTOPS-11's review found eleven scenarios in the corpus
still carry two or three `interaction_label`s inside a single verification pass. "The pass fails" and
"the overall result is a failure" say "settled by the data as stored" while "the clean store exits with
the success status" in the same file says "settled by the response the server sends". The builder
satisfied the pass the reviewer pointed at (all 12 engine claims now share a label) and declined the
literal criterion as unsatisfiable; the remaining eleven were never finished.

**2. Restraint is a narrow pattern.** TESTOPS-11's restraint rule matches be-verbs ("is correct",
"is accurate"). A compound sentence can carry a checkable claim beside a meta one, and a claim that
merely uses different wording — "that number comes out right" — slips through.

**3. Every claim statement opens with "This test…".** Visible in the corpus: "This test asserts that…
This test only reads the responses the server sends, which settles that, so the assertion is checked."
Repetition inside one sentence, and the same opener on all 94.

## Addendum from the TESTOPS-16 review

| id | criterion |
|----|-----------|
| AC-b | State (a) says "it predates observation recording", asserting *why* a run recorded nothing. A zero count cannot prove that. Say what is known ("this run holds no observations") and give the reason only where the store can show it. |

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Every scenario in the corpus carries exactly one `interaction_label` per verification pass, or the page says why not. No scenario has two labels without an explained reason. |
| AC2 | A compound assertion containing a checkable claim and a meta claim is not unplaced by the meta half; a test covers a sentence of each shape. |
| AC3 | Restraint recognises the meta vocabulary by meaning rather than by a be-verb pattern; the sentence "that number comes out right" is unplaced, and the corpus still holds at ≤3 unplaced. |
| AC4 | Claim statements no longer begin with "This test" on every claim: vary the opener by claim kind, and no sentence repeats its own subject within one statement. |
| AC5 | Verdicts unchanged: 94 claims, 90 distinct, 1 unplaced, 1 gap, 2 review. Readability changes must not move a single verdict. |
| AC6 | Suite green on both interpreters (CI enforces this now) and no codes in reader-facing text. |
