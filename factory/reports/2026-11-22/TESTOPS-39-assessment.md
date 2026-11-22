# TESTOPS-39 assessment — a second specimen, and what it falsifies

2026-11-22, branch `factory/testops-39-second-specimen`. The specimen is a different ecosystem and two
separate repositories, chosen so the analyses either generalise or are shown not to:

- tests: `m-pujic-levi9-com/cypress-cucumber-e2e-tests` — JavaScript, Cypress + Cucumber, `.feature` files
  bound by `.stepdef.js` files.
- product: `mwinteringham/restful-booker-platform` — Java, multi-service platform.

Both were read through the existing GitHub collector at the commits below. Nothing in either upstream
repository was modified; nothing was cloned into a source tree. The only product change is a `Project`
literal in `testops/config.py` — no analyser, extractor or collector was touched, per the ticket.

| arm | repository | pinned commit |
|---|---|---|
| test | m-pujic-levi9-com/cypress-cucumber-e2e-tests | `262404a95784970315faeae6374ce8783ccbe598` |
| product | mwinteringham/restful-booker-platform | `efe2deb8ce02db541adbf9d3a6604caf5fbdaae6` |

Runs: `restfulbooker-levels-20261122T201853` (snapshot `restfulbooker-levels-20261122-262404a9`) and
`restfulbooker-dup-20261122T201909` (snapshot `restfulbooker-20261122-262404a9`). Both exited 0. Neither
crashed. The suite: 417 passed.

## Sample sizes, honestly

Six feature files is the whole suite, not a sample of it, but it is also six files: do not read a
percentage off it.

| quantity | count |
|---|---|
| feature files in the upstream test repo | 6 (all collected, all parsed) |
| scenarios parsed | 33 (0 raw/parsed discrepancy) |
| asserting steps (`Then`, plus following `And`/`But`) | 43 |
| level-fitness claims | 43 |
| — distinct / review / gap / unplaced | 0 / 0 / 0 / 43 |
| step-binding observations recorded | 0 |
| duplicate signatures shared by ≥2 scenarios | 0 of 33 |
| duplication claims | 0 |
| cases raised by either analyser | 0 |
| pages that serve a claim | 0 |

That last row is the one to sit with: 43 claims were stored and no page anywhere shows one, because a
claim only reaches a page through a case, and this corpus raised none.

## What generalised unchanged

- **The Gherkin parser.** 6/6 files, 33/33 scenarios, step counts and line numbers as the files hold them.
  No tabs, outlines, doc strings or BOM trouble in this corpus; it simply read.
- **The collector.** Recursive tree read, blob pinning at a commit, the 512 KB cap and the ignore list all
  behaved. The two-role path (`project.product != project.test`) fetched both repositories separately and
  recorded both commit ids in one snapshot.
- **The source registry.** No tracker is named for this project, so Jira was not declared at all, and the
  claim rows carry `sources_missing: []` with a real assessment record — absent, not zero, as intended.
- **Persistence and the claim schema.** 43 v2 claim rows with coordinates, commit, span, support and
  assessment all written; no constraint refused a row.
- **The renderer.** Every stored claim runs through the page's own functions without an exception (see
  "How many pages error" below).
- **Duplication's grouping rule.** 33 scenarios produced 33 distinct normalised signatures, so zero groups
  is the right answer on the rule's own terms: this suite does not assert the same thing twice.

## What needed a new extractor, and still does

The step-binding extractor read **nothing**. That is a refusal, not a crash: `parse_file` returns `[]`, the
run continues, and the pipeline stats report `bindings: 0`.

The corpus contains **44 cucumber-js bindings, of the form `Given|When|Then|And|But('…', () => { … })` — 13 of them `Then(` — in the five
`*.stepdef.js` files** of a 15-file JavaScript test tree (corrected after review). The extractor read 0 of them. `BINDING` is
`\[(Given|When|Then|And|But)\s*\(\s*"` (`testops/extract/stepbindings.py:24`) — a C#/Reqnroll attribute.
Zero attribute-style bindings exist anywhere in this corpus, so the two counts cannot meet.

What it can read, and what it cannot:

| binding style | present here | read |
|---|---|---|
| C#/Reqnroll `[Given("…")]` | 0 | yes (the only shape) |
| cucumber-js `Given('…')` (all five keywords; 13 `Then(`) | 44 | no |
| cucumber-js `Given("…")` / `` Given(`…`) `` | 0 | no (same regex, wrong brackets) |
| Python `@given("…")` | 0 | no |
| Cypress custom commands (`Cypress.Commands.add('…')`) | several | no — they define no Gherkin step and are not looked for |

Consequence, and it is total for this corpus: no bindings means no `layer`, no `span`, no `instrument`, so
`inspect` falls to `unknown` and every one of the 43 claims is `unplaced`. A 33-scenario UI suite scores
identically to a repository with no tests at all.

## What is CotW-specific and would mislead another team

1. **The layer vocabulary is .NET.** `SIGNALS` (`stepbindings.py:27-41`) names `IPage`, `IWebDriver`,
   `HttpClient`, `IMediator`, `DbContext`, `EngineClient`, `RunDriverAsync`, `continuity_driver`. There is
   no signal for `cy.`, a page object, or a custom command. A Cypress step whose body is
   `cy.xpath('//a[text()="Logout"]').should('be.visible')` matches none of them.
2. **Drivers are found by filename.** `build_driver_map` only reads files ending `Driver.cs`/`.py`/`.ts`
   (`stepbindings.py:71-84`). Cypress puts its drivers in `cypress/support/custom-commands/*.js`; under
   this rule they are not drivers and never will be.
