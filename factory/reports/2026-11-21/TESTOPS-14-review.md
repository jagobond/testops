# TESTOPS-14 review — evidence depth (incl. addendum AC8–AC10)

Reviewed 2026-11-21 against `factory/testops-14-evidence-depth` @ 31c8001, diff `feature/f1..HEAD`.
Suite: 133 passed (.venv, 3.12), 129 passed + 4 skipped (builder venv311), both with
`env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1`.

## Verdict — PASS

The snapshot genuinely rebuilds its own claim set offline, the page now shows only what bears on a
claim, and the corpus verdicts are exactly the numbers the ticket promises.

## Criteria

- **AC1 HOLDS.** Snapshot `cotw-levels-20261121-a3f19853-r3` records 27 feature + 21 stepdef + 1
  build + 1 test artefacts for the test arm and 45 source artefacts for the product arm. I rebuilt
  it with `testops.rebuild.rebuild` in a process where `socket.socket`, `socket.create_connection`,
  `socket.getaddrinfo` and `ssl.wrap_socket` were all replaced with raisers — any network call
  would have crashed the run. It did not: 94 claims rebuilt from `snapshot → artefacts → blobs`
  alone. What this does not prove: DNS-level or proxy egress I did not patch (e.g. a raw
  `socket.socketpair` path), and it does not exercise a rebuild after the blob store is damaged
  beyond the one missing-blob refusal test covers.
- **AC2 HOLDS.** All 94 post-fix claims carry `assertion_path` + `assertion_commit`; the coordinate
  match resolves against the claim's own snapshot only (`queries.py:255` exact sha+path, no LIKE).
- **AC3 HOLDS (weakly, on real data).** Every one of the 94 claims carries non-empty support; the
  "explicit empty when nothing bound" branch is covered by
  `tests/test_evidence_depth.py:210` but never exercised by the corpus. That is fine, but the
  corpus cannot witness it.
- **AC4 HOLDS.** The case page for `case-cotw-levels-20261121T230858-01` renders a link + a
  one-line "shows" sentence per observation; the "no observations at these coordinates" fallback is
  absent from the page (checked the rendered HTML).
- **AC5 HOLDS.** Rebuilt claims are equal to the originals — subject_ref, statement, verdict and
  the support observation ids themselves — 94/94, zero mismatches. Equality on ids, not just
  similarity. `test_evidence_depth.py:410` also pins rebuild-twice determinism.
- **AC6 HOLDS.** Runs `230627` and `230858` both record 94 claims, 90 distinct, 1 unplaced, 1 gap,
  2 review; and run 230858's claims are identical in subject, verdict and statement to 230627's.
  Note: run 215534 (first build) recorded 43/48/1/2 — the verdict distribution moved *during* the
  ticket, between builds, before the reviewed state. See concerns.
- **AC7 HOLDS.** Both interpreters green; determinism verified above.
- **AC8 HOLDS.** Cold attack below: in three different feature files, every rendered row is either
  the asserting step's binding, its containing scenario, or another bound step of that same
  scenario. No row from another scenario, and no cross-snapshot support rows (checked all 94:
  zero foreign).
- **AC9 HOLDS.** In every sampled claim the first row is the asserting binding, flagged `asserted`,
  and the page prefixes it "the step that is asserted:" (`web/app.py:313`).
- **AC10 HOLDS.** Evidence sizes vary 3/4/5/6/10 rows purely with scenario length (histogram
  measured over all 94 claims) — a consequence of relevance, not a quota.

## Your own sample

Three claims, three different feature files, rendered cold via `claim_read`:

1. `features/approval_queue.feature:17` "there is one sheet per entity" (distinct). Rows: the Then
   binding for that exact text (asserted, line 123), the scenario containing line 17 (starts at 15),
   then three bindings for the other steps of that same 4-step scenario. Every row bears on the
   claim. RELEVANT.
2. `features/canon_search_states.feature:19` "the page reports that nothing has been admitted yet"
   (distinct). Rows: asserting Then binding (line 108), containing scenario (line 16, 12 steps),
   then eight bindings — all within lines 56–172, all steps of that one long scenario (12 steps,
   9 bound). No neighbour scenario leaked. RELEVANT, though nine rows is dense reading; that is the
   honest shape of a 12-step scenario, not noise.
3. `features/review_panel.feature:19` "every sheet in the index is listed" (distinct). Rows:
   asserting binding (line 47), containing scenario (line 17), two sibling bindings (lines 44, 61).
   All from the same 3-step scenario. RELEVANT.

## Three sharpest concerns

