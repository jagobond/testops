---
id: TESTOPS-99
title: Price a verified finding, then decide
feature: F3
status: queued
autonomy: build
depends_on: TESTOPS-98
---

# TESTOPS-99 - The number the decision rests on

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | For a fixed corpus, report: candidates proposed, candidates accepted, verified findings that the rules alone did not raise, tokens per stage, wall time per stage, and **cost per verified finding**, with the price table used and each price marked as verified or assumed. |
| AC2 | Report the same corpus's human baseline honestly: how long a reviewer takes to find one issue by reading the suite, measured or cited, or state that no baseline exists. |
| AC3 | State the decision the numbers support, including the case for stopping, and what extra data would change it. |
| AC4 | No number without its sample and interval. |
