# TESTOPS-39 review — the second specimen, independently checked

2026-11-22, reviewer. Branch `factory/testops-39-second-specimen`, tree clean at review time.
Every headline in the assessment was re-derived from the store, the blob corpus and the diff, not
taken on trust.

## Verdict — PASS

The assessment's central finding is correct and load-bearing: the tool read nothing that matters in
this corpus, said so to nobody, and rendered a false source sentence — and the two small slips I
found in the write-up (below) do not overturn it.

## Claims verified

**(a) The binding count.** I read the five collected `.stepdef.js` blobs straight out of the blob
store for snapshot `restfulbooker-levels-20261122-262404a9` and counted `\b(Given|When|Then|And|But)\s*\(`:
10 + 5 + 11 + 13 + 5 = **44**, matching the store's `bindings: 0` against a corpus that holds 44.
Two precision notes: only **13** are `Then(`; the assessment's phrase "all of the form
`Then('…', () => { … })`" is wrong — the 44 are Given/When/Then/And/But. And the JS test tree holds
**15** collected `.js`/`.ts` files (21 artefacts − 6 features), not the stated 14. Neither slip
changes the conclusion; both should be corrected if the assessment is cited.

**(b) The `.java` omission.** `testops/collectors/github.py:19-27`: `KINDS` maps `.csproj`,
`.feature`, `.feature.cs`, `.py`, `.cs`, `.ts`, `.js` — no `.java`. Confirmed in the store:
`select count(*) from artefact where snapshot_id like '%262404a9%' and uri like '%.java'` → **0**,
while the product contributed exactly 27 `.js`/`.ts` files (verified by URI listing). The product's
Java code was never fetched.

**(c) 43 claims, all `unplaced`.** `select verdict, count(*) from claim where run_id in
('restfulbooker-levels-20261122T201853','restfulbooker-dup-20261122T201909')` → 43 rows, every one
`unplaced`, no other verdict. Step-binding observations for the restfulbooker snapshots: extractor
`gherkin` only, 66 rows — no binding extractor observation exists at all. Zero cases raised.

**(d) The source sentence.** I rebuilt the assessment from the snapshot's recorded registry
(`state: available, capabilities: [code, test_code], observed: 48`) and rendered it through
`sources.Assessment.sentence()` (`testops/sources.py:256`). The exact sentence a page serves:

> Assessed: code and test code were consulted and returned 48 items.

48 is the artefact total (6 features + 42 stepdef-kind files), and no `.java` file is among them —
the sentence about `code` is false, as charged.

**(e) Scope of the diff.** `git diff --stat main..HEAD`: 6 files — factory bookkeeping (TICKETS.md,
review prompt, the assessment, tickets 41/42) and `testops/config.py` (+8, a `restfulbooker`
Project literal). No analyser, extractor, collector, renderer or store file moved.

**Suite.** `env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1 .venv/Scripts/python.exe -m pytest -q`
→ **417 passed**, matching the assessment's own claim.

## What generalised

No stored claim from this corpus is fully correct. Every one of the 43 is `unplaced` with a
"None of its steps could be tied to a layer" sentence, and I checked the actual bindings in the
blobs: `login.feature:13` is bound to `cy.xpath('//a[text()="Logout"]')`, `:14` to five
`cy.contains` calls, `:18` to `cy.contains('Log into your account')` — the layers exist and the
tool says they do not. The nearest miss to a correct claim: the "settled by what a person sees"
reading of the Thanks-for-getting-in-touch steps is substantively right about what would settle
them (the bindings assert visible DOM text in `div.contact`), but the same claim still asserts no
layer could be identified, which is false. So: nothing fully correct, and the one near-miss is
half-wrong in the same sentence.

What did generalise, as the assessment says: the Gherkin parser (6/6, 33/33), the collector's
two-role pinned-commit read, the claim schema, the renderer (43/43 through the read model without
exception), and duplication's rule producing an honest zero. Those verifications are consistent
with everything I re-ran.

## Licence and provenance

Test repo (`m-pujic-levi9-com/cypress-cucumber-e2e-tests`): **no licence** (GitHub API
`"license": null`) — all rights reserved by default. Product repo
(`mwinteringham/restful-booker-platform`): **GPL-3.0**. Nothing from either was copied into this
repository: the diff shows only a `Project` literal (owner/name coordinates) and factory files.
Reading public code at a pinned commit, storing metadata and quoting `file:line` facts with short
verbatim step texts and a line or two of binding code for criticism is analysis, not
redistribution, and is acceptable for both repos even under the stricter reading (GPL-3.0 governs
distribution of the code, not describing it; an unlicensed repo forbids copying and reuse, not
looking). Do not vendor either repo's files here.

## What I would do next

Fix the extractor and the collector together — a cucumber-js binding regex, a `.java` kind, and a
"cannot read this language" record replacing silent zeros are one small ticket's work — because
declaring the JS/Java ecosystem unsupported would mean the tool only ever speaks .NET, which
TESTOPS-39 was mounted to falsify and did not quite.

## Corrections owed to the assessment

1. "44 bindings, all of the form `Then('…', () => { … })`" → 44 bindings across all five keyword
   spellings (Given/When/Then/And/But), of which only 13 are `Then(`. The extractor reads 0 of all
   44 either way.
2. "14-file JavaScript test tree" → 15 collected `.js`/`.ts` files in the test repo.
3. The example step counts by label are accurate as stored; no other slip found.
