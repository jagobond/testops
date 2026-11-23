---
id: TESTOPS-42A
title: The extractor seam, ecosystem detection, and an inventory of what cucumber-js actually needs
feature: F2
status: done
autonomy: build
depends_on: TESTOPS-42
---

# TESTOPS-42A — Prove the seam before paying for the ecosystem

## Decision (Product Owner, 23 Nov)

Harry chose **C** — a pluggable binding layer, cucumber-js first — and asked for the work to be broken down before the
weeks are committed. This ticket is the first slice of C, and it is the cheapest useful part of it: build the seam,
make detection real, and replace estimates with a counted inventory of what one corpus needs.

**Read the rest of this ticket before writing code: this ticket does not add cucumber-js support.** It makes the shape,
and it makes the product tell the truth about what it cannot read.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | An ecosystem is a module under `testops/extract/ecosystems/` implementing one protocol: `detect(files) -> Ecosystem | None`, `bindings(files) -> list[Binding]`, `drivers(files) -> dict[str, str]`, and a declared name. The registry raises if two modules claim the same name or if none matches - no silent default, in the spirit of TESTOPS-47. |
| AC2 | The ecosystem chosen for each repository is **recorded per run and per repository** in the store, and shown in the sources sentence and the run page. "We read it as X" is a fact the record can print. |
| AC3 | Reqnroll/.NET and Python keep their current behaviour **exactly**: CotW 94/90/1/1/2, ReqOverflow 17/17, case-page goldens byte-identical after the refactor. The seam must be provable by the absence of change. |
| AC4 | A repository whose ecosystem is detected but unsupported reports `not_assessable`, naming the ecosystem and saying support does not exist. It must not report "no layers found" or "steps could not be tied to a layer". Proven on the `restfulbooker` corpus already in the store (JS/Cypress against a Java product). |
| AC5 | **No half-implementation.** cucumber-js must still be unsupported at the end of this ticket. A partial extractor that places some claims is not acceptable - an unplaced claim and a wrongly placed claim are different failures and only the first is honest. |
| AC6 | `docs/ecosystem-inventory-cucumber-js.md`, written from the corpus blobs in the store, with **counts not adjectives**: how many binding declarations exist and in which syntaxes (`Given('...')`, `Given(/regex/)`, `this.Given(...)`, hybrid), how drivers/custom commands are expressed, which layer signals a JS/TS vocabulary needs (Playwright, Cypress, supertest, axios, fetch, prisma/knex), and for each: what the current .NET vocabulary would wrongly conclude. Include a costed estimate per piece. |
| AC7 | A test asserts every registered ecosystem module declares a name, that detection is total (every repo with a recognisable marker resolves to exactly one ecosystem), and that an unrecognised repository is reported as `unknown` rather than guessed. |

## Notes

- AC6 is the deliverable Harry actually asked for. If it shows the layer vocabulary must be per-ecosystem rather than
  shared, that is a finding, and it changes T42-C's shape — say so plainly.
- Do not refactor the analysers. The seam is in extraction; the analysers take `list[Binding]` and should not care
  which module produced them.
- Keep `BINDING`, `SIGNALS` and `LAYER_ORDER` working through the Reqnroll module; do not delete them and leave the
  analysers to find nothing.
