---
id: TESTOPS-40
title: Say what a decision covers, and stop a shifted twin from silencing one
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-37
---

# TESTOPS-40 — The cover of a decision

## Finding (TESTOPS-37 review)

Decisions hold and reverse — proven. But what a decision *covers* is nowhere stated, and one of the boundaries is
silently wrong:

1. **The commit is not part of the identity.** Decide a finding against last month's snapshot and it stays silent
   against today's. Defensible — the finding is about the test, not the code — but undocumented, so it reads as an
   accident.
2. **Two identical assertions in one scenario are told apart by occurrence order** (`interaction|words#n`). Delete
   the first and the survivor's index shifts from `#2` to `#1`, so a decision recorded against it stops covering it,
   **silently**. This is the one place where the line would have been the safer key.
3. **Data-table content is invisible to the identity.** Change a scenario's test data and a decision stays silent.
   Defensible for an assertion about a list; not obviously right for a scenario whose inputs changed.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The case page states, in one sentence, what a decision covers: same scenario, same interaction, same assertion words — any commit, any test data — and that renaming or moving the scenario asks again. Written in the reader's language, passing the existing prose lint. |
| AC2 | The commit-insensitivity and data-insensitivity are pinned by tests that would fail if either changed, so the contract is enforced rather than described. |
| AC3 | **The twin case stops being silent.** When identical assertions are disambiguated by occurrence order and the count for a scenario changes between runs, a decision that was covering one of them must either keep covering it or be reported as needing judgement — never quietly stop covering. Test: two identical assertions, decide the second, delete the first, re-run, and assert the reader is asked again (or the decision still holds); what must not happen is silence with a changed index and no notice. |
| AC4 | Whatever resolution AC3 takes is also stated on the page in the same sentence as AC1 — the reader should not need this ticket to understand a re-ask. |
| AC5 | No verdict or claim counts change; existing runs untouched; suite green on 3.11 and 3.12. |

## Notes

- AC3 is the only behavioural change here. If the honest resolution is "re-ask", say so on the page rather than
  engineering a line-based key that would resurrect decisions on every reformat.
- Do not fix the commit question by adding the commit to the fingerprint — that would re-ask on every deploy.
