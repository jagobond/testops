---
id: TESTOPS-42C-2
title: cucumber-js finds the layer where it happens - commands, helpers, and a call graph
feature: F2
status: blocked
autonomy: build
depends_on: TESTOPS-42C-1
---

# TESTOPS-42C-2 — The inference

Part 2 of 3. The corpus's layer is **per command, not per file** (inventory §3): `room-management.js` holds UI and API
commands side by side, and 28 of 44 step bodies reach `cy.*` only through a custom command or a local helper.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | `cucumber_js.drivers()` returns the 11 real `Cypress.Commands.add` commands (15 raw less 4 inside comments) with file, name and body. Commented-out registrations are excluded by parsing, not by assuming the 4 are in one file. |
| AC2 | A JS/TS signal table exists **separate from** `SIGNALS`: ui = `cy.get`, `cy.contains`, `cy.xpath`, `cy.visit`, `.click`, `.type`, `.select`, `.should`; api = `cy.request`, `supertest`, `axios`, `fetch(`; storage = `prisma`, `knex`, `mongoose`. `LAYER_ORDER` stays shared. |
| AC3 | Layer inference follows: step body → custom command → one level of module-local helper → `cy.*`. Where nothing resolves, the answer is `unknown` with the reason recorded, never a guess. |
| AC4 | Per-command layer is the unit. A test proves the two mixed files are not given one layer: `loginViaApi` and `loginViaUI` in the same file must resolve to different layers, and `createRoom` vs `createRoomViaApi` likewise. |
| AC5 | The `.NET` signal that fires on JS by accident is closed: `\bRepository\b` must not classify JS as storage, and the "Playwright" signal must not be counted as JS Playwright support - it matches `GetByRole`/`ClickAsync`, which are .NET spellings. State in the module which signals are .NET-only. |
| AC6 | Still no placement: analysers unchanged, this part produces bindings + layers only. |
| AC7 | .NET and Python unchanged; suite green. |
