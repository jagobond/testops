---
id: TESTOPS-42C
title: cucumber-js, built as a module with its own vocabulary and command model
feature: F2
status: done-progress
autonomy: build
depends_on: TESTOPS-42A, TESTOPS-50
---

# TESTOPS-42C — The first real ecosystem, costed from counts

## Decision

Harry chose **C** (pluggable layer, cucumber-js first). T42A built the seam and produced
`docs/ecosystem-inventory-cucumber-js.md`; the reviewer independently confirmed its five headline counts and found three
that did not reproduce (T50 corrects those). **Quote this ticket at 7.5–8 engineering days, not 6.25** — the review
judged the call-graph line (1.5d) to be priced off the friendliest possible corpus.

## Scope

Seven pieces, itemised in the inventory: binding scanner 0.5d, pattern matcher 0.5d, suite scoping 0.25d, custom-command
model 1.5d, JS/TS layer vocabulary 1d, call-graph layer inference 1.5d, tests 1d. Pipeline wiring is already paid.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | `cucumber_js.bindings()` returns real bindings: 44 found on the corpus, in 5 files, with line numbers, across one-line and multi-line layouts and both quoting styles. `drivers()` returns the 11 real custom commands (15 raw less the 4 inside a comment), each with its body. |
| AC2 | Pattern matching handles `{string}`, `{int}` and literal text; the duplicate pattern resolves per-suite rather than per-first-match. |
| AC3 | Layer inference follows a step's body into its custom command and one level of local helper — because 28 of 44 bodies resolve only that way — and returns `unknown` where nothing matches, never a guess. `cy.get`/`contains`/`xpath`/`visit`/`click`/`type`/`select`/`should` are ui; `cy.request`/`supertest`/`axios`/`fetch` are api; `prisma`/`knex`/`mongoose` storage. Per-file layer is NOT used; layer is per-command. |
| AC4 | On the restfulbooker corpus: **17 of 43 asserting steps place a layer; 26 stay unplaced, each with the reason "no binding matches these words"** — not "unsupported ecosystem". Any other number is a finding to report, not a target to hit. |
| AC5 | The 26 unplaced claims name the step text and the two patterns that nearly matched, so a reader can see the suite drifted. |
| AC6 | A "wrong layer" guard: a test that would fail if a `cy.request` command inside a UI-named file were classified ui. |
| AC7 | .NET and Python behaviour unchanged: CotW 94/90/1/1/2, ReqOverflow 17/17, goldens byte-identical. |
| AC8 | The run page stops saying cucumber-js is unsupported for this corpus and instead reports what it placed and what it could not, in the same voice as the other analysers. |

## Notes

- AC4 is deliberately not "43 of 43". A ticket promising that would be lying about the corpus.
- The Java product side of this corpus remains unreadable (collector kinds); do not try to fix that here.
- The 26 drifted assertions are a test-writing problem in the corpus, not in this product.
