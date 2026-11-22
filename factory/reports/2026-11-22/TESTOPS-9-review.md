# TESTOPS-9 — review

## Verdict

**PASS.** The documented vocabulary in all three places now equals the set I derived independently
from the analyser source, the test bites in both directions against real mutations (four tried, four
failed, worktree restored clean), the corpus counts are exactly 94 = 90/1/1/2 and 17/17, and no
migration ran. One caveat, not a failure of this ticket but worth a decision: the store has **no
verdict CHECK constraint at all**, so an arbitrary verdict string is accepted on insert. That is the
pre-existing state, unchanged by this branch — see below.

## Emitted vs documented (both sets)

Emitted set derived by me from the analyser code (not from the test):

- `testops/analysers/level_fitness.py:664-672` — direct assignments `verdict = "unplaced"`,
  `"gap"`, `"distinct"`, `"review"`, `"distinct"` (the `verdict ==` comparisons at 547-584 are
  conditionals, not emissions; line 706 passes the local).
- `testops/analysers/duplication.py:245` — `verdict="duplicate"`.
- `base.py` and `__init__.py` emit nothing.

Emitted: **{distinct, gap, review, unplaced, duplicate}**.

Documented (read from the working tree directly, not via the test):
- `testops/store/schema.sql:74` column comment: distinct | gap | review | unplaced | duplicate
- `testops/analysers/base.py:27` `Claim` docstring `Verdicts:` line: same five
- `testops/analysers/base.py:35` `Claim.verdict` field comment: same five

Each set equals the other. No name appears in one and not the other, in either direction.

## Does the test bite

Four live mutations, each reverted before the next; `git status` is clean afterwards.

1. Added invented `overbuilt` to the schema comment → failed:
   `schema.sql verdict column names verdicts no analyser emits: ['overbuilt']`.
2. Removed real `duplicate` from the schema comment → failed (mangled parse caught it).
3. Added invented `overbuilt` to the `Claim` docstring → failed:
   `Claim docstring names verdicts no analyser emits: ['overbuilt']`.
4. Cleanly removed real `review` from the docstring → failed:
   `Claim docstring does not document verdicts the analysers emit: ['review']` (line 130, the
   undocumented direction).

Both directions demonstrated against both a doc and a non-schema place. Worktree restored
byte-identically: `git status --porcelain` empty, branch clean at `7acd3de`.

## The CHECK constraint

The dangerous edit did **not** happen — but only because there was never a CHECK to weaken. I
confirmed in a scratch copy of the store (2,310 claim rows, `PRAGMA user_version` = 0) that
inserting a claim with `verdict = 'total_nonsense'` is **accepted** by SQLite. The `claim` table's
only CHECKs are provenance and sources-assessed pairing (`schema.sql:89,102`); no verdict CHECK
exists on this branch, and the build report's history search (only `c67954b "Baseline"` ever
touched `overbuilt` in schema.sql) is consistent with what I see.

The ticket's premise that schema.sql carried "a CHECK mentioning optimal/overbuilt/necessary" was
wrong; the builder corrected only the comment and, in the build report, argued correctly that a
retroactive CHECK would either reject the 128 stored rows under retired names (verified present:
optimal 36, overbuilt 67, necessary 25) or require a migration AC4 forbids. That reasoning is
sound, but the net fact for the record: **today the store will silently persist any verdict
string**; the only guard is the documentation test. Recommend a follow-up ticket to consider a
partitioned CHECK (e.g. `verdict IN (...) OR schema_version < 2`) or a trigger, so the enforcement
is in the store and not only in prose.

## Counts

- Full suite from the worktree with the prescribed interpreter: **514 passed, 0 skipped**
  (3m55s), including the new vocabulary test.
- CotW levels, latest run `cotw-levels-20261122T204947` (queried the scratch store directly):
  **94 claims — distinct 90, gap 1, review 2, unplaced 1**. Matches.
- ReqOverflow duplication, latest run `reqoverflow-dup-20261122T205100`:
  **17 claims, 17 cases, all `duplicate`**. Matches. (Earlier same-day runs hold 18/18 — prior
  snapshots, never overwritten, per the standing rule.)
- No migration: `user_version` = 0, no new migration file in `git diff`, no writer path changed
  (`git diff` = schema comment + base.py docstring/comment + the new test only).
