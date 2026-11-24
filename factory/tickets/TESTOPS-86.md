---
id: TESTOPS-86
title: A Python signature end is counted in strings and comments
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-84
---

# TESTOPS-86 - Brackets inside a string are not brackets

## Why this exists

TESTOPS-84 made the code block honest about what it cannot delimit. Its review found that
`_python_signature_end()` is a raw character scan: it counts `(` and `)` over every character of the line, including those
inside strings, comments and f-strings. In the path where the file cannot be parsed, that can place the end of the shown
"signature" in the wrong place - a wrong answer that looks exactly as confident as the right one, in the state the ticket
was built to be careful in.

The Java side reads the lexer's tokens; the Python fallback does not, and it is the fallback that runs when the file is
unparseable - precisely when the reader should be most careful.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The Python signature end is found in **code position**: string literals (single, double, triple, f-strings) and comments are consumed before brackets are counted. Pinned with a `def` whose default argument contains a `)`, one whose annotation is an f-string, and one with a `#` comment containing brackets. |
| AC2 | Where the fallback genuinely cannot tell, the block says so rather than guessing - the third sentence from TESTOPS-84, not a confident count. Pinned. |
| AC3 | The three-state sentences from TESTOPS-84 are unchanged for the cases that already worked; the goldens from that ticket are unchanged except where a state legitimately changes, and each change is listed. |
| AC4 | Full suite green; contract suite green. |
