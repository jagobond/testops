# TESTOPS-43 build — partial is not whole

2026-11-22, branch `factory/testops-43-partial-reads`, worktree `C:/Users/Chester/Projects/testops-t43`
(HEAD `9f31ef3` when started; the main checkout was not touched).

Suite, from the worktree with `PYTHONPATH`/`PYTHONHOME`/`VIRTUAL_ENV` stripped and
`PYTHONNOUSERSITE=1`:

> `env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1 .venv/Scripts/python.exe -m pytest -q`
> **457 passed** in 75s

(The worktree has no `.venv`; the interpreter used is the main checkout's
`C:/Users/Chester/Projects/testops/.venv/Scripts/python.exe` with `PYTHONPATH` unset, as the
ticket allows.) Two environment notes, both verified, neither caused by this change:

1. **A copy of the store, not the store.** `data/` is absent in a fresh worktree, so every corpus
   test skips. I made a byte copy of `C:/Users/Chester/Projects/testops/data/testops.db` and
   `data/blobs` into the worktree's gitignored `data/` and read it read-only; the main checkout's
   store was only ever opened with `?mode=ro`. Without the copy the same suite is **445 passed,
   11 skipped** plus the one failure below.
2. **One pre-existing failure in this checkout.** `test_projects_services.py::test_every_case_page
   _and_the_indexes_are_byte_identical_after_the_migration` fails at index 59 with `b'\n' !=
   b'\r'`: the committed `tests/fixtures/projects_services/*.html` were checked out with CRLF
   while the app renders LF. It fails identically on a clean detached worktree at `9f31ef3` with
   no changes of mine; converting only the fixture `.html` files to LF locally makes it pass, and
   the conversion shows as modified in git, so I reverted it and did not commit it. With that
   local conversion the full suite is **457 passed, 0 failed**.

## What changed, criterion by criterion

