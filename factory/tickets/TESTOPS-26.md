---
id: TESTOPS-26
title: The summary is there, but the reader has to dig it out of a paragraph
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-23
---

# TESTOPS-26 — Three lines a reader can scan

## Why

TESTOPS-23 removed the analyser's voice and merged the six sections into five. What it produced, rendered:

> **Checked, but over-tested for what it asserts.** The test asserts the step "Then each fact's data-fact-id is
> the same on both loads". That is settled by the page the server sends, and the test drives a browser, which is
> a dearer way to reach it. Rewrite the step "each fact's data-fact-id is the same on both loads" to call the
> HTTP client instead of the browser. The response decides everything the browser is being used for.

The judgement is in the first sentence, in bold, which is right. Then everything else is one block, so:

- **the action is the third sentence**, found by reading past the argument — the Product Owner asked to scan and
  decide, and this makes scanning equal to reading;
- **the step text appears twice**, quoted twice in four sentences;
- **the last sentence restates the second** ("the response decides everything the browser is being used for" is
  "settled by the page the server sends" again);
- **"dearer"** is a word no engineer writes. It came from the builder reaching for variety;
- **quotes are mixed** — curly around the first mention, straight around the second;
- **identifiers are plain** — `data-fact-id`, `HTTP client` and the step text are prose, not monospace.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The opening block is three visually distinct parts: a **headline** stating the judgement in plain words; **one sentence** saying what is wrong; **one sentence** saying what to do, visually separated from the argument (own line, own label or style) so the eye lands on it. |
| AC2 | The step text is quoted once in that block, in monospace; the action refers to it without re-quoting it in full. |
| AC3 | No sentence restates another within the block: a test asserts the block contains no repeated clause of six or more words. |
| AC4 | Identifiers (paths, step text, `HTTP client`, attribute names) render in monospace everywhere on the page, not in prose quotes. |
| AC5 | One quote style throughout the rendered copy (typographic), except inside code spans, which keep their own characters. |
| AC6 | A plain-English lint runs over every claim in a real run: fails on "dearer", "whilst", "purportedly", "utilise", "commence", "prior to", "in order to", "leverage", "facilitate", "endeavour", plus any sentence over 45 words. |
| AC7 | The same three-part structure holds for all four verdicts; render one of each and confirm the action line exists in each (a `distinct` claim still says what to do or says plainly that nothing needs doing). |
| AC8 | Verdicts unchanged: 94 claims, 90 distinct, 1 unplaced, 1 gap, 2 review. |
| AC9 | Suite green on both interpreters. |

## Notes

- The headline is a judgement, not a category: "Checked, but over-tested for what it asserts" is a judgement;
  "review" is a category. Never print the category at a reader.
- Do not shorten by deleting the argument. Shorten the summary and keep the argument below it.
- The action line is the thing the Product Owner reads second and acts on. If it is a sentence he has to hunt
  for, the page has failed again.

## Addendum — two typographic defects seen in the rendered build

| id | criterion |
|----|-----------|
| AC10 | No space between an inline code span and the punctuation that follows it: "…both loads , but…" renders as "…both loads, but…". A test asserts no `</code> ,` / `</code> .` pattern reaches the output. |
| AC11 | The "What to do" box has even vertical padding, so descenders are not tight against the bottom border (visual check, screenshot in the report). |
