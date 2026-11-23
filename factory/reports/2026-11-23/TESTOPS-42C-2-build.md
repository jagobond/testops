# TESTOPS-42C-2 build — the inference

Branch `factory/testops-42c2-inference`. Part 2 of 3: the layer where it happens — commands,
one level of module-local helper, and `cy.*`, resolved **per command**. Still no placement: the
ecosystem stays `supported = False`, so the pipeline keeps the restfulbooker run `not_assessable`
with zero claims. Analysers, pipeline and `.NET`/Python readers are untouched.

## Changes

- `testops/extract/ecosystems/cucumber_js.py`
  - `JS_SIGNALS` — a JS/TS signal table of its own (`ui`: `cy.get`, `cy.contains`, `cy.xpath`,
    `cy.visit`, `.click`, `.type`, `.select`, `.should`; `api`: `cy.request`, `supertest`, `axios`,
    `fetch(`; `storage`: `prisma`, `knex`, `mongoose`). `LAYER_ORDER` is imported from
    `stepbindings`, not copied.
  - `DOTNET_ONLY_SIGNALS` — states, layer by layer, which signals in `stepbindings.SIGNALS` are
    `.NET`-only and why each is absent from the JS table (`\bRepository\b` is a common JS class
    name; `\bPlaywright\b`/`\bGetByRole\b`/`\bClickAsync\b` are the .NET Playwright spellings, so
    the "Playwright" signal was never evidence of JS Playwright). A module-level guard fails the
    import if the two tables ever share a pattern.
  - `CustomCommand` + `drivers()` — the 11 real `Cypress.Commands.add` registrations (15 raw less
    4 inside comments), each with file, 1-based line, body, and the layer its own body resolves to.
    Comments are stripped by a quote-aware scanner, so the four are excluded **because they are
    comments**: a commented and a live registration in the same file behave correctly in the tests.
  - `_reason_and_layer()` — the chain `step body → cy.<command>() → one level of module-local
    helper → JS signal`. Command bodies are the unit: a command is resolved on its own, helpers one
    hop only. Where nothing resolves the row is `unknown` and `layer_reason` says which of six
    distinct facts applies (no readable body / `Step(this, …)` delegation / a command that itself
    resolved to nothing / a command's own body (not followed) / helpers that reach no signal / a
    `cy.*` that is neither a signal nor a registered command).
  - `Binding` gains `layer_via` (the chain taken) and `layer_reason` (why not, when unknown).
    Additive with empty defaults; the .NET and Python readers never set them, and
    `test_the_reqnroll_module_is_the_old_extractor` still holds row-for-row equality.
  - Two qualifications the corpus forced, both documented in the module: `cy.get('@alias')` and
    `cy.get(<expr>)` are alias/data access, not browser commands (without this `createRoomViaApi`
    reads as `ui` through its `cy.get('@roomIds')` plumbing), and `Step(this, '…')` re-invokes a
    step by run-time-built text, so it is not followed.
  - `detect()` evidence gains the command split (`11 Cypress custom commands (6 api, 5 ui)`); the
    44-in-5-files line is unchanged. `REASON` no longer says "cannot read them" — it can read them
    now, and what is absent is placement.
- Carried item (A) from the T42C-1 review: a pattern split across a string concatenation is
  recorded at parse time (`Declaration.concatenated`) and **refused** in `bindings()` with
  `path:line` and the readable half named, and flagged in the detection evidence. It is never
  returned truncated. This corpus concatenates nothing, so nothing regressed.
- Carried item (B): `docs/ecosystem-inventory-cucumber-js.md` §7 corrected — the stem rule matches
  **0 of 5** files, not 5 of 5; directory co-location is the rule that works — and a dated
  Corrections entry preserves the old sentence and states the measurement. Details below.
- `tests/test_cucumber_js_inference.py` — new, 19 tests. `tests/test_cucumber_js_bindings.py` and
  `tests/test_ecosystems.py` — the two part-1 assertions that pinned "every layer is unknown" and
  "`drivers()` refuses" are updated: part 2 supersedes them, and the gate that still stops a claim
  is `supported is False`, which both files keep asserting.

## AC1 — the 11 real commands