1. **The verdict distribution moved mid-ticket.** Run 215534 (the first build of this ticket) gives
   43 distinct / 48 unplaced; the reviewed build gives 90 / 1. AC6 is written as "recording evidence
   must not change a verdict", and on the final build that holds — but the shift between builds
   means the support wiring (or a bug it fixed) changed how claims are placed. The ticket should
   record why, or a future reader will assume evidence recording silently re-judged the corpus.
2. **AC3's empty branch is unexercised by real data.** All 94 corpus claims bound their steps, so
   the "explicit empty" honesty the ticket promises is proven only by the unit test. If the
   collector ever stops matching bindings on a whole corpus, the page would flip 94 claims to an
   empty-support rendering and nothing in the corpus would catch it.
3. **Pre-fix runs render honest-but-thin pages, and the wording can mislead slightly.** A claim from
   run 215534 gets evidence `[]` and the page says "recorded no observations at these coordinates" —
   when the truth is the snapshot predates observation recording entirely. `None` (v1, "was not
   recorded") and `[]` ("nothing bears on it") are distinguished in the model, but a v2 claim on a
   pre-observations snapshot lands in the `[]` bucket with the wrong shade of meaning. Cosmetic;
   the fix's snapshot-scoping does mean no cross-run evidence can appear — I found zero support
   rows from a foreign snapshot across all 94 claims, and the base snapshot holds no feature
   artefacts an old claim could borrow. Acceptable as-is; the distinction would be a one-line
   wording ticket, not a defect.

## Demo

**The problem.** A levels run recorded only the product arm, so a run could not explain itself from
its own snapshot (TESTOPS-10 had to borrow a second snapshot and refuse on disagreement), and the
case page's evidence section said "no observations at these coordinates" for every real specimen —
then, after the first fix, showed six unrelated scenarios that merely shared a file.

**What changed.** `pipeline.run_level_fitness` records both arms as artefacts of one snapshot with
`meta.arms` and `meta.sources_missing`, writes gherkin and stepbinding observation rows, and hands
the analyser a support index so each claim names the observation ids it rests on. `rebuild.py`
reconstructs the whole claim set from one snapshot id, refusing snapshots that omit arms, missing
sources, or blobs. `queries.evidence_for_claim` renders only what bears on the claim: the asserting
binding first (flagged as such), the containing scenario, and the claim's recorded support — scoped
to the claim's own snapshot, matched by exact commit + path, never by file.

**How we know it works.** 133/129(+4 skip) tests green on both interpreters; an in-process
network-kill rebuild of snapshot `…-r3` reproduced all 94 claims with identical subject, statement,
verdict and support ids; AC6 numbers 94/90/1/1/2 present on both final runs with identical claims;
cold relevance attack on three files found no row that does not bear on its claim; the rendered
case page shows "the step that is asserted:" on the first row and no "no observations" fallback.

**What it does not solve.** The mid-ticket verdict shift is undocumented; the empty-support branch
has no corpus witness; pre-fix snapshots still render with slightly misworded empties; and rebuild
integrity assumes the blob store is intact (a corrupt-but-present blob would be believed).

**Where to look.** `testops/rebuild.py` (load/rebuild and its refusals),
`testops/pipeline.py:203` (both arms + observations + support index),
`testops/queries.py:160` (evidence relevance), `testops/web/app.py:287` (page rendering),
`tests/test_evidence_depth.py` (all ACs, incl. AC8–10 at lines 355/373/391).


---

## Lead annotation (correcting concern 1)

Concern 1 compares two runs from **different tickets** and reads the difference as movement inside
this one. Verified against the store:

| run | written by | distinct | unplaced | gap | review |
|---|---|---|---|---|---|
| `cotw-levels-20261121T215534` | TESTOPS-4 build, 21:55 | 43 | 48 | 1 | 2 |
| `cotw-levels-20261121T230858` | this ticket's build, 23:08 | 90 | 1 | 1 | 2 |

The 43/48 run predates TESTOPS-10 (coverage vocabulary) and TESTOPS-11 (restraint) — those two tickets
are what moved 48 unplaced to 1, and TESTOPS-11's review records that movement explicitly. AC6 compares
against the TESTOPS-11 state (90/1/1/2), which this build reproduces exactly. No verdict moved inside
TESTOPS-14. The reviewer's instinct — that a 47-claim shift needs explaining — was right; the
explanation is the ticket sequence, not this ticket.

Concern 3 stands and is filed: a v2 claim on a snapshot written before observations existed renders
"recorded no observations at these coordinates" when the truth is "this run never recorded any". `None`
and `[]` are distinguished in the model but collapse in the sentence.
