# TESTOPS-55 — review

Reviewer pass, 2026-11-24. Store checked against a copy (`data/` copied to scratch; the live store
and port 8791 were never touched). All renders below were produced by the pinned interpreter from
the copy, on this branch unless marked.

## Verdict

**PASS.** Both promises hold against the store, not against the build's table: the front page's
three numbers are the store's own counts at render time, a run-named project is counted, and every
kind the collector declares is named on every run page with its zero stated. The pinned sentence is
byte-identical to origin/main's. The only suite movement is the expected P05 pair. Three concerns
are recorded, none of which blocks the merge.

## The front-page totals, checked against the store

The copy of the live store renders:

> The store holds **4 projects**, **47 runs** and **208 cases**. A project is a set of repositories
> this tool is set up to analyse; a run is one analysis of a project at a fixed commit; a case is
> one finding waiting for a decision.

Checked three ways, all agreeing: `queries.store_totals(conn)` → 4/47/208; the same UNION/COUNT SQL
typed directly against the copy → 4/47/208; the rendered sentence → 4/47/208. The store's project
set is `{cotw, reqoverflow, restfulbooker, testops}`; the front page's headings are
`{restfulbooker, reqoverflow, cotw}` — a subset, so no heading can be a project the totals do not
count (headings come from `run.project`, which the totals' UNION includes).

Then a deliberately odd copy: a run inserted naming project `ghost` with no `project` row, and a
`project` row `lonely` with no runs. The store's own count moved to 6/48/208 and the page rendered
exactly "The store holds **6 projects**, **48 runs** and **208 cases**." The run-named project **is
counted** — the build's claim verified — and no new heading appeared for either (`ghost` has no
cases, `lonely` has no runs), so the totals can lead the headings without contradicting them.

## The zeros

`queries.known_file_kinds()` reads `config.FILE_KINDS` at call time
(`testops/queries.py:577`), and `read_counts` builds every repository's sentence from
`list(known) + sorted(set(counted) - set(known))` (`testops/queries.py:627`). So:

- The restfulbooker run page states all six declared kinds for both repositories, including the
  four real zeroes — verified against the copy, and independently against the artefact rows.
- **If `config.FILE_KINDS` gains a kind tomorrow, the sentence includes it with no code change.**
  The kinds are read from the tuple on every render; nothing about the page names them literally.
- What *would* break: only the suffix derivation. `_file_suffix` takes the text after the **last
  dot**, so a declared kind with a compound suffix (`.feature.cs`) would render its zero honestly
  while its actual reads were silently counted under `.cs` — a page stating a false 0. Every kind
  in the tuple today is single-dot, so nothing is wrong now; it is a latent trap, not a defect.
- An undeclared suffix that somehow reached the artefacts (the collector's `kind_for` gate makes
  this unreachable today) is appended after the declared kinds rather than dropped — it cannot
  vanish silently either.
- A snapshot that recorded no `reads` renders no section at all — silence, not invented zeroes
  (pinned by `test_a_snapshot_that_recorded_no_reads_renders_no_read_counts`).

## Read versus skipped

From the restfulbooker run page (`restfulbooker-levels-20261123T132456`), as it renders:

- *What this run read*: "Files this run read, per repository and per kind. A 0 is a kind this
  reader handles and that repository holds none of. Files it could not read are counted in their
  own section further down the page." — "From the product repository
  (mwinteringham/restful-booker-platform) it read 23 .ts files, 4 .js files, 0 .csproj files,
  0 .feature files, 0 .py files, and 0 .cs files." / "From the test repository
  (m-pujic-levi9-com/cypress-cucumber-e2e-tests) it read 14 .js files, 6 .feature files,
  1 .ts file, 0 .csproj files, 0 .py files, and 0 .cs files."
- *Files this run could not read*: "The repositories hold 341 files in 21 kinds that this run did
  not fetch. Nothing in this run says what they contain, so nothing here counts them as consulted."
  — "**142 .java** in the product repository — unsupported kind."

