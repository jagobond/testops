# TESTOPS-42C-2 review — the per-command layer inference

Reviewer: independent re-derivation of the command table from the stored blobs with my own scanner
(own comment-stripper, own registration regex, own close reading of every command body); probes
against `cucumber_js` and `stepbindings` run fresh in this session; synthetic fixtures for the
refusals; full suite run from the project `.venv` with `PYTHONPATH`, `PYTHONHOME`, `VIRTUAL_ENV`,
`CONDA_PREFIX` stripped and `PYTHONNOUSERSITE=1`: **615 passed in 116.80s**.

## Verdict

**ACCEPTED.** The 11/4 command count reproduces from my own scan; every layer in the build's table
matches the layer I derive from the source I read myself; all 11 unknown bindings are genuinely
run-time-built `Step(this, …)` template literals (not one is a literal call, so nothing is being
left on the table); the alias qualification is not only sound but load-bearing — `ui` is the
*highest* layer in `LAYER_ORDER`, so without it `createRoomViaApi` would flip to ui; carried item A
refuses loudly with a pasteable message; carried item B is exactly as required; no placement and
.NET parity hold. One recommendation for T42C-3 below (record-and-continue), and two minor
observations.

## The command table, re-derived

My scan (raw regex over every `.js` in the arm, then over my own comment-stripped text):

- **15 raw `Cypress.Commands.(add|overwrite|addAll)` occurrences**, of which **4 commented**
  (`login`, `drag`, `dismiss`, `visit`, all `cypress/support/commands.js:13-25`) and **11 live** —
  `bookRoom`, `bookRoomWithNoDates` (booking.js), `loginViaUI`, `loginViaApi` (login.js),
  `sendMessage` (messages.js), `createRoom`, `createRoomViaApi`, `deleteBookingViaApi`,
  `deleteAllBookingsViaApi`, `deleteRoomViaApi`, `deleteAllRoomsViaApi` (room-management.js).
  Matches AC1 and the build exactly.
- My synthetic probe: a file holding a commented **and** a live registration yields only the live
  one (`drivers: ['real'] | ghost excluded: True`) — exclusion is by parsing, not by file.
- I then read each of the 11 bodies and gave it a layer myself, one helper hop, `cy.*` signals,
  command calls not followed from a command body:

| command | my layer | my justification line |
|---|---|---|
| bookRoom | ui | helpers `clickBookThisRoom` (`cy.xpath(...).last().click()`), `enterFirstName`.. (`cy.get('.selector').type`), `clickBook` (`cy.xpath('//button[text()="Book"]').click()`); `setBookingDates` also `cy.get('@start')` — alias, but real signals abound |
| bookRoomWithNoDates | ui | same helpers less `setBookingDates` |
| loginViaUI | ui | `enterUserName`/`enterPassword` (`cy.get('#username').type`), `clickLogin` (`cy.get('#doLogin').click()`) |
| loginViaApi | api | `cy.request({method: 'POST', url: `${apiUrl}/auth/login`...})` |
| sendMessage | ui | five `cy.get('[data-testid="Contact…"]').type` helpers + `clickMessageSubmit` |
| createRoom | ui | six `cy.get('#…').click/.type/.select` helpers; its `cy.get('@roomNames')` is alias access |
| createRoomViaApi | api | own `cy.request({method: 'POST', url: `${apiUrl}/room/`...})`; calls `cy.deleteAllRoomsViaApi` (not followed from a command body) and `cy.get('@roomIds')` (alias) |
| deleteBookingViaApi | api | `cy.request({method: 'DELETE', url: `${apiUrl}/booking/${bookingId}`...})` |
| deleteAllBookingsViaApi | api | `cy.request({method: 'GET'...})`; `cy.get(response.body.bookings)` is data access |
| deleteRoomViaApi | api | `cy.request({method: 'DELETE', url: `${apiUrl}/room/${roomId}`...})`; calls `cy.deleteAllBookingsViaApi` (not followed) |
| deleteAllRoomsViaApi | api | `cy.request({method: 'GET', url: `${apiUrl}/room/`...})` |

**6 api, 5 ui — the build's split and every per-command layer match mine. No command is layered
differently from my own reading.** I confirmed `drivers()` returns these layers on the real blobs
(`loginViaApi api via=('cy.request',)` etc.), and that the two AC4 pins hold: `loginViaUI` ui /
`loginViaApi` api in one file, `createRoom` ui / `createRoomViaApi` api in one file.

