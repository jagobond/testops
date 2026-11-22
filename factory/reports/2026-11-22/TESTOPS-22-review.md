# TESTOPS-22 review — a quiet run is not a resolved case

## Verdict

PASS — every count on the quiet page traces to a stored row, "Resolved" is reachable only from a
`case_state` row, the recorded-registry rule holds under adversarial probing, and the trap case
renders both facts without confusing them.

## Criteria

| AC | Verdict | Evidence |
|----|---------|----------|
| AC1 | HOLDS | Quiet page heading is "No findings in this run" plus one sentence of what was analysed (`case_page` → `quiet_run_block`, `analysed_sentence`). `display_state` no longer maps (0 findings, open) to "Resolved". |
| AC2 | HOLDS | "Resolved" is rendered only by `decision_block`, reached only when `latest_decision` returns a `case_state` row. Real store page for `case-cotw-levels-20261121T173046` reads "Resolved by harry 15 hours ago. The note recorded with that decision: "smoke test"." |
| AC3 | HOLDS | Features, scenarios, exclusion patterns and the analyser's claim count all derive from the case's own snapshot rows (see The counts). |
| AC4 | HOLDS | `run_analysis` reads `snapshot.meta` joined through the run row (`queries.py:350`); the never touches `sources.registry()`. Adversarially proven below. |
| AC5 | HOLDS | Freshness line ("Analysed 37 hours ago at cotw-bdd@a3f19853, cotw-continuity@b901ea4d") and "Duplication" analyser name present on the live quiet page. |
| AC6 | HOLDS | `test_a_quiet_run_and_a_resolved_case_never_share_wording` asserts heading, badge and body all differ between the two pages, both built from stored rows in one store. |
| AC7 | HOLDS | Diff touches `queries.py`, `web/app.py` and tests only — no analyser code. Latest level-fitness run in the store: 94 claims → distinct 90, gap 1, review 2, unplaced 1. |
| AC8 | WEAK | Suite green on the prescribed `.venv` (3.12.5): 228 passed. A second interpreter is not available as a venv on this branch, so the "both interpreters" half is the builder's claim, not independently verified. |

## The counts

Live quiet page: `case-cotw-dup-20261120T194032`. Each claim traced to the store:

- "6 feature files" — `run_analysis` counts 6 of 27 feature artefacts as active under the stored
  `CotwBdd.csproj` patterns (snapshot `cotw-20261120-a3f19853`).
- "41 scenarios" — 41 `observation` rows with `key LIKE 'scenario:%'` recorded against those 6
  active artefacts (207 observations exist overall; dormant files' 166 are correctly excluded).
- "17 exclusion patterns read from CotwBdd.csproj" — 17 patterns parsed from the build artefact's
  stored blob (`.lead-draft/**/*.feature`, 14 named features, `.lead-draft/*`, `*/bin/*`, `*/obj/*`).
- "21 of 27 stored feature files outside the build" — 27 feature artefacts in the snapshot, 21
  inactive. Matches the case summary's `dormant_features: 21`.
- "recorded no claim about any of them" — 0 claim rows for run `cotw-dup-20261120T194032`.
- "What this run could not consult: This run recorded no source registry" — snapshot meta is `{}`,
  so `registry_recorded` is False. Correct: that snapshot predates registry recording.

## The trap

Zero findings plus a resolved `case_state` row, rendered for real (reviewer build, same code):

- Badge: **Resolved** (the decision wins the badge — it is a person's act).
- Heading: **No findings in this run** — the run is still described as a run.
- Both blocks appear: the analysed sentence, the registry blind-spot section ("Jira — blocked by
  Quilter policy… They were never consulted…"), then "Resolved by harry just now. The note recorded
  with that decision: "looked and agreed". This is a decision about the findings in this case; it
  did not change what the run analysed."

The two states do not share wording: the quiet-only heading never appears on a page without a
decision, and "Resolved" never appears on a page without a `case_state` row. The test
`test_a_quiet_run_that_was_resolved_shows_both_facts_without_confusing_them` pins exactly this.

## Three sharpest concerns

1. On the trap page the badge says "Resolved" while the first heading says "No findings in this
   run". Both are correct, but a reader glancing at the badge alone gets a decision word with no
   run facts; the decision-sentence boilerplate "a decision about the findings in this case" is
   slightly off when the case holds no findings at all.
2. Feature/scenario/pattern counts are recomputed from the snapshot's stored artefacts at render
   time, not recorded at run time. Correct today (the snapshot is frozen), but the page's honesty
   depends on the blob store staying append-only — a pruned blob degrades to "cannot be counted",
   which is handled, yet nothing records that the run itself saw the same numbers.
3. AC8's "both interpreters" is not reproducible here: only the 3.12 `.venv` exists on this branch,
   so the second-interpreter leg of the claim rests on the builder's environment.

## Demo

- The problem: a run that raised nothing read "Resolved — the analysis raised nothing to act on",
  implying a person had decided something about a claim nobody had made, with no record of what
  was analysed or what the run could not see.
- What changed: `display_state` no longer borrows the decision word; a quiet case gets its own
  badge ("No findings") and a rendered run description (features, scenarios, exclusions from the
  stored project file, analyser coverage) plus a "What this run could not consult" section read
  from the snapshot's recorded registry. "Resolved" is now produced solely by `decision_block`
  from a `case_state` row, naming actor, time and note.
- How we know it works: 228 tests pass, including 9 new `test_quiet_run.py` tests that pin the
  counts, the no-registry case (with `sources.registry` monkeypatched to explode), the
  missing-blob case, and the two-state wording split. Reviewer re-derivation: every number on the
  live quiet page reproduced from `data/testops.db` rows; adversarial AC4 probe (config has a live
  registry, snapshot has none) rendered "This run recorded no source registry… Nothing here says
  the sources it did not have were clean" with no source named from today's config; trap probe
  rendered both facts with distinct wording.
- What it does not solve: the per-render recomputation of analysis counts (see concern 2), the
  badge/heading tension on a resolved-but-quiet case (concern 1), and any registry-less snapshot
  still cannot say what it was blind to — the page now says so honestly, but the blindness itself
  is unfixable after the fact.
- Where to look: `testops/queries.py:437` (`latest_decision`, `run_analysis`),
  `testops/web/app.py:551` (`analysed_sentence`, `quiet_run_block`, `decision_block`),
  `tests/test_quiet_run.py`, live pages `case-cotw-dup-20261120T194032` (quiet) and
  `case-cotw-levels-20261121T173046` (resolved, names harry / 15 hours ago / "smoke test").
