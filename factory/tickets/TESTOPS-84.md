---
id: TESTOPS-84
title: When the code block cannot delimit a declaration it renders as if it were complete
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-83
---

# TESTOPS-84 - The silent truncation, in the state where honesty matters most

## Why this exists

TESTOPS-83 put the code on the page and its review found the one case where the new block lies by omission: when the brace
walk cannot close a method body (a file the reader cannot lex cleanly, a body missing its brace), the declaration's end is
set at the **signature**, so the caption states **no omitted count** and **no ellipsis row** appears. The reader sees two
lines that look like the whole declaration while the stored file continues below.

Second fault, found in the same review: the caption's arithmetic is true but explains the wrong constraint. "At most 8 lines
are shown: lines 42-43 of a 6-line declaration, so 4 lines are not shown" invites the reader to blame the 8-line cap for a
cut the cap did not make, when what is missing is the body.

Harry's rule, from earlier work on this tool: never a silent cut.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | When the signature's `{` is found and never closed, the page says so in words - "the rest of this declaration could not be delimited" - and shows the ellipsis row. It must never render an undelimitable declaration as complete. Pinned with a fixture whose method body has no closing brace. |
| AC2 | When the declaration WAS delimited but the cap cut it, the caption says what the cap did and what the body is: "8 of 34 lines of this declaration" rather than a sentence that blames the cap for both. Pinned for a long delimited method. |
| AC3 | The three states are distinguishable in words, not just numbers: complete and small (no ellipsis, no count), delimited but trimmed (count + ellipsis), undelimitable (a stated inability). One test per state asserting the exact sentence. |
| AC4 | For a Python surface, the same three states hold with the declaration's real unit (decorator plus `def`, ending at the dedent), and a docstring-heavy handler does not read as undelimitable. |
| AC5 | Full suite green; contract suite green; goldens regenerated deliberately with the three states and listed. |