| AC | What it now does | Where | Proof |
|----|------------------|-------|-------|
| AC1 | When a capability returned **nothing**, the sentence names each capability separately instead of adding them up: *"Assessed: code returned 0 items; test code returned 2 items."* A 1-and-1 still reads as one aggregate sentence, because there the total states the same fact. | `sources.py` (`Assessment.sentence`, `_result_clause`) | `test_a_capability_that_returned_nothing_is_named_with_its_zero`, `test_two_one_and_one_is_not_told_as_two_and_zero` |
| AC2 | A capability that read some files and lost others says so in one parenthetical: *"… returned 60 items (3 .cs files and 1 other kind unreadable)."* The count of what it read and the kinds it could not are both in the sentence. | `sources.py` (`_lost_clause`), `pipeline.py` (`_readings` records `lost`) | `test_a_partially_read_capability_says_what_it_read_and_what_it_could_not`, `test_a_lost_file_makes_the_sentence_partial_and_the_page_still_lists_it` (full pipeline run) |
| AC3 | **Every** skip is on the run page, whatever the verdict: one line with the file total and kind count, one row per kind with its count and reason, and the names behind a `<details>` disclosure. Files passed over by a rule (generated/vendored) get one quiet count instead of a list, so nothing recorded is silent. | `web/app.py` (`could_not_read_lines`) | `test_a_run_that_skips_five_hundred_sql_files_says_so_though_its_code_read_fine` |
| AC4 | CotW (*"Assessed: code and test code were consulted and returned 95 items."*) and ReqOverflow (*"Assessed: test code was consulted and returned 158 items."*) are unchanged — in memory and against the stored runs. Records written before readings existed render as they always did. | `sources.py` | `test_cotw_and_reqoverflow_sentences_are_unchanged`, `test_a_record_written_before_readings_still_reads_as_it_did`, `test_the_stored_runs_still_render_the_sentence_they_rendered` |
| AC5 | All wording stays in `sources.py`; the page only prints `run["assessment"]["sentence"]`. | `sources.py` | `test_no_page_module_builds_the_assessment_sentence` (scans `testops/web/*.py` for the sentence's own wording and from its own partial-read clause), plus AC3's test asserting the page carries the derived sentence |
| AC6 | The sentence uses the page's own words: "returned", "files", "kinds", "unreadable". No "capability", "registry", "reading", "arm", "observed", "snapshot", "artefact", "collector". It is stated once per page. | `sources.py`, `web/app.py` | `test_the_sentence_uses_the_page_s_vocabulary` (parametrised over three sentences), `test_the_run_page_states_the_sentence_once` |

Files touched: `testops/sources.py`, `testops/pipeline.py`, `testops/web/app.py`, and the new
`tests/test_partial_reads_visible.py` (18 tests). No analyser, store, schema, migration or
collector change; no version bump is needed (nothing is stored differently for an existing record,
and the new `lost` key is additive and read back defensively).

## The one judgement call, stated plainly

The ticket says CotW and ReqOverflow "both have zero skips". **They do not.** Queried from the
stored registry (`meta["sources"]["github"]["readings"]`):

- `cotw-levels-20261122T204947`: `code` 45 items with **7 skipped kinds / 94 files** (`.md` 54,
  `.txt` 23, `.json` 11, `(no suffix)` 2, `.ps1` 2, `.toml` 1, `.yml` 1); `test_code` 50 items
  with 5 kinds / 12 files. The page's arm records hold **106 files in 8 kinds**.
- `reqoverflow-dup-20261122T205100`: `test_code` 158 items with **11 kinds / 42 files**.

So "keep the sentence and also report every skip in it" cannot both be done by counting all skips:
CotW would gain a parenthetical. The two facts the sentence mixes had to be separated, and the
distinction that makes both AC2 and AC4 true is:

- **A loss** is a file of a kind this reader handles that the run did not fetch — in this build, a
  file over the 512 KB size cap. That is what makes a count partial, and the sentence names it
  with kind and count (AC2).
- **A kind the reader does not read at all** (`.java`, `.sql`, `.md`) is not a loss inside a
  capability: the run never claimed to read that kind. It is a fact about the repository, and
  AC3 now prints all of it on every run page, with kind, count, reason and names.

Under that reading CotW's and ReqOverflow's sentences are unchanged because neither lost a file
it would have read, and their 106 / 42 skipped files are on their pages for the first time.

The residual limit, which the reviewer should judge rather than discover: the ticket's example
parenthetical — "code returned 12 items (142 .java files and 3 other kinds unreadable)" — is not
produced, because this build cannot tell a `.java` from a `.md` without a per-ecosystem kind
table, and deciding which languages count as code is exactly TESTOPS-42's blocked product
decision. The 142 `.java` case is fully stated today on two surfaces that do not need that
vocabulary: the sentence says `code was not read: 142 .java files … no product code file was
fetched` (unchanged, TESTOPS-41) when the capability read nothing, and the new page section names
every kind whenever it read something. If the Product Owner wants unsupported source languages
inside the sentence as well, that is a ticket that depends on TESTOPS-42's answer.

## Nothing else moved

Rendered the same nine pages with a detached pre-change worktree at `9f31ef3` and with this
branch, against the same read-only store copy, normalising only the relative-age string:
`index`, `runs`, four run pages (`cotw-levels-20261122T204947`,
`reqoverflow-dup-20261122T164254`, `reqoverflow-dup-20261122T205100`,
`restfulbooker-levels-20261122T204917`) and three case pages.

    SAME  index
    SAME  runs
    SAME  case-case-cotw-dup-20261120T153507
    SAME  case-case-cotw-dup-20261120T194032
    SAME  case-case-cotw-levels-20261120T194425
    SAME  run-reqoverflow-dup-20261122T164254      (snapshot predates `reads`)
    DIFF  run-cotw-levels-20261122T204947
    DIFF  run-reqoverflow-dup-20261122T205100
    DIFF  run-restfulbooker-levels-20261122T204917

The three diffs are purely additive and identical in shape: one `@@` hunk at the end of the
"What this run could not consult" section inserting "Files this run could not read" and its rows.
No sentence changed on any page; CotW's page still says "Assessed: code and test code were
consulted and returned 95 items." where it said it before.

## For the reviewer — three probes that would catch a regression

1. `queries.run_read(conn, "cotw-levels-20261122T204947")["assessment"]["sentence"]` must be
   exactly `Assessed: code and test code were consulted and returned 95 items.` and the page for
   the same run must contain `The repositories hold 106 files in 8 kinds`.
2. A product arm with one `.py` fetched and 500 `.sql` skipped: the sentence stays the aggregate
   (no capability lost a file), the page shows `500 .sql` with `unsupported kind` and a
   `<details>` list.
3. A product arm with one `.py` fetched and one `.py` over `MAX_FILE_BYTES`: the sentence reads
   `Assessed: code and test code were consulted and returned 3 items (1 .py file unreadable).`

## Process note

Per AC6 of TESTOPS-44's sibling instruction, this report exists because the diff touches three
modules. The store under `data/` in this worktree is a copy for the suite and is gitignored; it
may be deleted without affecting anything, and the main checkout's store is untouched.
