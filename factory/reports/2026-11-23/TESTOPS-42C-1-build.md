# TESTOPS-42C-1 build — the cucumber-js parsing floor

Branch `factory/testops-42c1-bindings`. Part 1 of 3: declarations and matcher only. Claim placement is
not wired; the ecosystem still reports unsupported, so the restfulbooker run is still `not_assessable`
with zero claims. Analysers and pipeline are untouched.

## Changes

- `testops/extract/ecosystems/cucumber_js.py`
  - `DECLARATION` is a single multi-line expression; the gap between `(` and the quote is captured and
    may contain `\n`. Layout is recorded as `same-line` or `next-line`, never inferred by a second,
    line-oriented scan.
  - `parse_declarations(files)` returns `Declaration` rows: verb, pattern text, path, 1-based line of
    the keyword, quote, layout, regex flag, `this.` flag.
  - `bindings(files)` returns `Binding` rows (verb, pattern, path, line, suite; `layer="unknown"` —
    T42C-2 owns the vocabulary). Regex literals are **explicitly refused** with the file and line;
    they are also counted in the detection evidence. Nothing is silently skipped.
  - `suite_of_path(path)` uses the containing directory — the corpus co-location rule. The existing
    stem rule is applied to that directory, so features and step definitions resolve to one key.
  - `detect()` now reads the same parser, keeps the 44-in-5-files evidence line, and adds the
    layout split and the regex-literal support statement to the record.
  - `supported` remains `False` and `drivers()` still refuses. The pipeline's `readable` gate is
    therefore still shut, which is what keeps this ticket from placing a half-wired claim.
- `testops/extract/stepbindings.py::pattern_to_regex` — `{int}` → `\d+` before the generic
  placeholder substitution. `{string}` remains `(.+?)`; parentheses and dots remain literal;
  anchored and case-insensitive as before.
- `tests/test_cucumber_js_bindings.py` — new; `tests/test_ecosystems.py` — the 42A refusal test now
  asserts the declaration parses while the ecosystem and drivers still refuse.

## Corpus counts

`python tools/ecosystem_inventory_counts.py` (read-only, store `restfulbooker-20261122-262404a9`):
44 declarations in 5 files; When 26, Then 13, Given 5; single-quoted 44; same-line 28, next-line 16;
43 distinct patterns; one duplicate in two files; 6 features. The parser's own counts match these
exactly (asserted in tests, not by eye).

## Suite scoping — measured, not assumed

| feature | feature directory | owning step-def file |
|---|---|---|
| `login.feature` | `login` | `login.stepdef.js` |
| `room-management.feature` | `management` | `room-management.stepdef.js` |
| `book-a-room.feature` | `booking` | `booking.stepdef.js` |
| `book-a-room-invalid-validation.feature` | `booking` | `booking.stepdef.js` |
| `contact-hotel.feature` | `contact` | `contact.stepdef.js` |
| `contact-hotel-invalid-validation.feature` | `contact` | `contact.stepdef.js` |

Five step-definition files give five distinct suites (`login`, `management`, `booking`, `contact`,
`support`); all six features resolve to the suite of their directory (6 of 6). `support/background`
owns no feature directory and is reached by the any-suite fallback for its five Given steps.

**Finding against the inventory's wording.** The *filename* stem rule does not work on this corpus:
`stepbindings.suite_of` strips `js` but not `stepdef`, so `booking.stepdef.js` yields
`bookingstepdef`, and it yields `loginstepdef` … `backgroundstepdef`. Measured with that rule,
0 of 5 step-definition files match a feature and 0 of 6 features resolve. The rule that does work is
the co-location rule the inventory states in the same cell ("a `.feature` beside a `.stepdef.js`"):
the directory. The implementation uses that rule, and the tests prove 5 of 5 files and 6 of 6
features. This is a measurement of the claim, not a change to it in the report.

## Acceptance criteria

- **AC1** — `bindings()` returns 44 rows from 5 `*.stepdef.js` files: 26 When, 13 Then, 5 Given. Each
  row carries verb, pattern, path, 1-based line and suite; the test re-reads each declaration's line
  from the blob and checks the verb appears there.
- **AC2** — 28 same-line and 16 next-line declarations. The scanner is one multi-line expression; the
  test that counts layouts would fail under a same-line-only implementation (which reports 28).
- **AC3** — single, double and backtick forms are parsed in a synthetic fixture; the corpus is 44
  single-quoted. A regex literal makes `bindings()` raise `UnsupportedEcosystem` naming
  `path:line`, and `detect()` prints "1 regex-literal declarations; … unsupported".
- **AC4** — unit tests pin: `{int}` matches digits and not `4.5`/`ten`; `{string}` stays permissive;
  `(invalid )` and `.` are literal; the expression is anchored (`re.match` rejects prefixed/suffixed
  text) and case-insensitive.
- **AC5** — the duplicate resolves to `booking.stepdef.js` for suite `booking`, to
  `contact.stepdef.js` for suite `contact`, and falls back to the same pattern when the suite is
  `login` (neither). Both directions tested.
- **AC6** — 6 features, 5 step-definition files, 5 distinct suites, 6 of 6 features resolved (table
  above).
- **AC7** — no claim placed. `detect().supported is False`, `drivers()` still raises, and the
  existing real-corpus test still sees `assessment.state == "not_assessable"` with `claims == []`.
  The pipeline and analysers have no diff.
- **AC8** — .NET and Python unchanged: CotW 94 claims, ReqOverflow 17/17 and case-page goldens are
  covered by the suite and all pass. Full suite: **596 passed in 137.97s** (from the project `.venv`
  with `PYTHONPATH`, `PYTHONHOME`, `VIRTUAL_ENV`, `CONDA_PREFIX` stripped and `PYTHONNOUSERSITE=1`).

## Left for T42C-2 / T42C-3

- Layer vocabulary over declaration and command bodies (T42C-2), so `Binding.layer` can stop being
  `unknown`.
- Feature-side suite lookup must use `cucumber_js.suite_of_path` (or the same directory rule), not the
  filename stem; otherwise booking's features fall through to the any-suite fallback.
- Flipping `supported` to `True` and allowing `readable` to open is T42C-3. Until then the run keeps
  the pre-existing refusal sentence and places nothing.
