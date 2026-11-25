# TESTOPS-21 review — 2026-11-22

## Verdict

PASS — every criterion holds on real execution, and a reader opening one of the new case pages now gets a concrete, located, actionable finding instead of eighteen copies of the same verdict.

## Criteria

- AC1 HOLDS. All 18 claims in the new runs are `schema_version = 2` with `assertion_text`, `assertion_path`, `assertion_line`, `assertion_commit`, `span`, `interaction_label` and `proposed_action` populated; the store's `claim_v2_requires_provenance` constraint accepted them (test asserts the DB, not a Python guard).
- AC2 HOLDS. Each statement names its own scenario, its own `file:line`, quotes the assertion verbatim, and names the establishing copy with that copy's `file:line`. All 18 statements in each of the three new store runs are distinct (verified directly against `data/testops.db`, not just via the test).
- AC3 HOLDS. The real store shows `demo-service-dup-20261122T090025/-090159/-090439` each with 18 cases, one finding each; the old v1 run still has its single case, untouched.
- AC4 HOLDS. Every action reads "Raise this with the team: this copy … to establish what <file:line> settles …; keep one." No I1–I4/KP shorthand, no condemn/delete vocabulary (regex-checked in tests and spot-checked in the store).
- AC5 HOLDS. Evidence resolves from the claim's coordinates; the asserting step's binding is first and the assertion snippet is marked at `assertion_line`.
- AC6 HOLDS. `case-demo-service-dup-20261120T153431` still exists with 18 v1 claims and one case; the page renders "recorded before provenance was captured" and the old statement. Nothing was backfilled; new runs wrote new snapshots (`demo-service-20261122-78153818{-r2,-r3}`), per the no-overwrite rule.
- AC7 HOLDS. Level-fitness runs on the demo-product corpus still total 94 claims: 90 distinct, 1 gap, 2 review, 1 unplaced (latest run `demo-product-levels-20261122T011316`, read from the store). Duplication is measured on its own corpus.
- AC8 HOLDS with a caveat. Suite green locally: 220 passed (Python 3.12.5 venv, env stripped per AGENTS.md). CI runs the two-leg interpreter matrix plus the render check; I could only execute one leg locally.

## Statement collisions

I built four adversarial corpora and drove the real `run_duplication` against each:

1. Same title, same assertion, two feature files → 1 claim (cheapest copy suppressed); no pair to collide.
2. Same title and identical steps twice in the SAME file → 1 claim; the intra-group dedup keeps one.
3. A scenario title identical to another scenario's step text → distinct statements; title and quoted text sit in different positions.
4. The strongest case: a cheap copy plus the SAME scenario (same title, same steps) duplicated in two same-level files, and again two same-title scenarios in one file over a cheap copy → 2 claims each time, distinct statements. The statements differ only by the claim's own `file:line`.

No collision found. The statement embeds the claim's own coordinates, so two claims can only share a statement if two scenarios occupy the same file and line, which the parser cannot produce. One residual: in case 4 the two claims share a `subject_ref` (`scenario:features/twin.feature#the sheet is served`) — statements are unique, but subject references are not. Nothing in AC2 forbids it, and the one-claim-per-finding page still disambiguates by coordinates, but it is worth a ticket if subject_ref ever becomes a decision key.

## The corpus

Not synthetic — copied. `tests/demo-service_fixtures.py` says so itself: the files were "read back from that run's stored snapshot (`reqnroll/demo-service@78153818`)". The tree is a verbatim subset of the Reqnroll DemoService sample's test projects (namespace `DemoService.Specs.*`, the sample's own fictional credentials `Trillian`/`139139` — a Hitchhiker's Guide joke, not a leak; no real names, keys or licence headers found; no licence file shipped in the fixture either).

Two honest observations, not blockers:

- Measuring the Product Owner's actual corpus is the right call and the fixture docstring is candid about provenance — but nothing in the repo records the upstream licence. DemoService is a public Reqnroll sample (MIT to the best of my knowledge; I could not verify offline). Add a provenance/licence note alongside the fixture so a future auditor doesn't have to trust my memory.
- The review prompt called it a "synthetic fixture corpus". It is not. If the Lead wrote that prompt believing the corpus was generated, the belief is wrong; if he knew, the wording is loose. Either way it should not survive into the merge description.

## Three sharpest concerns

1. The no-collision guarantee is structural, not tested at the boundary. The AC2 test only asserts distinctness on the happy corpus. My probes show the only near-miss is two same-title same-file scenarios, which differ by line — but if a future refactor ever dropped the coordinates from the statement, every same-title corpus would collide silently. A test with the twin-scenario fixture would lock the property, not the accident.
2. Duplicate `subject_ref` across claims in one run (probe 4). Harmless today; a landmine if anything keys on subject_ref.
3. The provenance check in the suite (`test_the_claim_coordinates_point_at_the_step_that_asserts`) only inspects the first claim. I verified two more by hand (API and WebUI Authentication at line 9, controller copy at line 8 — all correct), but a per-claim loop would be cheap and would have caught a grouping-order bug.

## Demo

**The problem.** The Product Owner opened the demo-service duplication case and saw 18 identical sentences naming the verdict ("asserts the same claim as 1 cheaper copy(ies) at controller; this copy drives api"), six "not recorded" fields each, and one case button that would silence all eighteen at once. No finding was presented.

**What changed.** Duplication claims are now v2. Each carries the coordinates of the step that asserts (the first `Then`), the commit, a span, an interaction label and a proposed action. The statement says which scenario, at which file:line, asserts what, and which cheaper copy already establishes it. One case per finding. Old runs render as before with the "recorded before provenance was captured" wording.

**How we know it works.** 220 tests pass with the environment stripped. In the store: three new runs, 18 cases each, one finding per case, 18 distinct statements per run. Sample from `demo-service-dup-20261122T090439`: "The scenario \"User logs in with valid credentials\" at DemoService.Specs.API/Features/Authentication.feature:9 calls the HTTP client to assert \"the login attempt should be successful\" and \"the user should be authenticated\", which DemoService.Specs.Controller/Features/Authentication.feature:8 already establishes in-process." I checked those coordinates against the fixture content at the claim's commit: line 9 is the `Then`, line 8 is the controller copy's `Then`. The old v1 case still renders. Level-fitness numbers unchanged at 94/90/1/1/2.

**What it does not solve.** The duplicated tests themselves — 18 findings still need 18 team decisions. Duplicate `subject_ref` is possible (see concerns). The corpus licence is undocumented. And "one case per claim" was verified on a duplicated scenario set; nothing yet asserts a case page cannot render two findings if a future grouping change reintroduces it beyond the count assertions.

**Where to look.** `testops/analysers/duplication.py` (v2.0.0, statement and action construction), `tests/test_duplication_v2.py` (AC1–AC6 pins), `tests/demo-service_fixtures.py` (corpus provenance), `data/testops.db` runs `demo-service-dup-20261122T*` and the untouched `demo-service-dup-20261120T153431`, `factory/reports/2026-11-22/TESTOPS-21-build.md`.
