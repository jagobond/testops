# TESTOPS-36 review — cross-reference between analysers

Reviewed: commit 1013366 (the tip commit; `origin/feature/f1..HEAD` also contains unmerged
TESTOPS-33/34 work from the f1 branch that is not this ticket's change — see concerns).
Tests: `pytest` from the worktree root with the shared `.venv`, env stripped per AGENTS.md —
373 passed, 7 skipped; `testops.__file__` confirmed inside this worktree
(`C:\Users\<name>\Projects\testops-t36\testops\__init__.py`).

## Verdict

PASS — every cross-reference generated resolves, none of the four adversarial stores made it lie,
and the one sentence I would reword is not false, merely narrower than the situation it can describe.

## Criteria

- AC1 HOLDS. `queries.cross_references` (testops/queries.py:1091) keys on stored
  `assertion_path`+`assertion_line`+`assertion_commit`, one entry per analyser, only when a finding
  names the claim; `app.also_reported_block` (testops/web/app.py:667) renders
  "Also reported by <analyser>: <line>. Read that case." on both pages. Verified by render, not
  just by the build's tests.
- AC2 HOLDS, with a wording note. The level page says "fixing the level here does not remove the
  duplication" — true in every construction I tried, including when the duplication's action is
  "keep one" (deleting a copy removes the duplication, not the level fix, so the sentence stays
  true). The duplication page's converse is the weaker one — see concerns.
- AC3 HOLDS. Nothing is re-analysed; the query reads stored rows only, and a counterpart with no
  case (its claim never raised) yields `[]` — exercised both by the build's
  `test_a_counterpart_with_no_case_renders_nothing` and my own probe.
- AC4 HOLDS. The build's test asserts byte-for-byte equality of a single-reported page before and
  after adding a counterpart at a different commit; it passes.
- AC5 HOLDS. `tests/test_cross_reference.py` builds both directions and both one-sided shapes;
  all pass.
- AC6 HOLDS. Suite green; verdict badges unchanged on every page I rendered ("Checked, but
  over-tested…", "Checked, but this repeats another test").

## Links

The real store (`C:/Users/<name>/Projects/testops/data/testops.db`, copied read-only) contains
**zero** cross-analyser shared coordinates — no path+line+commit, and not even path+line, is
claimed by both `level_fitness` and `duplication`. So no cross-reference is generated on the real
corpus; all 184 case pages were rendered and none contains `<aside class="xref">`. The brief's
"17 shared coordinates" did not reproduce: the store's 94 multi-claim coordinates are all
same-analyser level_fitness rows (latest verdicts: distinct/unplaced/gap/review). The silence is
genuine and structural either way.

In my fixture stores, every generated cross-reference was followed:

- lie3 (one side resolved): level page → `/case/c2` → 200; dup page → `/case/c1` → 200.
- lie4 (level verdict `distinct`): same, both directions 200.

Both link targets render under 200 with their decision badge visible; no dead reference found.

## Lies attempted

1. Same path+line, **different commits**: neither page renders the section. Correct per AC3's
   exact-coordinate rule, but note it is a hard silence — two analysers judging the same step
   across a re-analysis go unlinked (see concerns).
2. Same commit, **different lines**: silent on both pages. Correct — different step.
3. Same coordinates, duplication case **resolved**, level case open: the section renders on both
   pages and both links resolve. Not a lie: the reference says the other analyser raised the step,
   which the store proves, and the linked page carries its "Resolved" badge. A reader is not told
   the duplication still stands.
4. (bonus) Level verdict `distinct` against a duplicate: the level page reads "already asserted at
   the level it should be … fixing the level here does not remove the duplication" — coherent, no
   contradiction manufactured between the two verdicts.

## Sentence scrutiny

Quoted from the rendered level page: "This step is also reported as duplicating
`Other.feature:5`; fixing the level here does not remove the duplication." True in every
construction, including "keep one" — the duplication ends only by deleting a copy, which no level
fix does. The duplication page's mirror, "deciding which copy to keep does not change the level
the remaining test runs at," is literally true in both branches, but it glosses the branch a
reader most needs: if **this** copy is the one deleted, the level claim on this page is settled
with it, not merely "unchanged". I would word it: "…does not settle the level claim — if this
copy is the one kept it still needs a level fix; if it is the one deleted, the level claim here
is closed with it." That is two clauses, which the ticket's Notes say is a design signal — so at
minimum the Lead should accept the current sentence knowingly, as a deliberate shortening.

## Three sharpest concerns

1. **Commit-fragility of the identity key.** The code comment asserts "each analyser writes its
   own snapshot over the same commit", but nothing enforces it. Lie-1 shows the consequence: after
   any re-analysis at a new commit, a real counterpart goes silently unlinked. The section does
   not lie — it goes dark exactly when the duplication has just been re-confirmed. Consider a
   fallback on path+line with the commit difference stated.
2. **The duplication-page sentence is narrower than the decision it sits beside.** See scrutiny
   above; "keep the other copy" is the reader's likeliest action and the sentence's least helpful
   branch.
3. **The stated diff is not the ticket.** `origin/feature/f1..HEAD` shows −1,924/+391 lines
   because f1 carries unmerged TESTOPS-33/34 work (its tip 664928d is not an ancestor of HEAD,
   despite the TESTOPS-35 merge). This branch does not contain f1's `run_read`/`list_runs`/
   `case_lead` features. Merge state should be reconciled before the next f1-dependent ticket, or
   the factory will review phantom regressions again. (Scoping note, not a defect of this build.)
