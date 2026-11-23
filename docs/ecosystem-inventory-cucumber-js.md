# What cucumber-js actually needs — counted, not estimated

TESTOPS-42A, 23 November 2026. Every number below is a count over the corpus that is already in the
store; none of it is an adjective or an extrapolation.

**Provenance.** Snapshot `restfulbooker-20261122-262404a9` in `data/testops.db`, from the TESTOPS-39
run. Test arm `m-pujic-levi9-com/cypress-cucumber-e2e-tests@262404a95784970315faeae6374ce8783ccbe598`
(6 `.feature` files, 15 JavaScript/TypeScript files). Product arm
`mwinteringham/restful-booker-platform@efe2deb8ce02db541adbf9d3a6604caf5fbdaae6` (27 `.js`/`.ts`
files collected; the Java product code was never fetched — that is TESTOPS-39's collector gap, not
this ticket's). Counts were produced by reading the stored blobs, not by reading GitHub again.

## 1. The suite, in numbers

| quantity | count |
|---|---|
| feature files | 6 |
| scenarios | 33 |
| steps | 76 (33 When, 33 Then, 10 And) |
| asserting steps (Then, plus the And/But that follow) | 43 |
| `.js` / `.ts` files in the test arm | 15 |
| — of those, step-definition files (`*.stepdef.js`) | 5 |
| — Cypress support/config files (of which 1 is `index.d.ts`) | 10 |
| scenario tags | 6 (`@sanity` 4, `@bug` 2) |

## 2. Binding declarations: how many, in which syntaxes

**44 declarations in 5 files.** Keyword split: When 26, Then 13, Given 5, And 0, But 0.

| syntax | count |
|---|---|
| `Given('…')` / `When('…')` / `Then('…')` — single-quoted string | 44 |
| double-quoted string `Given("…")` | 0 |
| template literal `` Given(`…`) `` | 0 |
| regular expression `Given(/^…$/)` | 0 |
| `this.Given(…)` (World style) | 0 |
| hybrid (two forms in one repository) | n/a — one form only |

Two shapes of *layout* matter as much as the quoting:

| layout | count |
|---|---|
| declaration closed on one line (`Then('…', () => {` ) | 28 |
| pattern on its own line after the parenthesis (`When(\n  '…',` ) | 16 |

The second shape is 36% of the corpus and breaks any line-oriented scan. The first version of this
ticket's own detector missed exactly those 16 and reported 28 declarations — the count is now 44
because the scan is allowed to cross a newline. That is the whole argument for counting before
costing.

**Pattern bodies:** 43 distinct patterns for 44 declarations (one duplicate:
`Visitor will get validation/mandatory error message: {string}` is declared in both
`booking.stepdef.js` and `contact.stepdef.js`).

| pattern content | count |
|---|---|
| patterns mentioning `{string}` (86 occurrences in total) | 29 |
| patterns mentioning `{int}` (5 occurrences in total) | 5 |
| patterns with no placeholder at all (a literal sentence) | 15 |
| regular-expression pattern | 0 |
| expression interpolation (`${…}`) inside a pattern | 0 |

The rows overlap — a pattern can mention `{string}` and `{int}` — and they cover all 43 distinct
patterns between them. So the extractor's matching rules are: string literals, `{string}`, `{int}`,
and nothing else. The existing `stepbindings.pattern_to_regex` already turns `{string}` into a
permissive group; it would need `{int}` (\d+) and a regex-literal arm only if another corpus has
them.

## 3. How drivers and custom commands are expressed

There are no driver classes. Cypress puts its "drivers" in `Cypress.Commands.add(...)` and in
module-local helper functions.

| quantity | count |
|---|---|
| `Cypress.Commands.add|overwrite` occurrences, raw regex | 15 |
| — of those, inside comments (the sample `commands.js` header) | 4 |
| real custom commands | 11 |
| commands that contain `cy.request` in their own body | 6 |
| commands that contain only browser commands (`cy.get`/`click`/`type`/`select`) | 1 |
| commands whose body calls module-local helpers that then call `cy.*` | 4 |
| files ending `Driver.cs` / `Driver.py` / `Driver.ts` (what the current driver map looks for) | 0 |

The 11 commands, by the signal in their own body:

| command | file | `cy.request` | browser calls |
|---|---|---|---|
| `loginViaApi` | `custom-commands/login.js` | 1 | 0 |
| `createRoomViaApi` | `custom-commands/room-management.js` | 1 | 1 |
| `deleteBookingViaApi` | `custom-commands/room-management.js` | 1 | 0 |
| `deleteAllBookingsViaApi` | `custom-commands/room-management.js` | 1 | 1 |
| `deleteRoomViaApi` | `custom-commands/room-management.js` | 1 | 2 |
| `deleteAllRoomsViaApi` | `custom-commands/room-management.js` | 1 | 2 |
| `createRoom` | `custom-commands/room-management.js` | 0 | 1 |
| `loginViaUI` | `custom-commands/login.js` | 0 | 0 (helpers do) |
| `bookRoom`, `bookRoomWithNoDates` | `custom-commands/booking.js` | 0 | 0 (helpers do) |
| `sendMessage` | `custom-commands/messages.js` | 0 | 0 (helpers do) |

The layer is therefore **not a property of the file**. `room-management.js` holds UI commands and API
commands side by side; `login.js` holds one of each. A per-file layer — which is what
`build_driver_map` computes today — would be wrong for roughly half of them whichever way it fell.

How the 44 declarations reach their work:

| what the declaration body contains | count |
|---|---|
| a browser command directly (`cy.get`/`cy.contains`/`cy.xpath`/`cy.visit`/`.click`/`.type`/`.select`) | 16 |
| no browser command and no `cy.request`; it calls a custom command or helper | 28 |
| `cy.request` directly in the step body | 0 |

So the instrument of a step can only be inferred by following the call graph two levels: declaration →
command/helper → `cy.*`. A regex over the declaration body alone resolves 16 of 44.

## 4. Layer signals a JS/TS vocabulary needs — and what today's .NET vocabulary concludes

Measured across the 15 test-arm `.js`/`.ts` files:

| signal | count | layer it should mean | what the current .NET vocabulary concludes |
|---|---|---|---|
| `cy.get(` | 64 | ui (browser) | nothing — no signal matches; file layer `unknown` |
| `cy.contains(` | 12 | ui | nothing |
| `cy.xpath(` | 4 | ui | nothing |
| `cy.visit(` | 3 | ui | nothing |
| `.click(` / `.type(` / `.select(` | 12 / 13 / 2 | ui | nothing |
| `.should(` | 17 | ui (an assertion on the browser) | nothing |
| `cy.request(` | 6 | api (HTTP from the test process) | nothing — `SIGNALS["api"]` has `\brequests\b` (plural, Python) and `\bHttpClient\b`, neither matches |
| `cy.fixture(` | 5 | data, not a layer | nothing |
| `cy.wrap(` / `.as(` | 11 / — | state, not a layer | nothing |
| `expect(` | 6 | assertion, not a layer | nothing |
| `Cypress.Commands` | 15 (11 real) | the driver-definition mechanism | nothing — and not a `*Driver.*` filename, so 0 drivers are found |
| `playwright` | 0 | — | not present in this corpus |
| `supertest` | 0 | — | not present |
| `axios` | 0 | — | not present |
| `fetch(` | 0 | — | not present |
| `prisma` / `knex` / `mongoose` | 0 | — | not present |
| `localStorage` | 0 | — | not present |

**Measured consequence, not inference:** running the current extractor over all 15 files gives
`layer = unknown` for every one of them, 0 bindings, and 0 drivers. That is how 43 claims became
43 unplaced.

Two corrections to the vocabulary beyond "add `cy.`":

* **Playwright's JS API is not the .NET Playwright API.** `SIGNALS["ui"]` matches `\bPlaywright\b`,
  `\bGetByRole\b` and `\bClickAsync\b`. In JavaScript Playwright these are `getByRole(` (lower-case
  g) and `click(` — so the existing "Playwright" signal does not fire on Playwright JavaScript
  either. It is a .NET signal wearing a framework's name.
* **`\bRepository\b` is a storage signal in C# and a common class name in JavaScript.** It fires on
  this corpus 0 times, but it is the kind of shared-vocabulary signal that produces a confidently
  wrong layer rather than an honest unknown.

## 5. What a cucumber-js extractor would actually achieve here

Applying the 44 patterns to the 76 steps, with `{string}`/`{int}` as permissive groups:

| quantity | count |
|---|---|
| steps that match a declared pattern | 46 of 76 |
| Given/When steps that match | 29 of 33 |
| **asserting steps that match** | **17 of 43** |
| asserting steps that match nothing | 26 of 43 |

The 26 are not a parser failure; they are the suite's own drift. Every one of them names a
`validation error message` or a `mandatory error message`, while the only bindings that exist are
`Visitor will get validation/mandatory error message: {string}` and
`User will get validation/mandatory error message: {string}`. Counted: 26 asserting steps, 2 patterns
they were meant to hit.

This matters for expectations. A complete cucumber-js extractor would turn this corpus from
0 of 43 assertions placed into 17 of 43 placed, with 26 remaining unplaced **for a true reason that a
reader can act on** ("no binding matches these words"). It would not produce 43 clean claims, and a
ticket that promised it would would be lying about the corpus.

## 6. Finding: the layer vocabulary must be per-ecosystem

The case for sharing it was that a layer is a property of the system, not of the language. The
corpus falsifies the implementation of that idea, not the idea:

* the .NET vocabulary recognises **type names** (`IPage`, `IWebDriver`, `HttpClient`, `IMediator`,
  `DbContext`); the JS vocabulary must recognise **call names** (`cy.get`, `cy.request`, `fetch(`,
  `axios.`);
* the .NET driver model is **a class in a `*Driver.cs` file**; the JS model is **a command registered
  at runtime in a support file**, whose name never appears in a filename;
* the .NET per-file layer is correct because a step file names its driver class; the JS per-file
  layer is wrong because one support file holds UI and API commands (measured above: 2 files, 11
  commands, both layers in both files).

So `SIGNALS` and the driver map cannot be shared; the **layer names and their order**
(`storage < engine < controller < api < ui`) can and should stay shared, because they are the
vocabulary the verdicts and the prose are written in. T42-C's shape changes accordingly: a module
must supply its own signal table and its own driver model, while `LAYER_ORDER` and the analysers stay
common. Building it the other way round would mean teaching the JS vocabulary to emit .NET types, or
teaching the analysers two languages.

## 7. Costed estimate, per piece

Estimates are engineering days for one person who has read this document, including tests. The
`counted` column is the corpus fact that the estimate is anchored to.

| piece | what it involves | counted | estimate |
|---|---|---|---|
| Binding declaration scanner | tolerate 36% multi-line layouts, both quoting styles, `this.` form, regex literals; report line numbers | 44 declarations, 16 multi-line, 1 quote style | 0.5 day |
| Pattern → matcher | `{string}`, `{int}`, optional regex literal; 1 duplicate pattern | 43 distinct patterns, 2 placeholder kinds | 0.5 day |
| Suite scoping | a `.feature` beside a `.stepdef.js` is the same suite; today's stem rule already works on 5 of 5 files | 5 stepdef files, 6 feature files | 0.25 day |
| Custom-command model | parse `Cypress.Commands.add`, extract the body, build command-name → body, follow one level of local helpers | 11 commands; 28 of 44 step bodies depend on them | 1.5 days |
| JS/TS layer vocabulary | `cy.*` UI families, `cy.request`/`supertest`/`axios`/`fetch` API, `prisma`/`knex` storage, `should`/`expect` assertion; separate from `SIGNALS` | 9 distinct signals needed for this corpus; 6 present at 0 count and only specified | 1 day |
| Call-graph layer inference | declaration → command/helpers → `cy.*`, so a step's instrument is found where it happens | 16 of 44 resolvable in the body; 28 only one level down | 1.5 days |
| Pipeline + rebuild wiring | already done by this ticket: detection, per-repository record, not_assessable gate, rebuild parity | 2 call sites + 1 rebuild path | 0 (paid) |
| Tests | fixtures from this corpus (44 declarations, 5 files), a step-binding table, a "wrong layer" guard | 6 features, 33 scenarios, 43 assertions | 1 day |
| **total** | | | **6.25 days** |

Two things that are *not* in this estimate and should be quoted separately if they are wanted:

* **The 26 drifted assertions are a test-writing problem, not a tool problem.** Fixing the feature
  text to match the bindings is work in the corpus, not in this product; without it, one third of
  this suite will stay honestly unplaced after the extractor ships.
* **The Java product was never fetched** (142 `.java` files skipped by kind). The product side of
  this corpus remains unreadable until the collector's kind list grows, and the run page now says so
  rather than reporting code as consulted.

## 8. What this ticket did with the finding

Nothing of the above was built. `testops/extract/ecosystems/cucumber_js.py` detects the vocabulary,
counts it (44 declarations, 5 files, 11 custom commands), and refuses to extract, because a half
extractor that placed 16 of 44 steps and left 28 unplaced for the *wrong* reason — "we cannot read
JS" — is the lie TESTOPS-39 caught in the first place. The run for this corpus now says:

> cucumber-js is unsupported: this build can recognise JavaScript step definitions and cannot read
> them, so it will not guess what they do.

and makes no claim about the steps. T42-C can be estimated from this document instead of from
optimism.
