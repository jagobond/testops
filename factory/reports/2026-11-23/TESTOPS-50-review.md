# TESTOPS-50 review — reviewer, 23 November 2026

Interpreter: `env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1 C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe`,
store copy in `data/`, snapshot `demo-booking-levels-20261122-262404a9-r3`.

## Verdict

**Accepted.** The tool reproduces every integer this review demanded, the two numbers I re-derived by
hand agree with both the tool and the document, both arithmetic claims are true of the corpus (not
just of the document), the corrections section names what was wrong and what was merely unstated and
quotes the original figures, the store is untouched, product code is untouched, and the suite is
green (583 passed in 132.85s). The reconciliation story is not merely convenient: `pattern_to_regex`
genuinely produces 46/29, and the asserting rows are invariant at 17/26 under every variant printed.

## The tool reproduces

`tools/ecosystem_inventory_counts.py` run from this worktree, exit 0. Every demanded integer appears
in its stdout: **44** declarations, **16** multi-line, **11** real custom commands, **28** distinct
`{string}` patterns with **(29 declarations)**, **46** of 76, **29** of 33 (When), **38** of 76 and
**21** of 33 under cucumber-expression semantics, **48** and **31** under permissive-`{int}` cucumber,
**17** of 43 and **26** of 43 asserting — and 17/26 are printed under every variant. No integer
failed to appear. The tool also states its rules (R1–R4) before counting, matching the document's
prose.

## Two counted by hand

My own scanner, independent of `pattern_to_regex` and of the tool's implementation, over the stored
blobs (via `artefact` + `data/blobs`):

- **Multi-line layouts: 16.** 44 total declarations found by a line scan for `(When|Then|Given)\(` in
  the 5 `*.stepdef.js` files; 28 open with the pattern on the same line, 16 leave the parenthesis
  bare at end of line (e.g. `booking.stepdef.js`'s `When(\n  'Visitor {string} {string} with an
  (invalid )email…'`). 16/28, as the document claims.
- **Custom commands: 11.** 15 raw `Cypress.Commands.add|overwrite` occurrences; 4 sit in comment
  lines/blocks; 11 real, split booking.js 2, login.js 2, messages.js 1, room-management.js 6 —
  matching both the tool and §3's table.

Tool, document and blobs agree three ways on both.

## The arithmetic

- **15 + 28 + 5 − 5 = 43** — verified against the blobs, not the document: my own pattern extraction
  gives 15 no-placeholder, 28 mentioning `{string}`, 5 mentioning `{int}`, 5 mentioning both, 44
  declarations / 43 distinct / 1 duplicate. Union is exactly 43.
- **87 step lines = 11 Background + 76 scenario** — my own walk of the 6 `.feature` blobs gives 87
  total step lines, 11 under `Background:` (the tool reports their split as 6 Given + 5 And; the
  11/76 denominator split is confirmed), 76 in scenario bodies. Both claims hold of the corpus.

## Corrections, honest or tidy

Honest. The section (docs §"Corrections, 23 November 2026") quotes the original figures rather than
erasing them: **"`patterns mentioning {string}: 29" was wrong**… The original mixed two units
without saying which it used" and **"46 of 76" and "29 of 33" were right, but their rule was never
stated** — which, in a document whose argument is "counts, not estimates", is the same defect." It
correctly does not pretend the reviewer's 38/21 were errors; it records them as the same corpus
under different semantics and prints the variant. The diff's deletions are exactly the superseded
cells; §7 is untouched (no estimate line appears in the diff).

## Read-only

`sha256(data/testops.db)` = `123df9d2e7542ac0cf4732af825f2af3293865f1ff4ec81800a0c36af74462df`
before and after the full tool run — identical. No `-wal` or `-shm` file exists after the run; the
tool opens the store `mode=ro`.

## Scope

`git diff --stat origin/main...HEAD -- testops/` is **empty**. The branch touches only the document,
the tool, and factory files. Suite: **583 passed in 132.85s** from the `.venv` with the environment
variables stripped.

## Three sharpest concerns

1. **The variant labels reattribute my own numbers.** My TESTOPS-42A review reported 38/21 under
   "`{int}` = `\d+`"; the tool prints 36/19 for that variant and 38/21 under cucumber-expression
   semantics. The pairs are all printed and 17/26 is invariant, but the reconciliation narrative
   quietly reassigns which rule produced which auxiliary pair — an honest-corrections standard
   should label the reviewer's original attribution as well, or show that the difference is scanner
   anchoring, not semantics. It does not.
2. **AC4 is one implementation checking itself.** The tool and the document were written together
   against the same `pattern_to_regex`; my hand counts cover §2's two layout tables, but §4's
   signal counts (e.g. `.as(` = 18) and §5's 46/29 still rest on a single regex implementation the
   builder chose because it reproduces the disputed numbers. The invariance of 17/26 is the real
   safeguard; the auxiliary rows remain one-implementation-deep.
3. **§8's historical claims are unverifiable by counting.** "The first version of this ticket's own
   detector missed exactly those 16 and reported 28" and the run-page sentence are narrative, not
   counts; no blob can confirm them. AC1 is met for every countable number, but the document still
   carries two sentences of the adjective kind it opens by forswearing.
