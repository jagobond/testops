---
id: TESTOPS-76
title: The source band reads "consulted" where it means "read", and asserts blind spots the case never had
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-72, TESTOPS-73
---

# TESTOPS-76 - Three words on the source band that overclaim

## Why this exists

The band's facts are backed by the store and its links are right. Its **words** overclaim in three ways, and the corpus's
flagship case is the worst example: restfulbooker, where the product was read, 25 surfaces were found, and the analyser
consumed none of them.

1. **"Consulted" is indistinguishable between two states** - "the run read this repository" and "the verdict used it".
   The band note's converse ("a kind that is not tagged here was not part of the evidence") pushes the reader to the
   second reading.
2. **The test-only sentence is not scoped by need.** A case whose analyser never needed the product - duplication on
   reqoverflow - still says the product's routes "could not be consulted", asserting a blind spot the analysis did not
   have. The tag is withheld correctly; the sentence must follow the same rule.
3. **The standing absence line misleads while the link seam is unpopulated.** Every case says "a kind that is not tagged
   here was not linked to this case", when in fact no collector can write a link yet. A reader cannot distinguish "this
   case has no tracker item" from "the tool never links tracker items".

TESTOPS-72 makes the analyser consume surfaces for browser claims, so "the verdict used the product" becomes true for some
claims and false for others **within one case** - which makes the distinction this ticket draws more necessary, not less.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The product tag states what actually happened, in the reader's words: "read by the run" when the run read it but the claim reached no product-backed conclusion; "used by this claim" only when the claim records a product match (a surface id and a matched word). Both states are distinguishable without hovering, in text. |
| AC2 | The test-only sentence follows `NEEDS`: when the analyser's needs exclude the product, the page says "the product was not part of this analysis" rather than asserting a blind spot; when the product was needed and could not be read, it keeps the blind-spot wording. Both pinned by a page test on each case shape. |
| AC3 | The absence line is true today: while no collector writes links, the page says once that tracker and pipeline links are not yet recorded by the tool, and stops implying that a given case lacks them by choice. When the seam is populated the sentence changes with it - one constant, one place. |
| AC4 | No false precision: a claim with no product match never renders a "used by this claim" tag, and a case where every claim lacked a match renders no product tag as "used". Pinned. |
| AC5 | Contract suite green including the case-page opening promise; full suite green; goldens regenerated deliberately with the wording change listed. |
