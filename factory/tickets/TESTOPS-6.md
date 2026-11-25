---
id: TESTOPS-6
title: The case page — an argument a developer can act on
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-11
---

# TESTOPS-6 — The case page

## Why

The Product Owner reviewed the current page: *"Look at the claim heading ... What is this? Is this a
requirement? Where did it come from? ... the 'ev' section just has links to some scenarios, with no
justification for why they're there ... even I don't understand what this claim is trying to tell
me."*

The claims are now readable and carry their own coordinates (TESTOPS-4, TESTOPS-10, TESTOPS-11).
This ticket makes the page present them as an argument — assertion, provenance, what the test did,
why that falls short, what could not be checked, what to do — rather than a heading, a template
sentence and a pile of links.

Each case is one claim. The page must be decidable in one read, by someone who has never heard of
TestOps.

## The page, in order

1. **What is asserted** — `assertion_text` verbatim, with `assertion_path:line` as a permalink at
   `assertion_commit` (the commit the claim was read at, never HEAD).
2. **Where the name came from** — the scenario title, explicitly labelled as the test's own name, and
   never presented as a requirement.
3. **What the test actually does** — `span` and the instrument in words ("drives the HTTP API",
   "drives a browser").
4. **Why that does or does not establish it** — the statement, plus `interaction_label` and
   `established_by` in the reader's words ("classified because the assertion names an accessibility
   property a browser computes").
5. **What could not be checked** — `sources_missing`; an empty list renders as "every source needed
   for this claim was available", never as a blank.
6. **Proposed action and decision** — the action sentence, then the decision form.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A case page renders all six sections for a v2 claim, in that order, from the store only, server-rendered, no JavaScript, no network at render time. |
| AC2 | The assertion permalink resolves to `blob/<assertion_commit>/<assertion_path>#L<line>` using the claim's own commit — a test asserts the commit in the URL equals the claim's, and that a claim from an older commit does not link to HEAD. |
| AC3 | Evidence is resolved from the claim's own coordinates. `queries.evidence_for_subject`'s `LIKE %feature%` lookup is not used for v2 claims; a test proves a claim in `a/x.feature` does not pick up evidence from `b/x.y.feature` or from another snapshot. |
| AC4 | The scenario title is labelled as coming from the test ("from the test's own scenario title"), and no page implies a requirement source exists while none is connected. |
| AC5 | Every evidence link carries a one-line statement of what it shows. A bare list of links fails this criterion. |
| AC6 | No `I1`..`I4` or `KP` appears in the primary text of any page; if shown at all, the code sits in a footnote below the decision, labelled as debugging shorthand. |
| AC7 | `interaction_label`, `span` and `established_by` are rendered in the reader's words, not as data structures (no raw JSON, no list reprs, no codes). |
| AC8 | A decision applies to this case only; the form states how many findings ride on it; reopening deletes the suppression and the page says so. |
| AC9 | A v1 claim (older runs, duplication findings) renders with a provenance section reading "recorded before provenance was captured" — never blank, never an exception. |
| AC10 | A case with no findings is described as a resolved case, not an error; the home page's empty state reports freshness (last analysed time and commit), never "all clear". |
| AC11 | The case list shows the claim statement, not `finding.title`, so no heading ends mid-sentence. |

## Notes

- Real path: `testops/web/app.py` (`index`, `case_page`), read models in `queries.py`
  (`claim_read`, `case_row`, `finding_rows`, `freshness`), permalinks in `links.py`.
- Nothing behind a disclosure: a reason a scanning lead has to click for is a reason they will not
  read.
- Keep it ugly-but-legible if you must choose. No framework, no build step.
- The specimen to develop against is in the store: run `demo-product-levels-20261121T215534` and the current
  replay output, which include the accessibility `gap` and the two `review` claims.
