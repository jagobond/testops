---
id: TESTOPS-39
title: A second specimen of a different shape, to find out whether the analyses generalise
feature: F2
status: ready
autonomy: build
depends_on: TESTOPS-38
---

# TESTOPS-39 — Prove it on something that is not CotW

## Why (Product Owner)

> "I'm pretty sure you found a pair like this online previously, didn't you? … Check your history first, then look
> online again for public repos."

History: the earlier find was `reqnroll/Sample-ReqOverflow` — C#/Reqnroll, and it is already in use. That makes
three C#-flavoured specimens (two of them Reqnroll) and one Python product. Nothing yet proves the analysers work
on a different ecosystem.

## The pair

- **Tests:** https://github.com/m-pujic-levi9-com/cypress-cucumber-e2e-tests — JavaScript, Cypress + Cucumber,
  `.feature` files with `.stepdef.js` bindings (51 files, actively maintained).
- **Product:** https://github.com/mwinteringham/restful-booker-platform — Java, multi-service SaaS platform,
  338 files, 178 stars, actively maintained. Its own README names the Cypress suite as the tests for it.

Why this pair: a genuinely different ecosystem (JS tests, Java product), a different binding technology
(`.stepdef.js` rather than C# attributes), **separate repositories**, and a product made of several services —
which is the shape ADR-1 has just made first class.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Both repos are cloned at pinned commits, recorded with their commit ids, and analysed by the level-fitness and duplication analysers under project slug `restfulbooker`. |
| AC2 | The step-binding extractor handles `.stepdef.js` or reports `not_assessable` with the reason. **A crash is a failure; a refusal is a finding.** Report exactly which binding styles it can and cannot read. |
| AC3 | Every claim renders without a page error, and any analyser that produces zero claims says why in the terms the honesty rules require. |
| AC4 | A written assessment: what generalised unchanged, what needed a new extractor, what is CotW-specific and would mislead another team. Name the specific claims that are wrong, with `file:line`. |
| AC5 | The assessment states the sample sizes honestly: how many scenarios, how many asserting steps, how many claims of each verdict — so nobody mistakes a 6-scenario sample for a trend. |
| AC6 | Nothing in either the product repo or the test repo is modified. Clones live outside both source trees. |

## Notes

- The point is **falsification**, not another green run. If the level-fitness analyser needs Gherkin step tables to
  work and this corpus lacks them, that is the finding, and it goes in the report rather than into a fix.
- If the licence of either repo forbids analysis, stop and say so — do not analyse and hope.
