# TESTOPS-55 — build report

Ticket: `factory/tickets/TESTOPS-55.md` — Counts that say what they count.
Branch: `factory/testops-55-counts`, based on `origin/main` at 7182c4d (fast-forwarded onto
main first, so the suite includes TESTOPS-53's self-owned server and store: the contract suite
never touches `data/` or port 8791).

## What changed

Two page faults, both read from the store at render time.

**Front page (`testops/web/app.py::totals_line`, `testops/queries.py::store_totals`).**
The home screen now opens with one labelled line: "The store holds 4 projects, 47 runs and 208
cases. A project is a set of repositories this tool is set up to analyse; a run is one analysis of
a project at a fixed commit; a case is one finding waiting for a decision." The three numbers are
plain integers read from the store on every render (`project ∪ run.project`, `run`, `case_`).
A project the store knows only because a run names it is counted, so a heading on the page can
never be a project the totals do not count.

**Run page (`testops/web/app.py::read_counts_block`, `testops/queries.py::read_counts`).**
A new section, *What this run read*, gives per-repository, per-kind read counts including
explicit zeroes, e.g. for the pinned restfulbooker run:

    From the product repository (mwinteringham/restful-booker-platform) it read 23 .ts files,
    4 .js files, 0 .csproj files, 0 .feature files, 0 .py files, and 0 .cs files.
    From the test repository (m-pujic-levi9-com/cypress-cucumber-e2e-tests) it read 14 .js files,
    6 .feature files, 1 .ts file, 0 .csproj files, 0 .py files, and 0 .cs files.

The kinds listed are every kind the collector reads (`config.FILE_KINDS`), so a zero is a fact
about the repository rather than a silence. The counts are **derived, not stored twice**: every
file a run fetched is an `artefact` row of its snapshot, and the snapshot's recorded `reads` entry
says which commit belongs to which repository. A snapshot that recorded no reads renders no
section — silence, not invented zeroes.

Read and skipped stay visibly distinct: read counts live under *What this run read* and say
"it read N .cs files"; the existing *Files this run could not read* section is untouched, keeps
its "did not fetch" summary and its per-kind `<strong>142 .java</strong> … unsupported kind` lines,
and the read section never borrows its words.

`pipeline.py`, the collectors, both analysers and `sources.Assessment.sentence()` are untouched,
so the pinned COTW sentence ("Assessed: code and test code were consulted and returned N items")
and the analyser counts are unchanged by construction and re-verified by the suite
(`tests/test_partial_reads_visible.py::test_the_stored_runs_still_render_the_sentence_they_rendered`,
`test_action_prose`/`test_case_scan` 94/90/1/1/2, ReqOverflow 17/17 — all pass).

## Tests added (`tests/test_counts_that_say_what_they_count.py`, 7)

- AC1: the front page's three stated counts equal counts read from the store in the test, not
  constants; a second test adds a project, a run and a case and asserts all three numbers move
  with the store.
- AC2/AC4: a real pipeline run (in-memory repositories, throwaway store) whose product repository
  holds only a `.py` file — the page states `1 .py file` and `0 .cs files`, `0 .js files`,
  `0 .feature files`; every kind in `config.FILE_KINDS` is stated for every repository.
- AC4 (partial): one `.cs` read and two `.cs` refused at the size cap — the page states both
  `1 .cs file` (read section) and `2 .cs … size cap` (skipped section).
- AC3: the skipped section uses none of the read section's words, and the skipped-by-kind
  summary keeps its "did not fetch" meaning.
- An older snapshot with no recorded reads renders no read section.

## Golden

One golden changed, for the intended text only — `tests/fixtures/projects_services/index.html`,
which gains the totals paragraph and nothing else:

```diff
@@ -84,2 +84,2 @@
-<body><main><h1>TestOps</h1><p class="meta"><a href="/runs">all runs</a></p><p class="fresh">Last analysed <strong>a fixed time ago</strong> at cotw-bdd@a3f19853 <span class="quiet">(Level fitness)</span></p><h2 class="section">cotw</h2>…
+<body><main><h1>TestOps</h1><p class="meta"><a href="/runs">all runs</a></p><p class="fresh">Last analysed <strong>a fixed time ago</strong> at cotw-bdd@a3f19853 <span class="quiet">(Level fitness)</span></p><p class="totals">The store holds <strong>4 projects</strong>, <strong>12 runs</strong> and <strong>12 cases</strong>. A project is a set of repositories this tool is set up to analyse; a run is one analysis of a project at a fixed commit; a case is one finding waiting for a decision.</p><h2 class="section">cotw</h2>…
```

Rendered from the same migrated `before_v3.db` with the same frozen clock the test uses. No run
page golden exists in that fixture; `runs.html` and the twelve case pages are byte-identical.

## Verification

    env -u PYTHONPATH -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
      C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe -m pytest -q

    730 passed, 3 skipped, 2 failed in 151.81s

The two failures are `tests/contracts/test_page_contracts.py::test_P05_case_links_back_to_its_run`
and `::test_P05_config_page_is_reachable_from_the_front_page`. Both fail identically at the base
commit 7182c4d without this branch (verified in a detached worktree), and both belong to
TESTOPS-54 — which this ticket depends on and which is still on its own unmerged branch
(`factory/testops-54-navigation`); nothing in this change touches them. **P07 and P10 pass**, as
does the whole contract suite's self-owned server harness.

Regression baseline: at 7182c4d the same two P05 tests fail and P07/P10 also fail; on this branch
P05 is unchanged and P07/P10 pass. No other test changed state.
