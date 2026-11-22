# TESTOPS-21 build report — 2026-11-22

Branch `factory/testops-21-duplication-v2`. The Product Owner opened
`case-reqoverflow-dup-20261120T153431` and found eighteen findings that looked identical and presented
no finding. He was right, and the product was wrong twice: the claims were `schema_version 1` with no
assertion, no path, no line, no commit, no span and no action, and all eighteen sat under one case, so a
single decision would have silenced findings nobody had read.

Both defects are fixed in the analyser and the pipeline. Existing v1 runs are untouched.

## What changed

**`testops/analysers/duplication.py` (1.1.0 → 2.0.0).** The grouping rule is unchanged; the claim is
not.

- Every claim now carries the coordinates of the scenario's first asserting step (`Then`, or the
  `And`/`But` that follows it), the commit, the layers the scenario reaches, a reader-language
  interaction label, the rule that classified it, and a proposed action.
- The statement names the scenario's own `file:line`, quotes every asserting step, and names the copy
  that already establishes it with *that copy's* `file:line` and what settles it there. Two findings in
  one run cannot share a statement; the corpus produces 18 distinct statements out of 18.
- The proposed action raises the duplicate for the team — never condemns the test and never recommends
  deletion: *"Raise this with the team: this copy drives a browser to establish what
  `ReqOverflow.Specs.Controller/Features/Authentication.feature:8` settles in-process; keep one."*
- Each scenario's step-binding observations are recorded as `support`, the asserting step's binding
  first, so the page resolves evidence from the claim's coordinates and shows the feature excerpt and
  the step-definition body inline, as TESTOPS-19 established for level fitness.
- The intra-level branch (same layer, same steps) writes the same kind of claim, and the single-known-
  layer branch now judges unknown-layer copies against the identifiable copy rather than whichever
  scenario was parsed first.

**`testops/pipeline.py`.** A duplication run now records the scenario *and* step-binding observations,
writes every claim as v2 with the store's `claim_v2_requires_provenance` constraint enforced by the
database, and creates **one case per claim with one finding each**. The snapshot records
`schema_version = 2`. Suppressed claims raise no case at all, so a decision still stops re-reporting
that one claim and nothing else.

**`testops/cli.py`.** `duplicate` prints the number of cases, not a single case handle.

**Tests.** `tests/test_duplication_v2.py`, ten tests driving the real `run_duplication` against
`tests/fixtures/reqoverflow/` — the 108 test-suite files of the run the Product Owner opened, read from
its stored snapshot `reqoverflow-20261120-78153818` (test arm
`reqnroll/Sample-ReqOverflow@78153818`): 18 features, 48 scenarios, 123 bindings. Nothing is fetched;
the fixtures are the run's own content and the helper stores them in a throwaway blob store.
`tests/reqoverflow_fixtures.py` wires that corpus to the real pipeline. The tests cover AC1–AC6,
including the v1 legacy page.

## Evidence

Suite, clean invocation (`env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX
PYTHONNOUSERSITE=1`):

- Python 3.12.5 (`.venv`): **220 passed**, 25.31s. 210 before this ticket, 10 added.
- Python 3.11.15 (`uv run --no-project --python 3.11`): **216 passed, 4 skipped**, 24.88s. The four
  skips are the pre-existing pre-3.12 checks.

Level-fitness corpus replay, `scripts/replay_levels.py --acceptance` on snapshot
`cotw-levels-20261122-a3f19853-r6`: **94 claims, 90 distinct, 1 unplaced, 1 gap, 2 review** — PASS.
The duplication ticket touches no level-fitness code and no verdict moved.

Duplication corpus, measured separately on the real run
`reqoverflow-dup-20261122T090439` / snapshot `reqoverflow-20261122-78153818-r3`:

| measure | value |
|---|---|
| claims | 18 |
| cases | 18 |
| findings | 18 |
| findings per case | exactly 1 (maximum 1) |
| distinct statements | 18 of 18 |
| claims by layer | api 6, ui 11, controller 1 |
| features / scenarios / bindings | 18 / 48 / 123 |

Old run, not backfilled: `case-reqoverflow-dup-20261120T153431` still renders (37,979 bytes), carries
its original eighteen v1 statements, and says "recorded before provenance was captured" in section 1
for each. Confirmed by rendering the case through `app.case_page` from `data/testops.db`.

## Two new cases, rendered

Rendered from the store through `testops.web.app.case_page`; HTML stripped, text kept verbatim.

