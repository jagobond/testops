---
id: TESTOPS-83
title: The case page quotes its evidence but never shows the code
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-73
---

# TESTOPS-83 - Show the two lines this case is made of

## Why this exists

A case page currently says *"the product already declares `POST /`"* and *"the test asserts the step … will be created"* and
links both to their commits - but a reader never sees **the code**. They are asked to accept that those two things are what
the tool says they are, on the strength of a link they must click out of the page to check. For a tool whose whole claim is
that it reads both sides, the two lines are the argument, and they are missing.

Harry's words: "there's no code snippet showing the test in the product code that is being referenced."

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The case page shows the **test line** the claim was read from: the assertion's own text as it appears in the feature file, with its file, line number and commit, and the surrounding step context (the step that supplied the value, where the reader recorded it). Read from the stored blob, not from a live checkout - the page must render what the run saw. |
| AC2 | The case page shows the **product line** the verdict rests on: for a `repeats product` case, the annotation and method signature that produced the matched route (`@RequestMapping(value = "/", method = RequestMethod.POST)` and `public ResponseEntity createRoom(...)`), with file, line and commit. Where the matched surface is a Python route, the decorator and the function signature. Nothing invented: where the reader did not record a line, the page says so rather than guessing one. |
| AC3 | Both snippets are **verbatim** from the stored blob, shown in a monospace block with the matched word marked (the shared word that justified or declined the match) and no reformatting beyond whitespace trimming. A test asserts the rendered snippet equals the blob's own lines. |
| AC4 | The snippets obey the same rule as everything else here: escaped as text, never rendered as HTML, never fetched at render time, and no secret or absolute host path can appear in them (the store holds public corpus files; a future private repo must not leak through this path - screen the snippet against the same credential shapes the guard already knows). |
| AC5 | Long snippets are trimmed honestly: a stated maximum with an ellipsis and the true line count, never a silent cut. A 400-line handler shows its annotation line and signature, and says how many lines it did not show. |
| AC6 | Keyboard and screen-reader reachable: the snippet is a labelled region naming the file and line, and the page does not rely on colour to mark the matched word (it is also wrapped in a marker with an accessible name). |
| AC7 | Full suite green; contract suite green; goldens regenerated deliberately with the snippet block for the demo-booking cases and listed, including one case where the product line could not be located (the page says so). |
