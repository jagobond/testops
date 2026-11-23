---
id: TESTOPS-42C-3
title: cucumber-js places 17 of 43 assertions, and says why the other 26 are not placed
feature: F2
status: blocked
autonomy: build
depends_on: TESTOPS-42C-2
---

# TESTOPS-42C-3 — The honest result

Part 3 of 3, and the part where the number Harry will judge us by appears. **17 of 43 placed, 26 unplaced for a true
reason.** A run that claims 43 is wrong about the corpus.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | On the restfulbooker corpus the level-fitness run places a layer on **17 of 43** asserting steps. Any other number is a finding to report, not a target to hit. |
| AC2 | The **26 unplaced** each say "no binding matches these words" and name the step text plus the two patterns that nearly matched (`Visitor will get…`, `User will get…`), so a reader sees that the suite drifted from its own bindings. Not "unsupported ecosystem", not "could not be tied to a layer". |
| AC3 | The run page drops the cucumber-js-is-unsupported sentence for this corpus and speaks in the same voice as the other analysers: what was placed, what was not, and why. |
| AC4 | The claim provenance names the extractor (`cucumber-js`) and the command or helper the layer came from, so a reader can walk from claim to `cy.request` in `custom-commands/room-management.js`. |
| AC5 | "Wrong layer" guard: a test fails if a `cy.request` command inside a UI-named file is classified ui, or if per-file layer inference is reintroduced. |
| AC6 | Duplication analyser runs on the corpus without crashing and its output is honest about what it could and could not see (pairing JS features with JS steps only). |
| AC7 | .NET and Python unchanged: CotW 94/90/1/1/2, ReqOverflow 17/17, goldens byte-identical, suite green. |
| AC8 | Report the placed/unplaced split with counts in the build report, and state plainly that 26 of 43 is a corpus problem, not a tool problem. |
