---
id: TESTOPS-72
title: The product is evidence - is this test repeating work the developer already did?
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-70
---

# TESTOPS-72 - Wire the product into the verdict

## Why this exists

The tool has always discovered the product's surfaces and never used them: in `level_fitness.py` the word `surface`
appears once, as a parameter. Every verdict is a statement about the test suite. Harry's framing is the one this tool
exists to answer - **"is the tester essentially repeating work that the developer has already done?"** - and that question
cannot be answered from one side.

This ticket makes the product evidence in the verdict, and it must do so without repeating the failure that killed v0.1:
the rule "a cheaper surface exists" was true for almost every scenario in any product and scored precision 0.118. The
difference between then and now is that surfaces now carry **claims** - what each route says it does - so the match can
be evidence rather than proximity.

## The judgement

A claim is **`repeats product`** when all of the following hold, and it records each one as evidence:

1. the claim needs a browser (`I3` or `I4`) - a browser is the expensive instrument, so this is where repetition costs;
2. a product surface exists whose route or claim shares a **meaningful** word with the assertion - a word that is not in a
   stop list of generic testing words (`the`, `data`, `result`, `page`, `should`, `correct`, `displayed`, ...);
3. that shared word is not merely the noun the whole repository is about (a common-noun guard: if the word matches more
   than a stated share of all surfaces, it does not count as evidence);
4. the matched surface id, the matched word and the matched route are recorded on the claim, so the case page can show
   *why* - a verdict with no quotable evidence is not published.

The verdict says what a reader can act on: the product already exposes this at the API, so a browser check re-verifies
the developer's work; the proposed action names the API-level check and states what a browser check would still be needed
for (rendering, interaction), so the reader is not told the UI test is worthless.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | `surfaces` is **used** by the analyser: the parameter is consumed, and a claim carries `detail["product"]["state"]` (`found` / `zero` / `not_assessable`), the matched surface id and route, and the matched word. A claim with no match records `zero` or `none`, never silence. |
| AC2 | **The flip test exists and is the proof Harry asked for:** one fixture suite analysed twice - once with a product whose surfaces include the route, once with a product that reads fine and declares no such route - and the **same assertion carries different verdicts** in the two runs, with the difference traceable to the product alone. Nothing else in the two runs differs. |
| AC3 | Precision guards are pinned by tests: a claim whose only overlap is a generic word (`data`, `result`, `page`, `correct`) does **not** match; a word matching more than the stated share of all surfaces does not match; a claim that does not need a browser (`I1`, `I2`, `KP`) is never `repeats product` however well it matches. |
| AC4 | The `not_assessable` path is real: when the product could not be read (a Java-less reader, a Python-only reader over Java, an unreadable arm), a browser claim is **not** `repeats product` and says the product could not be consulted - the same distinction `sources_missing` already makes. Pinned by a run whose product arm is unreadable. |
| AC5 | The case page shows the product evidence for the claim: the matched route, the matched word and the surface's own claim, in the reader's words. A verdict of `repeats product` with no visible evidence is a failure of this ticket. |
| AC6 | Aggregate honesty: the run page's counts separate claims that **are** `repeats product` from claims where the product could not be consulted, and neither is folded into the other. |
| AC7 | The corpus is re-read: on restful-booker, state how many of the 43 claims become `repeats product`, and paste the three strongest matches with their routes and matched words so a reader can argue with them. A number without examples is not evidence. |
| AC8 | No existing verdict moves on the .NET corpus unless the product evidence justifies it: list every case whose verdict changes in the CotW run and, for each, the rule that moved it. Contract suite green; full suite green. |
