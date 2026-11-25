---
id: TESTOPS-23
title: The page narrates the analyser instead of telling the reader one story
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-19
---

# TESTOPS-23 — Copy that reads as one argument

## Why

The Product Owner, on `case-demo-product-levels-20261122T011316-03`:

> "The verbiage is still not right, but I'm not quite sure how to explain why yet. That might need another
> iteration."

He could not name it, which is a diagnosis problem, not a specification problem. Here is the page text, and
what is wrong with it, line by line.

### The page, as a reader meets it

> **Browser not needed**
>
> **1. What is asserted** — "each fact's data-fact-id is the same on both loads"
> Test source: features/review_panel.feature:32 at commit a3f19853 — the commit this claim was read at.
>
> **2. Where the name came from** — "This name comes from the test's own scenario title: 'Every rendered fact is
> anchored by a stable data-fact-id'. It is the test author's name for the scenario, not a requirement: nothing
> here was checked against one."
>
> **3. What the test actually does** — "It drives a browser." Then four observations, three of which are other
> steps in the same scenario, each ending "…that drives a browser."
>
> **4. Why that does or does not establish it** — "The assertion is about the page as served: each fact's
> data-fact-id is the same on both loads. The page the server sends settles it, yet the run drives a browser, so
> it pays for a browser that decides nothing extra."
> "What settles it. **It is settled by the page the server sends.**"
> "**Why it was classified this way:** the words name the page as served, which the response body settles."
>
> **5. What could not be checked** — Jira and Azure DevOps, blocked by policy.
>
> **6. Proposed action** — "Rewrite the step … to call the HTTP client instead of the browser; the response
> decides everything the browser is being used for."

### Seven specific faults

1. **The claim is stated three times** — section 1 quotes it, section 4 restates it, section 4's "what settles
   it" paraphrases it again. A reader re-reads the same sentence looking for the new information.
2. **Two labelling subsystems before the argument.** "2. Where the name came from" is a whole section spent
   on the provenance of a heading, sitting between the claim and the reason. It is honest and it is in the
   way. Provenance belongs as a line under the quote, not as a numbered step in the argument.
3. **The sentence talks about the classifier.** "Why it was classified this way: the words name the page as
   served…" — *the words* is the analyser's view of the assertion. A reader wants to know what is true of the
   test, not how a rule read its nouns.
4. **Fragment headings inside sections** — "What settles it." and "Why it was classified this way:" are labels
   disguised as sentences. Read aloud, the page stutters.
5. **Inconsistent voice.** "It drives a browser" (the test), "the run drives a browser", "the run only reads
   the responses the server sends" — three names for one actor.
6. **The verdict badge says what is absent, not what is wrong.** "Browser not needed" requires the reader to
   invert the negation and infer the cost. The fact is: *this claim is checked, more expensively than it needs
   to be.*
7. **Repetition inside lists.** Four observation lines, three of them context, each with the identical trailing
   clause "that drives a browser". They are evidence of what the scenario contains, not of the claim, and the
   page does not distinguish the two.

## What good looks like

One paragraph, one story, said once. For this case:

> **Checked — but this test costs more than it needs to.**
>
> The test asserts that "each fact's data-fact-id is the same on both loads". That is settled by the HTML the
> server sends: two responses, compared. The test opens a real browser to compare them, which works, but the
> browser is buying nothing the response does not already contain.
>
> *Rewrite the step to use the HTTP client; the response decides what the browser is being asked to prove.*
>
> Then the evidence — the step, its definition, the assertions around it — and then the provenance line.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Each of the seven faults above is removed, and a test or a corpus-level check pins each one: no assertion text repeated across sections; no sentence containing "the words"; no fragment-style pseudo-headings; one term for the test throughout; no verdict badge that states an absence; observation lines that distinguish evidence of the claim from context. |
| AC2 | The page's first paragraph answers, in order: is this checked; what is wrong with it; what should happen. A reader who stops after it can decide whether to read on. |
| AC3 | Provenance (scenario title, file:line, commit) appears as a labelled footnote under the quoted assertion, not as its own numbered section. The six sections become five, or six with provenance folded in. |
| AC4 | The quoted assertion includes its Gherkin keyword and reads as a sentence ("Then each fact's data-fact-id is the same on both loads"), not a bare lower-case fragment. |
| AC5 | No reader-facing sentence refers to the analyser, its rules, its vocabulary or its classification process. Where the rule matters, state the fact the rule found ("the response settles this"), not the rule. |
| AC6 | Observation lines that are context rather than evidence are visually separate and collectively introduced ("the other steps in this scenario, for context"), never presented as equal-weight support. |
| AC7 | The verdict vocabulary is rewritten to state what is true, not what is missing: `gap` → something like "Not proved — nothing runs a browser"; `review` → "Checked, but over-tested for what it asserts"; `distinct` → "Checked"; `unplaced` → "Cannot tell". Zero codes; footnote keeps the shorthand. |
| AC8 | All corpus prose passes a lint the ticket file defines, run as a test over every claim in a real run: no "the words", no duplicated assertion sentence across sections, no label interpolation, no double space, no sentence longer than 45 words. |
| AC9 | Verdicts unchanged: 94 claims, 90 distinct, 1 unplaced, 1 gap, 2 review. Copy changes only. |
| AC10 | Suite green on both interpreters. |

## Notes

- Do not "polish" by shortening everything. The problem is repetition and inside-out perspective, not length.
- Read the finished page aloud before reporting. The reviewer is instructed to do so as a reader who has never
  heard of TestOps, and to fail it if any sentence needs the footnote to be understood.
