---
id: TESTOPS-92
title: The switch says on and the reader typed true
feature: F2
status: ready
autonomy: build
depends_on: TESTOPS-88
---

# TESTOPS-92 - A switch that ignores a value is a switch that lies

## The evidence

Harry opened the same case page twice, once plain and once with `?agent=true`, and saw **the same page**. He asked whether
they were meant to differ. Measured just now against the deployed app:

```
plain body == agent=true body   -> True    (7358 == 7358 chars)
plain body == agent=on  body    -> False   (8601 chars, "Explanation of this case" present)
```

The flag accepts only the literal `on`. `true`, `1`, `yes` and `True` are silently ignored and the page renders as if the
agent were off — which is exactly what a reader who typed them is entitled to read as "the agent does nothing". On the
morning of a demo this is the trap that makes the feature look broken while it is working.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The flag accepts `on`, `true`, `1`, `yes` (case-insensitive, whitespace-trimmed) as "show the explanation", and `off`, `false`, `0`, `no` as "do not". Default stays off. Pinned as a table: eight accepted values, plus empty and absent. |
| AC2 | **An unrecognised value is never silent.** `?agent=maybe` renders the page without the explanation **and** a single line saying the value was not understood, naming what is accepted. A reader who typed something wrong must not be able to conclude the feature is dead. Pinned: the line appears for `maybe`, `2`, `onn`, and does not appear for a recognised value or for no parameter at all. |
| AC3 | `agent=off` and no-parameter remain byte-identical to each other and to the page before this ticket, over all 275 real pages - the AC1 gate from TESTOPS-88 must still pass exactly. |
| AC4 | `/agent-report` shows which flag values it saw, so a demo-day typo is visible in the meter rather than inferred from an empty column. |
| AC5 | No weakening: suites and contracts green; the citation validator untouched. |