A reader cannot confuse them: the sections have different headings, the read section says "it read
N", the skip section says "did not fetch", and the page's own lead-in sentence tells the reader the
two are different facts. The read counts were re-derived directly from the copy's artefact rows and
match the page; the 142 comes from the snapshot's recorded `skipped` entry, as before.

## The pinned CotW sentence

Rendered through the same derivation path the pages use (`sources.assessment_for` on the stored
snapshot meta of `cotw-levels-20261122T204947`), on this branch and on a detached origin/main
worktree over the same store copy:

    'Assessed: code and test code were consulted and returned 95 items.'

Byte-identical on both. One finding the brief should know about: this sentence **does not render on
any CotW page in the live store** — the run has findings, so its run page takes the findings path,
which renders no assessment sentence, and its case pages carry no `Assessed:` line either. The pin
is real (the sentence builder is untouched and `sources.Assessment.sentence()` is byte-stable), but
"diff it against origin/main's rendering" can only be honoured at the builder level, and was. Also,
"zero skips" is true only in the lost-readings sense: the run's record shows it skipped 94 product
and 12 test files as unsupported kinds (recorded in the skip section), and the sentence carries no
unreadable-files parenthetical. Both facts are correct as rendered; the brief's wording was looser.

## Derivation

- Front totals: one UNION/COUNT over `project.slug ∪ run.project`, plus two plain counts, executed
  at render time. Not stored, not cached, not written anywhere a second copy could go stale.
- Read counts: counted from the run's snapshot artefact rows, attributed to repositories by the
  snapshot's own `reads` commit record. Skipped counts remain where TESTOPS-41 put them, in the
  snapshot's `reads` record. Nothing is duplicated: there is no count column, no cache, no second
  write. A stale count could arise only from the store itself drifting — artefacts whose commit the
  `reads` record does not name are dropped from the read counts, and pruned artefacts would lower
  them — and retention deletes run, snapshot and cases together, so the window is bounded. Within
  one snapshot, the page cannot disagree with the store.

## Contract suite

`pytest -q` on this branch, stripped env: **730 passed, 3 skipped, 2 failed** — the failures are
exactly `test_P05_case_links_back_to_its_run` and `test_P05_config_page_is_reachable_from_the_front_page`
(TESTOPS-54, unmerged here; the build's account matches what I ran, failure text identical to the
branch's). **P07 and P10 pass** (run explicitly). The new file's 7 tests pass, the
TESTOPS-43 sentence pins pass, and the analyser pins hold: CotW 94 claims / 90 scenario /
1 / 1 / 2 (test_action_prose, test_case_scan) and ReqOverflow 17 claims / 17 cases / 17 findings
(test_action_prose, test_duplication_v2) — all inside the green 730. No other test moved.

## The wording

Read cold, the totals line works: three nouns, each with its count, then one sentence of
definitions a newcomer can act on. The definitions earn their place — "a case is one finding
waiting for a decision" is the one a newcomer actually needs and could not guess. Two small nits,
not blockers: a case can carry several findings, so the definition slightly understates it; and a
reader counting headings sees three under a totals line that says four (the `testops` project has
no cases and no heading), which is correct but unexplained. The read-counts lead-in ("A 0 is a kind
this reader handles and that repository holds none of") is the best sentence in the change: it
turns the zero from a number into a fact without a legend.

## Three sharpest concerns

1. **The pinned sentence is invisible on the pages it is pinned about.** No CotW run or case page
   in the live store renders "Assessed: … 95 items" — the findings path of `run_response` renders
   no assessment sentence at all. The pin survives at the builder (verified against origin/main),
   but a reader of the CotW pages cannot see the sentence the factory believes is pinned. Worth a
   ticket to decide whether that is intended.
2. **`_file_suffix` is a latent false-zero trap.** A declared kind with a compound suffix would be
   stated as 0 while its reads were counted under the last-dot suffix. Guard it when
   `FILE_KINDS` next grows (one assert that every declared suffix is last-dot-unique would do).
3. **The totals can lead the headings.** Projects with no cases are counted in the headline but
   render no heading (and a run-named project with no cases renders nothing at all). Correct, but
   the page offers the reader no sentence reconciling "4 projects" with three headings — the same
   silence-about-a-difference this ticket exists to remove, one level up.