`drivers()` returns exactly `loginViaApi, loginViaUI, createRoom, createRoomViaApi,
deleteBookingViaApi, deleteAllBookingsViaApi, deleteRoomViaApi, deleteAllRoomsViaApi, bookRoom,
`bookRoomWithNoDates, sendMessage`, each with a non-empty body of at most 21 lines from
`cypress/support/custom-commands/`. 15 raw `Cypress.Commands.add|overwrite` occurrences, 4 inside
comments in `cypress/support/commands.js` (`login`, `drag`, `dismiss`, `visit`), 11 real. The
exclusion is proven on a synthetic file that holds both a commented and a live registration.

## AC2 — the vocabulary

`JS_SIGNALS` is a separate object from `SIGNALS` (`is not`), holds exactly the tokens the ticket
lists, and `LAYER_ORDER is stepbindings.LAYER_ORDER`. Each token is exercised on its real call
form, not just by membership.

## AC3/AC4 — measured on the corpus

| layer | declarations | how |
|---|---|---|
| `ui` | 31 | 16 resolve inside the step body, 15 one level down through `cy.<command>()` |
| `api` | 2 | `cy.loginViaApi()` and `cy.createRoomViaApi()` from `background.stepdef.js` |
| `unknown` | 11 | all `Step(this, …)` delegation — reason recorded on every row |

The point of the part, per-command and not per-file:

| file | command | layer |
|---|---|---|
| `custom-commands/login.js` | `loginViaUI` | ui (helpers `enterUserName`, `enterPassword`, `clickLogin`) |
| `custom-commands/login.js` | `loginViaApi` | api (`cy.request`) |
| `custom-commands/room-management.js` | `createRoom` | ui (`cy.get`/`.type`/`.select`/`.click`) |
| `custom-commands/room-management.js` | `createRoomViaApi` | api (`cy.request`; its `cy.get('@roomIds')` is alias access) |

A file-level answer would be wrong for one of each pair whichever way it fell.

## AC5 — the .NET signals that fire on JS

`\bRepository\b` on a JS class definition: `stepbindings.infer_layer_from_body` → `storage`,
`cucumber_js.infer_layer_from_body` → `unknown`. `page.GetByRole('button').ClickAsync()`: .NET
table → `ui`, JS table → `unknown`. Both facts are pinned by tests, and the tables are asserted
disjoint.

## Carried item (B) — the stem-rule correction, measured

`stepbindings._suite_of` strips `js` and stops, so `booking.stepdef.js` → `bookingstepdef`:
`loginstepdef`, `roommanagementstepdef`, `bookingstepdef`, `contactstepdef`, `backgroundstepdef`
against feature stems `login`, `roommanagement`, `bookaroom`, `bookaroominvalidvalidation`,
`contacthotel`, `contacthotelinvalidvalidation` — **0 of 5** files match. Directory co-location
(`cucumber_js.suite_of_path`) gives `login`, `management`, `booking`, `contact`, `support` and all
six features resolve; 4 of 5 files share a directory with a feature, the shared
`background.stepdef.js` living in `cypress/support/` and reached by the any-suite fallback. The
0.25-day estimate is unaffected (the directory rule is the cheaper of the two). The document's §7
cell is corrected and the old sentence is preserved in the Corrections section, dated.

## Verification

```
env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
  C:/Users/Chester/Projects/testops/.venv/Scripts/python.exe -m pytest -q
615 passed in 123.29s
```

596 before, 19 new. .NET pinned proofs (CotW, ReqOverflow, case-page goldens) are in that run and
unchanged; `test_the_reqnroll_module_is_the_old_extractor` compares module rows to the old
extractor row-for-row.

## What is left for T42C-3

- Decide record-and-continue for the regex-literal arm (the T42C-1 review argued for it: raising
  converts one unreadable declaration into zero claims for the suite). The concatenation arm added
  here raises for the same reason and carries the same decision.
- Wire placement: `supported = True`, `bindings()` handed to the analysers, and the 11 `unknown`
  rows rendered with their `layer_reason` rather than as a layer.
- Not in this part, and not changed: `expect(` as an assertion signal (the ticket's table stops at
  `.should`), and Playwright JS spellings (`getByRole(`, `click(`) — a vocabulary decision, not a
  side effect of removing the .NET signal.
