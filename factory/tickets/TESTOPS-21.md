---
id: TESTOPS-21
title: The duplication analyser still writes v1 claims, so its cases say nothing
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-19
---

# TESTOPS-21 — Duplication claims carry their own subject

## Why

The Product Owner opened `case-reqoverflow-dup-20261120T153431` and saw eighteen findings that look identical
and present no finding:

> "I don't know what's going on here. 18 claims, all the same, and they don't present any actual findings?
> Looks like a bug to me."

It is a bug, and the store confirms it. Those 18 claims:

- are `schema_version = 1`, so they carry no `assertion_text`, `assertion_path`, `assertion_line`,
  `assertion_commit`, `span`, `established_by` or `proposed_action`;
- state only the relation — "asserts the same claim as 1 cheaper copy(ies) at controller; this copy drives api"
  — which is identical across every finding, because it names the *verdict* rather than the assertion;
- sit under **one case for the whole run** (`case-<run_id>`), so a single decision would silence eighteen
  findings the reader never saw. That is the defect TESTOPS-4 fixed for level fitness and duplication never
  received.

The page then renders six sections of "not recorded" for each of them, which is honest and useless.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Duplication claims are v2: each carries `assertion_text`, `assertion_path`, `assertion_line`, `assertion_commit`, `span`, `interaction_label`, `proposed_action`, and satisfies `claim_v2_requires_provenance`. |
| AC2 | The claim statement names the duplication concretely — what is asserted, by which scenario, and which other copy already establishes it, with that copy's `file:line`. Two findings in one run must not share a statement. A test asserts all statements in a run are distinct. |
| AC3 | One case per claim: a run yields 18 cases for 18 duplicate findings, and no case holds more than one finding. A test asserts this on the real `reqoverflow` corpus. |
| AC4 | The proposed action says what to do about the duplicate ("this copy drives a browser to establish what `<file:line>` settles over HTTP; keep one"), phrased per the vocabulary rules — raise it for the team, never condemn, never recommend deletion outright. |
| AC5 | Evidence resolves from the claim's coordinates and shows the asserting step inline, as TESTOPS-19 established. |
| AC6 | Existing v1 duplication runs are not backfilled and keep rendering "recorded before provenance was captured"; only new runs are v2. Confirm the old page still renders. |
| AC7 | Level-fitness corpus numbers are untouched (94/90/1/1/2); the duplication corpus is measured separately and reported. |
| AC8 | Suite green on both interpreters; CI enforced. |

## Notes

- The 18 claims are genuinely distinct tests (`ReqOverflow.Specs.API/...Authentication.feature#User logs in with
  valid credentials` and its WebUI twin are different claims). The failure is that the *statement* records the
  relation instead of the assertion, so a reader cannot tell them apart.
- Do not merge the duplicates into one finding to reduce the count. One claim per assertion is the product's
  unit, and a team decides on each.
