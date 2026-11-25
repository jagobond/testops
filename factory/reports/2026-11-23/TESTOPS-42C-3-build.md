# TESTOPS-42C-3 build — placement: 17 of 43, and the other 26 told the truth

Part 3 of 3. cucumber-js is now a supported ecosystem: the declarations are read, the commands
followed, and a layer placed where the call graph reaches one.

## The number

**On the demo-booking corpus the level-fitness run places 17 of 43 asserting steps and leaves 26
unplaced.** The run's own `placement` record says `asserting 43, placed 17, unplaced 26, layers
{ui: 17}`; the claim set is 43 claims (13 distinct, 4 review, 26 unplaced). I measured 17/43 before
writing any wiring and it did not move afterwards; no tuning was done to reach it.

The 26 are a **corpus problem, not a tool problem**. Every one names a validation or mandatory
error message while the only declarations that exist say `Visitor will get …` or `User will get …`.
Each unplaced claim's statement reads, for example:

> The step reads "User will get mandatory error message: 'Room name must be set'", but no binding
> matches these words. The two nearest patterns are "User will get validation/mandatory error
> message: {string}" and "Visitor will get validation/mandatory error message: {string}".

Neither "unsupported ecosystem" nor "could not be tied to a layer" appears anywhere in those
statements, and the run page carries no cucumber-js-is-unsupported sentence.

## What changed

- `cucumber_js` — supported (`Ecosystem.supported=True`, no "not wired yet" reason). `bindings()`
  records and skips unreadable declarations (regex literal, concatenation, unterminated literal) —
  `unreadable(files)` returns `path:line`, kind and reason; `bindings(strict=True)` keeps the old
  loud refusal as an audit switch. `explain_unmatched()` returns the step and the two nearest
  distinct patterns. Bindings carry `layer_commands` (command name, path, line, its own via) so a
  reader can walk a claim to the command body.
- `level_fitness` — an `extractor`/`unmatched` seam. With it, a step with no binding of its own is
  unplaced for the ecosystem's reason (not rescued by a sibling's layer), the background joins the
  span, and each claim records `provenance` (extractor, binding path:line/layer/via/commands, and
  the scenario's bindings). The page renders a "What placed this claim" block. Supplying neither
  keeps the .NET path byte-for-byte identical.
- `duplication` — accepts the ecosystem's suite rule and extractor. On this corpus it runs and
  returns 0 claims (no two scenarios share a normalised signature); the JS suite rule keeps a
  feature paired with its own suite's JS steps, and a synthetic cross-suite pair shows each copy
  placed from its own declaration (api vs ui).
- `pipeline`/`rebuild` — pass the hooks; record `placement` and `unreadable_declarations` in the
  snapshot meta; run page gains "What this run placed".
- Tests: `tests/test_cucumber_js_placement.py` (7 tests) plus updates to the three cucumber test
  modules.

## ACs

| id | result |
|----|--------|
| AC1 | **17 of 43**, verified on a real levels run over the stored blobs |
| AC2 | 26 unplaced, each "no binding matches these words" + step text + the two near patterns |
| AC3 | unsupported sentence gone; page states 17 placed (17 ui), 26 unplaced, why, and 0 unreadable |
| AC4 | claim detail names `cucumber-js` and the binding; the scenario chain is walkable, e.g. background `background.stepdef.js:30` → `cy.createRoomViaApi()` at `custom-commands/room-management.js:99` → `cy.request` |
| AC5 | a `cy.request` command in a UI-named file is `api`; a mixed file yields both layers; static guard forbids the .NET per-file path |
| AC6 | duplication runs, 0 claims, extractor/suite recorded; cross-suite fixture pairs each copy with its own suite's steps |
| AC7 | Demo Product 94/90/1/1/2, DemoService 17 claims/17 cases/17 findings, case-page goldens byte-identical, **622 passed** |
| AC8 | 17/43 placed, 26/43 unplaced — corpus problem, stated above |
| AC9 | record-and-continue for regex/concat/unterminated; **0 unreadable declarations in this corpus**; synthetic run with 2 shows `2 declarations could not be read` with both `path:line`s and the readable step still claimed |
| AC10 | 11 `Step(this, …)` delegations remain `unknown`, all 11 When-steps, reason recorded; they do not touch 17/43 |

## Verification

From the project `.venv`, with `PYTHONPATH`, `PYTHONHOME`, `VIRTUAL_ENV`, `CONDA_PREFIX` stripped and
`PYTHONNOUSERSITE=1`: `622 passed in 121.96s`. Targeted .NET pins re-run and green:
`test_the_corpus_still_carries_the_verdicts_the_ticket_pins`,
`test_every_case_page_and_the_indexes_are_byte_identical_after_the_migration`,
`test_every_finding_is_its_own_case_with_one_finding_each`, `test_the_reqnroll_module_is_the_old_extractor`.

`docs/ecosystem-inventory-cucumber-js.md` gets a dated correction (TESTOPS-42C-3) superseding §8's
"nothing was built" status; no prior text is deleted.

The store copy in `data/` is the gitignored build artefact used by the corpus tests.