## The 11 unknown (Step delegation)

The single most consequential judgement, checked line by line. I located every `Step(this, …)` in
the corpus — 11, at `room-management.stepdef.js:28,35`, `booking.stepdef.js:15,23,30,38,45,52,60`,
`contact.stepdef.js:9,21`. **All 11 are template literals with interpolated variables** —
e.g. `` Step(this, `Visitor '${firstName}' '${lastName}' with an email '${email}' … tries to book
a room '${roomName}'`) ``. **None is a literal string.**

So the quantification is: **0 of the 11 could be resolved by following a literal
`Step(this, '...')`** — there are no literals to follow. The build's reason holds precisely: the
text is assembled at run time (two of them vary which fields are blanked by *which parameters are
empty*, and two booking rows are even textually identical delegations from different bindings —
the layer would have to come from the target step's parameters, not the call site). Following them
is genuinely a T42C-3+ question of matching the assembled text back against the corpus's patterns,
which is a matcher problem, not a parse problem. The recorded reason on every row names the
delegation, and `layer_reason` is present on all 11.

## Alias qualification

Probed each form through `infer_layer_from_body` (the qualification lives in the `cy.get` pattern
`(?!@)` after a quote character):

- `cy.get('.widget').click()` → **ui** ✓
- `cy.get("#username").type(...)` → **ui** ✓
- `cy.get('[data-testid="X"]').should(...)` → **ui** ✓
- `cy.get(someVariable)` → **unknown** — stated treatment: only a selector *literal* is a browser
  command; a bare expression is data access. Stated in the module docstring and comment.
- `cy.get('@roomIds')` → **unknown** — alias access ✓

Not over-suppressing: verified. Under-suppression edge: `cy.get(\`#id${x}\`)` — a dynamic template
selector — counts as ui because the quote is a backtick not starting with `@`. Defensible (it *is*
a selector), not in this corpus, not worth a ticket.

**The qualification is load-bearing, and the build's claim understates nothing:** `LAYER_ORDER` is
`['storage','engine','controller','api','ui']` and `highest()` picks the *last*, so `ui` outranks
`api`. Without the qualification, `createRoomViaApi`'s `cy.get('@roomIds')` alone would flip it to
ui. The build's docstring claim ("without this createRoomViaApi reads as ui") is correct, not
cosmetic.

## Carried A (and the raise-vs-continue recommendation)

Reproduced with a synthetic fixture (`When('Visitor will get validation/' + 'mandatory error
message: {string}', …)` in `cypress/e2e/x.stepdef.js`). The refusal, verbatim:

```
UnsupportedEcosystem: cucumber-js step patterns split across a string concatenation are not
supported by this build: cypress/e2e/x.stepdef.js:2 declares When('Visitor will get validation/'
+ ...). Only the first half is readable, which would be a pattern that matches nothing, so this
build refuses to return a partial binding list.
```

The declaration is recorded at parse time (`parse_declarations` returns `pattern='Visitor will get
validation/'`, `concatenated=True` — never silently truncated into the returned list), and
`detect()` evidence carries the count when one exists. The regex arm raises the same way
(`cypress/e2e/x.stepdef.js:2 … refuses to return a partial binding list`). Both pinned by tests
(`test_a_pattern_split_across_a_concatenation_is_refused_never_truncated`, and the T42C-1 regex
pins).

**Recommendation for T42C-3: record-and-continue for both arms.** Raising is right *now* (it is a
canary while nothing calls `bindings()` in anger) and wrong *wired*. The two forms fail
differently and the distinction matters:

- A **concatenation** returns a *wrong* pattern — a matcher that silently matches nothing, i.e. a
  false negative masquerading as coverage. That must never be placed; skip the declaration.
- A **regex literal** returns a *missing* row — an honest gap. Skip the declaration.
- In both cases the correct end state is: the declaration gets **no placement**, `detect()`
  evidence and the build report name it with `path:line` (already implemented — the evidence lines
  exist), and **the other 43 declarations still become claims**. Raising instead converts one
  unreadable declaration into zero claims for a whole suite — throwing away readable evidence to
  punish an unreadable corner, which is the trade the product exists to refuse.
- The raise should survive only as a switchable strictness flag (or as the default while `supported
  is False`), so a future corpus can be audited hard if wanted. T42C-3's ticket should say this
  explicitly rather than inherit the raise.

## Carried B

Verified in `docs/ecosystem-inventory-cucumber-js.md`:

- §7's Suite-scoping cell now reads "…the working rule is directory co-location, because the
  filename stem rule matches **0 of 5** files (see Corrections)" — the 0.25-day estimate is
  unchanged.
- The Corrections section (dated 23 November 2026, TESTOPS-42C-2) **preserves the old sentence
  verbatim** ("The §7 sentence \"today's stem rule already works on 5 of 5 files\" was false"),
  states the measurement (`bookingstepdef` etc., 0 of 5 via `_suite_of`), names the working rule
  (`suite_of_path`, all six features resolve), and states the estimate is unaffected because the
  directory rule is the cheaper of the two.
- Independently I had already verified the same 0-of-5 measurement in the T42C-1 review; the
  document now matches it. Not quietly changed to fit: the old text is quoted, dated, and the
  correction is attributed to the measurement, not to preference.

## No placement

- `git diff 9d1dba0..HEAD` touches `cucumber_js.py`, `stepbindings.py` (+7 lines: the two new
  `Binding` fields with empty defaults and their comments), the `EcosystemModule` protocol's
  `drivers` return-type annotation, docs, factory files, and three test files. **No analyser, no
  pipeline file, no reader changed.**
- `detect()` on the corpus returns `supported=False` with evidence now including the command split
  (`11 Cypress custom commands (6 api, 5 ui)`); `REASON` no longer claims it cannot read the
  files — it names what is absent: placement.
- `bindings()` returns bindings + layers with zero claims; `supported is False` keeps the corpus
  `not_assessable`. Pinned by `test_ac6_the_ecosystem_is_still_unsupported_so_the_layers_claim_nothing`
  and the part-1 gate tests, all green in the 615.

## .NET parity

- The only shared-code change is the two `Binding` fields (`layer_via: tuple[str, ...] = ()`,
  `layer_reason: str = ""`), additive with empty defaults. The .NET reader sets neither; the
  protocol change to `drivers()` is a widening annotation, not a behaviour change.
- `test_the_reqnroll_module_is_the_old_extractor` (row-for-row equality against the old extractor)
  passes in the green suite.
- Demo Product **94/90/1/1/2**, DemoService **17/17**, and the case-page goldens byte-identical are all
  pinned proofs inside the 615 — green. No .NET pattern regressed.
- AC5 verified by my own probes: a JS `Repository` is `unknown` in the JS table (the .NET table
  still says `storage` when the word genuinely stands alone — `\bRepository\b` is unchanged); JS
  `page.GetByRole('button').ClickAsync()` is `unknown` while the .NET table says `ui`. The tables
  are disjoint with a module-level import guard. `DOTNET_ONLY_SIGNALS` states every .NET-only
  signal, layer by layer, with the reason (`Playwright` matches `GetByRole`/`ClickAsync`, which
  are the .NET spellings — so it was never JS Playwright evidence).

## Three sharpest concerns

1. **The T42C-3 decision is still open in the code, not just in the ticket.** Both refusal arms
   raise today; that is correct for this part, but the raise is a loaded spring. If T42C-3 wires
   placement without revisiting it, the first real suite with one regex literal or one
   concatenation drops to zero claims. My recommendation above is record-and-continue for both;
   the ticket should decide it in writing before wiring.
2. **The `Step(this, …)` unknowns are a residual 25% of the corpus with no resolution path.** All
   11 are template literals, so the reason recorded is exactly true — but note two of the booking
   rows are *textually identical* delegations (`booking.stepdef.js:23/38` and `:52/60` pairs),
   and the assembled text of a delegation maps back to a *pattern in the same file*. T42C-3 could
   resolve all 11 by re-invoking `match_step` on the assembled-text-with-{string} substitution —
   a matcher exercise, worth naming in the T42C-3 ticket, since it converts 11 unknowns to
   real layers for one small change.
3. **Dynamic selector literals (`cy.get(\`#id${x}\`)`) count as ui.** Defensible, rare, and absent
   from this corpus — but it is the same shape of judgement as the alias rule and is currently
   implicit in the `(?!@)` guard rather than stated as a documented rule next to the alias/data
   statement. One sentence in the docstring would close it.
