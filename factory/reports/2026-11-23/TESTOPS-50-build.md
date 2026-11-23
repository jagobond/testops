# TESTOPS-50 build — every number derivable, or plainly corrected

Branch `factory/testops-50-derivable`. Product code untouched: the diff is `docs/ecosystem-inventory-cucumber-js.md`
and one new read-only tool. Suite green.

## What the three numbers turned out to be

Re-derived from the store copy in `data/` with the blobs read directly, not the module's regexes.

- **"patterns mentioning `{string}`: 29" — wrong unit.** The table counts distinct pattern texts, and that number is
  **28**. 29 is the count of *declarations*, because `Visitor will get validation/mandatory error message: {string}`
  is declared in both `booking.stepdef.js` and `contact.stepdef.js`. The cell now reads `28 (29 declarations)`.
- **"46 of 76" and "29 of 33" — right, but the rule was never written down.** They reproduce exactly under the rule
  now stated beside the table: every `{name}` placeholder becomes one permissive group `(.+?)`, everything else
  (parentheses included) is literal, anchored and case-insensitive. That is, verbatim,
  `testops/extract/stepbindings.py::pattern_to_regex` — the matcher this repository already ships.
- **The reviewer's numbers are the same corpus under cucumber-expression semantics.** With `{string}` as a quoted
  string, `(invalid )` as an optional text group and `{int}` as digits: **38 of 76, 21 of 33**. Widen `{int}` there:
  **48 of 76, 31 of 33**. Both pairs are the reviewers'; both are now printed by the tool. The asserting rows are
  **17 and 26 under every variant**, so the document's conclusion never depended on the contested rule.

The "no rule gives 46" finding is therefore not quite right — one rule does, the repository's own — but the document
gave the reader no way to know which rule it had used. That was the real defect, and it is now stated.

## Changes

- `docs/ecosystem-inventory-cucumber-js.md`
  - §1: counting rule printed beside the table — scenario vs `Examples:` row, Background exclusion (**87 step lines,
    11 Background: 6 Given, 5 And, 76 scenario steps**), `.js`/`.ts` includes `index.d.ts`, scenario tags vs feature tags.
  - §2: duplicate-pattern rule stated; `{string}` row corrected to 28 (29 declarations); union arithmetic shown
    (15 + 28 + 5 − 5 = 43).
  - §4: `.as(` count filled in (18) rather than a dash.
  - §5: full matching rule beside the table; variant note recording 38/21 and 48/31 and that 17/26 are invariant.
  - New **Corrections, 23 November 2026** section at the end: says plainly which count was wrong, which was only
    unstated, and why the reviewer got different auxiliary numbers.
  - §7 estimate untouched, as instructed.
- `tools/ecosystem_inventory_counts.py` — recomputes every counted table and prints it with its rules, from the store
  with `mode=ro`. Not under `docs/`.

## Verification

- **AC4:** every integer in every counted table of the final document appears in the tool's output, checked
  mechanically by extracting table cells and diffing against stdout. The only document integers absent are §7's
  engineering-day estimates (out of scope) and the 142 `.java` files its notes mention — never fetched, so no blob can
  confirm them; the tool prints both facts as "not derivable here" rather than pretending.
- **AC3, touching nothing:** `sha256sum data/testops.db` is byte-identical before and after a full run; no `-wal`/
  `-shm` files are created. The tool opens the store read-only and never writes.
- **AC5:** no product code in the diff. Full suite, from `.venv` with `PYTHONPATH`/`PYTHONHOME`/`VIRTUAL_ENV`/
  `CONDA_PREFIX` stripped and `PYTHONNOUSERSITE=1`: **583 passed in 125.61s**.
- The five previously confirmed headline numbers are unchanged: 44 declarations, 16 multi-line, 11 real custom
  commands, 17 of 43 asserting steps, 26 matching nothing.

## One note for T42-C

If the target matcher is cucumber's own expression semantics rather than `pattern_to_regex`, the auxiliary rows to
quote are 38/21, not 46/29; the document now carries both, and either way the placement claim is 17 of 43.
