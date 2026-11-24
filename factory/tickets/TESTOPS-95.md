---
id: TESTOPS-95
title: A blind gold set, so recall is a number instead of an opinion
feature: F3
status: queued
autonomy: build
depends_on: TESTOPS-93
---

# TESTOPS-95 - Label the truth before looking at the tool

## Why

Precision has been attacked from both directions for weeks. Recall has never been measured, so "we catch the issues we
know about" is untested and unpublishable.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A sampled set of 40 assertions from at least two corpora, written to a workbook with the assertion, its path/line/commit and the product evidence, and **no tool verdict anywhere in it**. Harry and Bobby label each one: level correct / wrong level / duplicates product / cannot tell, plus one sentence why. |
| AC2 | A scoring harness reads the returned labels and computes precision and recall against the stored run, with confidence intervals and the sample size stated beside every number. |
| AC3 | Disagreements between the two labellers are reported as a separate number (inter-rater agreement) rather than silently resolved. |
| AC4 | The result is a page in the app (`/recall`) that states the method, the sample, the numbers and what the sample cannot tell you. No number appears anywhere without its interval. |