3. **The collector's kinds are a fixed language list** (`collectors/github.py:19-27`). `.java` is absent, so
   the product's **142 Java files were never fetched**. The product contributed 27 `.js`/`.ts` assets, all
   recorded with kind `stepdef` — including `assets/next.config.js` and a Jest setup file. The product's
   actual code is invisible to every analyser, and nothing says so.
4. **Surface discovery parses Python only** (`surfaces/discover.py:45`: `if not path.endswith(".py")`). For a
   Java product it returns `[]`, and the run prints `"surfaces": 0` with no reason attached. A zero from a
   reader that cannot read the language is being reported like a zero from a reader that can.
5. **"The page the server sends" is a server-rendered concept.** `INTERACTION_LABEL["KP"]` and
   `_SETTLED_BY["KP"]` (`analysers/level_fitness.py:250-275`) assume the page arrives from the server. In a
   Cypress suite `cy.contains('Room #')` runs in the browser against a client-rendered SPA; the label is
   simply false about the instrument.
6. **`csproj.excluded_patterns`** is an MSBuild idea. It is harmless when absent, but it means "every
   feature is active" is the silent default for any team that does not build with a `.csproj` — the
   protection that stopped CotW reporting 141 scenarios instead of 43 does not exist off .NET.
7. **`duplication._suite`** takes the first path segment (`duplication.py:105`); every file here is in the
   suite `cypress`, so per-suite scoping degenerates to global. It did not bite only because nothing matched.

## Specific claims that are wrong, with `file:line`

All coordinates are `path:line` in the pinned test commit. Each is a stored claim, not a paraphrase.

| claim | what it says | why it is wrong |
|---|---|---|
| `cypress/e2e/features/admin-panel/login/login.feature:14` ("User is redirected to Rooms Management Page") | label *"settled by the page the server sends"*; statement ends *"None of its steps could be tied to a layer of the system"* | The step is bound at `login.stepdef.js:33-38` to `cy.contains('Room #')` … five `cy.contains` calls. It is tied to a layer — the browser — and the extractor could not see the binding. The label also claims a server-sent page for a client-side SPA. |
| `login.feature:13` ("User is Logged In") | *"Its words name no data, response, page or anything a person sees"* | The words name exactly what a person sees, and so does the implementation: `login.stepdef.js:29-30`, `cy.xpath('//a[text()="Logout"]').should('be.visible')`. |
| `login.feature:19` ("Username field will have red border") | *"Its words name no data, response, page or anything a person sees"* | A red border on a field is a visual property. `PRESENTATION` (`level_fitness.py:181-182`) has no `field`, `border` or `style`, so the vocabulary reports the absence of words that are present. This one is a vocabulary gap, not a parser gap — it would mislead on any corpus. |
| `login.feature:18`, `:23`, `:28` ("User is still on Booking Management login page") | *"settled by the page the server sends"* | Bound at `login.stepdef.js:41-42` to `cy.contains('Log into your account')` — a browser assertion, not a server-rendered page. |
| every claim's source record | GitHub `observed: 48`, capabilities `code` + `test_code`; a page would render *"Assessed: code and test code were consulted and returned 48 items."* | 48 is the total of collected artefacts — 6 features and 42 `.js`/`.ts` files, 27 of them from the product's front-end — counted once for a source serving both capabilities (`pipeline.py:298`). **No product code file was read**: 142 `.java` files were skipped by kind. The sentence about `code` is false. |

The generalisation of the first three faults is one fault: *"this repository is not C#"* is rendered as
*"nothing here can be tied to a layer"*, in the reader's own language, with a proposed action
("Bind the step … to a step definition whose driver can be identified") that the team cannot act on,
because the binding already exists.

## How many pages error

Zero. Detail, because "zero errors" is only meaningful with what was actually rendered:

| page | result |
|---|---|
| `/` (index) | 6,568 bytes, 200, no exception |
| `/runs` | 22,565 bytes, 200, no exception |
| `/run/restfulbooker-levels-…` | 200, 6,664 bytes |
| `/run/restfulbooker-dup-…` | 200, 6,649 bytes |
| `/case/…` | none exist — 0 cases |
| claim rendering | 43/43 stored claims passed through `queries.claim_read` → `web.claim_sections` with no exception |

The honest limitation: because no case exists, no URL serves a claim, so "every claim renders without a
page error" is satisfied at the renderer and vacuous at the page. A defect in claim rendering could sit
in this corpus unnoticed by clicking, which is why the renderer was exercised directly.

## The zero-claim analyser, and whether it says why

Duplication raised 0 claims. Its run page says the run examined 6 features / 33 scenarios at the pinned
commit, that no tracker was connected, and that it raised no finding. That part is honest. What the page
cannot say is the fact that matters here — **layering was unknown for all 33 scenarios** — because that
fact only existed inside claims the analyser never made. Zero claims is also zero places to carry a blind
spot. The same shape would hide a corpus the tool could not read at all.

## Evidence for TESTOPS-38

Adding this specimen required **editing Python**. The whole change is a `Project` literal in
`testops/config.py`; there is no configuration file, no row and no CLI argument that names a project. That
is a direct contradiction of ADR-1 consequence 2 ("Adding a *project* must require no code at all"), and
it is not a one-line convenience: the edit has to be typed, reviewed, tested and deployed before the corpus
can even be named, and it puts repository coordinates — data — inside a module the Lead may not edit
without a ticket. A second team cannot onboard themselves. This is the case TESTOPS-38 exists for.
