---
id: TESTOPS-42
title: The tool reads one ecosystem, and says nothing when it does not
feature: F2
status: done
autonomy: build
depends_on: TESTOPS-41
---

# TESTOPS-42 — Ecosystem support, and the honesty of not having it

## Finding (TESTOPS-39)

On a JavaScript/Cypress suite against a Java product:

- **0 of 44** cucumber-js bindings (`Then('…', () => {})`) were read. `BINDING` is a C# attribute regex.
- With no bindings there is no layer, so **43 of 43** claims are `unplaced`.
- The layer vocabulary names .NET types only (`IPage`, `IWebDriver`, `HttpClient`, `IMediator`, `DbContext`).
- Drivers are found by filename (`*Driver.cs/.py/.ts`), so Cypress custom commands are never drivers.
- The label "settled by the page the server sends" is applied to a client-rendered SPA.

The result is a page telling a team *"none of its steps could be tied to a layer"* about a suite whose steps are
all bound, with an action the team cannot perform because the binding already exists. That is worse than refusing
to analyse the corpus.

## Decision needed (Product Owner)

Two honest options, and they are not the same product:

**A. Supported ecosystems, declared.** Reqnroll/.NET and Python are supported; anything else is `not_assessable` at
the project level, saying which ecosystem was detected and that support does not exist. Cheap, truthful, and useless
to a team outside those two ecosystems.

**B. A pluggable binding layer.** Step-binding extractors and layer vocabularies become per-ecosystem modules
(cucumber-js, pytest-bdd, Java/Cucumber-JVM, Reqnroll), selected from what the repository contains and recorded per
run. Weeks of work, and it is the difference between a tool for Demo Product and a tool a Quilter team can adopt.

**C. B, but only cucumber-js first**, to prove the seam with the corpus already in hand.

## Acceptance criteria (shape only — do not start until the decision lands)

| id | criterion |
|----|-----------|
| AC1 | Whatever the answer, a corpus in an unsupported ecosystem never renders "none of its steps could be tied to a layer" as though the tool had looked. |
| AC2 | The detected ecosystem is recorded per run and shown on the run page. |
| AC3 | If B/C: each extractor declares the ecosystems it handles, is selected automatically, and reports its own refusals with reasons. |
| AC4 | If B/C: the TESTOPS-39 corpus must produce a real verdict distribution, not 43 unplaced — and the assessment's seven Demo Product-specific faults become the acceptance checklist. |

## Notes

- Recommend **A now, then C**: stop the false claims cheaply, then prove the seam with a corpus that already exists
  rather than building four extractors on faith.
