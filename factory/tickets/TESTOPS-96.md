---
id: TESTOPS-96
title: A model as a recall probe, not a judge
feature: F3
status: queued
autonomy: build
depends_on: TESTOPS-95
---

# TESTOPS-96 - Ask the model what we missed

## Why

A blind gold set measures recall on 40 assertions. To find *what kind* of issue we are blind to, ask a strong model, over
the cases we called `distinct`, how each assertion could be wrong - then adjudicate. The model generates hypotheses; it
decides nothing.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A harness sends each sampled `distinct` case an evidence pack (assertion, binding, product surface at commit) and asks only for candidate problems, each with the rows it rests on. Replies that cite nothing are discarded. |
| AC2 | Every candidate that survives is adjudicated by a human and stored as `confirmed_blind_spot` or `not_a_problem`, with the reason. |
| AC3 | The output is a blind-spot table grouped by kind (asserts nothing, asserts its own fixture, satisfied by a mock, passes regardless, ...), with counts and the sample it came from - the input to deciding which new rule or gate to build. |
| AC4 | No cases, no verdicts and no page copy change. This ticket produces a measurement and a list, nothing else. |