```
CASE case-reqoverflow-dup-20261122T090439-01
reqoverflow · Duplication
What this is
The scenario "User logs in with valid credentials" at ReqOverflow.Specs.API/Features/Authentication.feature:9 calls the HTTP client to assert "the login attempt should be successful" and "the user should be authenticated", which ReqOverflow.Specs.Controller/Features/Authentication.feature:8 already establishes in-process.
What to do
Raise this with the team: this copy calls the HTTP client to establish what ReqOverflow.Specs.Controller/Features/Authentication.feature:8 settles in-process; keep one.
Open · Analysed just now at Sample-ReqOverflow@78153818
Already covered
1. What is asserted
“the login attempt should be successful”
Source, the asserted line is marked: ReqOverflow.Specs.API/Features/Authentication.feature:9 — view in repository
7 Given there is a user registered with user name "Trillian" and password "139139"
8 When the user attempts to log in with user name "Trillian" and password "139139"
9 Then the login attempt should be successful
10 And the user should be authenticated
Test source: ReqOverflow.Specs.API/Features/Authentication.feature:9 at commit 78153818 — the commit this claim was read at.
2. Where the name came from
This name comes from the test’s own scenario title: “User logs in with valid credentials”. It is the test author’s name for the scenario, not a requirement: nothing here was checked against one.
3. What the test actually does
It drives the HTTP API.
The observations this claim rests on, recorded in this run:
- Sample-ReqOverflow@78153818:ReqOverflow.Specs.API/StepDefinitions/AuthStepDefinitions.cs:33 — the step that is asserted: a Then step definition for “the login attempt should be successful” that drives the HTTP API.
- Sample-ReqOverflow@78153818:ReqOverflow.Specs.API/Features/Authentication.feature:6 — the scenario “User logs in with valid credentials” begins at line 6, 4 steps.
- Sample-ReqOverflow@78153818:ReqOverflow.Specs.API/StepDefinitions/RegistrationStepDefinitions.cs:10 — a Given step definition for “there is a user registered with user name {string} and password {string}” that drives the HTTP API.
- Sample-ReqOverflow@78153818:ReqOverflow.Specs.API/StepDefinitions/AuthStepDefinitions.cs:26 — a When step definition for “the user attempts to log in with user name {string} and password {string}” that drives the HTTP API.
- Sample-ReqOverflow@78153818:ReqOverflow.Specs.API/StepDefinitions/AuthStepDefinitions.cs:39 — a Then step definition for “the user should be authenticated” that drives the HTTP API.
The step definition that runs the assertion, the step that is asserted: ReqOverflow.Specs.API/StepDefinitions/AuthStepDefinitions.cs:33 — view in repository
33 [Then("the login attempt should be successful")]
34 public void ThenTheLoginAttemptShouldBeSuccessful()
35 {
36 authApiDriver.Login.ShouldBeSuccessful();
37 }
4. Why that does or does not establish it
The scenario "User logs in with valid credentials" at ReqOverflow.Specs.API/Features/Authentication.feature:9 calls the HTTP client to assert "the login attempt should be successful" and "the user should be authenticated", which ReqOverflow.Specs.Controller/Features/Authentication.feature:8 already establishes in-process.
What settles it. It is settled by the application's own controllers in-process.
Why it was classified this way: the scenario's steps match those of ReqOverflow.Specs.Controller/Features/Authentication.feature:8 after normalisation, and its step definitions place this copy at api.
5. What could not be checked
Not connected when this claim was checked:
requirements — absent: no source is declared that could provide it.
They were never consulted, so nothing here says they were clean — only that this claim was never checked against them.
6. Proposed action and decision
Raise this with the team: this copy calls the HTTP client to establish what ReqOverflow.Specs.Controller/Features/Authentication.feature:8 settles in-process; keep one.
Decide this case — 1 finding rides on this decision, and it applies to this case only.
```

