---
id: TESTOPS-16
title: Say which kind of nothing it is
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-15
---

# TESTOPS-16 — Empty evidence, two meanings

## Why

TESTOPS-14's review, concern 3: a v2 claim from a snapshot written *before* observations existed renders
"recorded no observations at these coordinates" — when the truth is that the run recorded no observations
at all, for anything. `None` ("not recorded") and `[]` ("nothing bears on this claim") are distinct in
the model and collapse into one sentence on the page.

A reader cannot tell "we looked and found nothing relevant" from "nobody was looking". Those are
different trusts.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A snapshot with no observation rows renders "this run recorded no observations; it predates observation recording" — distinguishable at a glance from a claim whose support is empty because nothing matched. |
| AC2 | A claim with `support = []` on a snapshot that *does* record observations renders "nothing in this run bears on this claim", with the run's observation count alongside so a reader can judge the emptiness. |
| AC3 | A v1 claim keeps its existing "recorded before provenance was captured" text; the three states never share wording. |
| AC4 | Tests cover all three states from stored data, not from mocked dicts. |
| AC5 | No verdict changes and no schema change. |
