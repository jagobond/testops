# TESTOPS-5 review — source capability registry

## Verdict — PASS

The two states that must never collapse are held apart end to end (registry, store, read model, page), an available source that fails stops the run with nothing written, and the corpus did not move; the three weak spots below are seams for the next ticket, not holes in the product's current paths.

## Criteria

- **AC1 HOLDS.** `testops/sources.py` declares identity + capability set + state per source; the deployment lives in `registry()`. Adding a source is registry configuration only — the fake `confluence` source (tests/test_source_registry.py:266) and my own fake `gitlab-tests` both flow through `pipeline.run_level_fitness(..., registry=...)` with no analyser edit.
- **AC2 HOLDS.** Three states with mandatory reasons (`SourceState.__post_init__` refuses a stateless reason and a blocked source with no blocker, sources.py:115-128). State comes from configuration or from `SourceKind.probed`; a raising probe propagates (verified). No product code path converts an exception into `absent`.
- **AC3 HOLDS.** Both run paths write `sources` (full registry record) and `analysers` (needs/consults) into snapshot meta; `rebuild.load` refuses a snapshot holding only half of it (rebuild.py:95-99), and refuses a snapshot with no `sources_missing` at all.
- **AC4 HOLDS.** `sources_missing` is `Registry.missing(...)`, never a hard-coded list. My own registry with a blocked fake source produced claim rows `["gitlab-tests"]` and snapshot meta `missing: ["gitlab-tests"]` through the real pipeline.
- **AC5 HOLDS.** See "The crux".
- **AC6 HOLDS.** See "The crux" (2a/2a').
- **AC7 HOLDS.** `claim_read`/`finding_rows` attach `sources` (the recorded registry, not a re-probe), `assessment` and `source_notes`; `section_unchecked` names the state, the reason and the blocker. Corrupt snapshot meta raises rather than reading as "nothing recorded" (queries.py `_snapshot_meta`).
- **AC8 HOLDS.** The declaration record contains no credential field; the only credential-like strings in the diff are inside the test that asserts their absence; a run given a secret token stores no trace of it (tests/test_source_registry.py:515).
- **AC9 HOLDS.** Latest cotw rebuild runs: 94 claims, 90 distinct, 1 unplaced, 1 gap, 2 review at analyser 0.9.0; the 0.8.1 rebuild run also totals 94 with 90/1/1/2. Per-subject comparison of run `cotw-levels-20261121T230627` (0.8.1) against `cotw-levels-20261122T001550` (0.9.0): zero differences in verdict or statement. The diff adds recording fields only; version bumps (0.8.1→0.9.0, duplication 1.0.0→1.1.0) changed no judgement code.
- **AC10 WEAK (HOLDS via CI).** Suite green here: 162 passed, 13s, on the repo venv (Python 3.12). I cannot run a second interpreter locally; `.github/workflows/ci.yml` enforces the 3.11/3.12 matrix, which is the mechanism the criterion names.

## The crux

**Two stores I built myself (not the builder's fixtures), both through the product's own writers/readers:**

1. **Blocked.** Real `run_level_fitness` with my registry: GitHub available (observed 7), `gitlab-tests` **blocked** ("the GitLab group is inside the banned network zone", blocked by "the security office"). Read back: assessment state `not_assessable`; sentence "Cannot assess this claim: nobody could look at code and test code. The GitLab test repo is blocked by the security office: …"; page shows the Cannot-assess badge, never the words "real zero"; every claim row carries `["gitlab-tests"]`.
2. **Empty.** My stored snapshot/run/claim with `gitlab-tests` **available, observed 0**: assessment state `zero`; sentence "…consulted and returned nothing. That is a real zero — there is nothing there, not that nobody looked."; page says "real zero" and never "Cannot assess".

Verdicts differ, sentences differ, page copy differs — both directions (blocked ≠ zero, and zero is never not_assessable).

**Collapse attempts:**

- **A source that raises:** collect raises → `SourceFailed` with the collector label and the underlying error; the store after the run has 0 snapshots, 0 claims, 0 runs; a subprocess run exits **1** with `SourceFailed` and the failing path in stderr. Nothing degrades to absent.
- **A probe that swallows an exception:** accepted — my probe caught its own failure and returned `ABSENT, reason="tracker did not answer the probe"`, and the registry cannot tell that from an honest probe. It does not collapse the verdicts (the sentence still says "absent", not "nothing"), but the honesty of a probe is unauditable by the API. A probe that *raises* propagates.
- **A claim whose `sources_missing` is empty because the registry was never consulted:** a claim written through `db.add_claim` with the analyser's default `[]` (no registry ever asked), on a snapshot with empty meta, renders **"Every source needed for this claim was available."** That is the one path I found where never-looking reads as a clean bill — it requires bypassing the pipeline (every product call site derives the list from the registry), so it is a seam, not a live path.

**Could I make them collapse? No, on any product path.** The near-miss is the analyser default above.

## Three sharpest concerns

1. **Wrong safe default at the analyser seam.** `level_fitness.analyse`/`duplication.analyse` turn an omitted `sources_missing` into an explicit `[]` — the page renders "Every source needed for this claim was available" for a registry that was never consulted (proven). One future caller forgetting the kwarg writes a clean bill of health. Defaulting to `None` ("not recorded", which the page already handles honestly) would make the failure mode visible instead of clean.
2. **Probe honesty is trusted, not checked.** `SourceKind.probed` type-checks the return and propagates raises, but a probe that swallows its own exception and declares `absent` is indistinguishable from a real absence. A later ticket could require probes to log or countersign why they looked and what happened; today the guarantee lives only in the probe author's discipline.
3. **The `zero` verdict is unreachable from a live run.** An available source that returns no matching files yields no claims at all, so "we looked and there is nothing" is only ever exercised by directly written stores. The wording is pinned by tests, but no pipeline path has ever produced it — the first real zero will arrive untested against the full page path.

## Demo

**The problem.** Before TESTOPS-5, "which sources were missing" was a hard-coded list derived from config, a source's absence was indistinguishable from an empty result, and an analyser that failed mid-collect could leave a snapshot implying a clean read.

**What changed.** A declared registry (identity, capabilities, state with reason and blocker), consulted by the pipeline through `Registry.use`; the registry and the analyser's needs recorded in every snapshot; `sources_missing` derived, never assumed; the case page names the state, reason and blocker from the recorded registry; a failure at use raises `SourceFailed` and stops the run before anything is written.

**How we know it works.** Suite: 162 passed. My own blocked-vs-empty stores produced different verdicts, sentences and page copy in both directions. A raising available source: exit code 1, zero rows in the store, source still declared available. Corpus unchanged: 94/90/1/1/2 at 0.9.0, identical verdicts and statements to the 0.8.1 rebuild.

**What it does not solve.** The GitHub MCP transport (explicitly out of scope); probe honesty; the analyser default seam; no live path exercises a real zero.

**Where to look.** `testops/sources.py` (registry, states, `use`), `testops/pipeline.py` `run_level_fitness`/`run_duplication` (recording + collection gate), `testops/queries.py` `_attach_sources`, `testops/web/app.py` `section_unchecked`, `tests/test_source_registry.py`. Reviewer attack script: reviewer-profile scratch `attack_testops5_v2.py` (output captured in this report).