```
CASE case-reqoverflow-dup-20261122T090439-02
reqoverflow · Duplication
What this is
The scenario "User logs in with valid credentials" at ReqOverflow.Specs.WebUI/Features/Authentication.feature:9 drives a browser to assert "the login attempt should be successful" and "the user should be authenticated", which ReqOverflow.Specs.Controller/Features/Authentication.feature:8 already establishes in-process.
What to do
Raise this with the team: this copy drives a browser to establish what ReqOverflow.Specs.Controller/Features/Authentication.feature:8 settles in-process; keep one.
Open · Analysed just now at Sample-ReqOverflow@78153818
Already covered
1. What is asserted
“the login attempt should be successful”
Source, the asserted line is marked: ReqOverflow.Specs.WebUI/Features/Authentication.feature:9 — view in repository
7 Given there is a user registered with user name "Trillian" and password "139139"
8 When the user attempts to log in with user name "Trillian" and password "139139"
9 Then the login attempt should be successful
10 And the user should be authenticated
Test source: ReqOverflow.Specs.WebUI/Features/Authentication.feature:9 at commit 78153818 — the commit this claim was read at.
2. Where the name came from
This name comes from the test’s own scenario title: “User logs in with valid credentials”. It is the test author’s name for the scenario, not a requirement: nothing here was checked against one.
3. What the test actually does
It drives a browser.
The observations this claim rests on, recorded in this run:
- Sample-ReqOverflow@78153818:ReqOverflow.Specs.WebUI/StepDefinitions/AuthStepDefinitions.cs:36 — the step that is asserted: a Then step definition for “the login attempt should be successful” that drives a browser.
- Sample-ReqOverflow@78153818:ReqOverflow.Specs.WebUI/Features/Authentication.feature:6 — the scenario “User logs in with valid credentials” begins at line 6, 4 steps.
- Sample-ReqOverflow@78153818:ReqOverflow.Specs.WebUI/StepDefinitions/RegistrationStepDefinitions.cs:10 — a Given step definition for “there is a user registered with user name {string} and password {string}” that drives a browser.
- Sample-ReqOverflow@78153818:ReqOverflow.Specs.WebUI/StepDefinitions/AuthStepDefinitions.cs:29 — a When step definition for “the user attempts to log in with user name {string} and password {string}” that drives a browser.
- Sample-ReqOverflow@78153818:ReqOverflow.Specs.WebUI/StepDefinitions/AuthStepDefinitions.cs:42 — a Then step definition for “the user should be authenticated” that drives a browser.
The step definition that runs the assertion, the step that is asserted: ReqOverflow.Specs.WebUI/StepDefinitions/AuthStepDefinitions.cs:36 — view in repository
36 [Then("the login attempt should be successful")]
37 public void ThenTheLoginAttemptShouldBeSuccessful()
38 {
39 loginPageDriver.ShouldBeSuccessful();
40 }
4. Why that does or does not establish it
The scenario "User logs in with valid credentials" at ReqOverflow.Specs.WebUI/Features/Authentication.feature:9 drives a browser to assert "the login attempt should be successful" and "the user should be authenticated", which ReqOverflow.Specs.Controller/Features/Authentication.feature:8 already establishes in-process.
What settles it. It is settled by the application's own controllers in-process.
Why it was classified this way: the scenario's steps match those of ReqOverflow.Specs.Controller/Features/Authentication.feature:8 after normalisation, and its step definitions place this copy at ui.
5. What could not be checked
Not connected when this claim was checked:
requirements — absent: no source is declared that could provide it.
They were never consulted, so nothing here says they were clean — only that this claim was never checked against them.
6. Proposed action and decision
Raise this with the team: this copy drives a browser to establish what ReqOverflow.Specs.Controller/Features/Authentication.feature:8 settles in-process; keep one.
Decide this case — 1 finding rides on this decision, and it applies to this case only.
```

## What this does not satisfy

1. **Section 1 quotes the first asserting step; the statement quotes the whole asserting pass.** The
   coordinates point at the first `Then` and the evidence list carries both bindings, but a scenario
   with two asserting steps shows only the first in the section-1 block quote. That is the step the
   claim is pinned to; the full pass is in the statement and the evidence.
2. **The duplication snapshot is not rebuildable.** A duplication run records its claims and
   observations, but its snapshot still has no test/product arm record, so `rebuild.load` refuses it by
   design. Only level-fitness runs are rebuildable today. This ticket did not widen that.
3. **Same-file, same-level duplicates are handled, but the page's "It drives a browser" wording for a
   controller-only group is generic.** The claim is correct; the section-3 summary comes from the
   scenario's span and is honest, just not specific to duplication.
4. **No pixel/visual check.** The two pages above were rendered through `app.case_page` and inspected as
   text; the suite asserts content and structure, not layout.

## Where to look

`testops/analysers/duplication.py` (claim construction, `_claim`, `analyse`), `testops/pipeline.py`
(`run_duplication`: observations, v2 persistence, one case per claim), `tests/test_duplication_v2.py`,
`tests/reqoverflow_fixtures.py`, `tests/fixtures/reqoverflow/`, `testops/cli.py`.
