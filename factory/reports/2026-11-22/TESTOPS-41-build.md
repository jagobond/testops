# TESTOPS-41 build — skipped is not consulted

2026-11-22, branch `factory/testops-41-skipped-is-not-consulted`. Suite: **428 passed** (`pytest -q`
from `.venv`, `PYTHONPATH`/`PYTHONHOME`/`VIRTUAL_ENV`/`CONDA_PREFIX` stripped, `PYTHONNOUSERSITE=1`).
Eleven of them are new, in `tests/test_skipped_is_not_consulted.py`; the rest are unchanged.

## The sentence, before and after

Before, on the TESTOPS-39 specimen (Java product, JavaScript suite):

> Assessed: code and test code were consulted and returned 48 items.

48 was what had been fetched: 6 features and 42 `.js`/`.ts` files, 27 of them from the product
repository, counted once for a source serving both capabilities. 142 `.java` files had been dropped by
a suffix list, and no product code file had been read.

After, re-run on the same pinned commits (`cypress-cucumber-e2e-tests@262404a9`,
`restful-booker-platform@efe2deb8`):

> Cannot assess this claim: code was not read: 142 .java files in the product repository were skipped
> because .java is not a kind this collector reads (unsupported kind), along with 169 more in 17 other
> kinds, so no product code file was fetched; test code was consulted and returned 48 items.

The page (`/run/restfulbooker-levels-20261122T204917`) also lists every skipped file by kind under
*Files this run could not read*, and says under *What the surface reader could not read*: "the surface
reader parses Python only, and the product repository holds no file it can read: 23 .ts, 4 .js. No
surface was found and none was ruled out."

## Criterion by criterion

| id | what was done | where |
|----|---------------|-------|
| AC1 | The collector classifies every blob in the tree into *fetched*, *ignored by pattern*, *over the size cap* or *unsupported kind*, and records the refused ones as `Skipped(reason, kind, files)` in `Collected.skipped`. The run writes them into the snapshot's `meta["reads"][arm]`, with the file list, and into its stats as per-kind counts. Counts come from fetched files only, so a skipped file can never be counted as read. | `collectors/github.py`, `pipeline.py` (`_skips`, `meta["reads"]`) |
| AC2 | A source now records a `Reading` per capability: *observed N* (N may be 0 — a real zero), or *not readable* with the reason and the skips. `Registry.with_readings` replaces the single aggregate count; `assess` returns `NOT_ASSESSABLE` when a needed capability could not be read, and the sentence names each capability separately. `code` no longer reads as observed when no product code file was fetched. A record written before this change has no readings and is read through `observed` exactly as before. | `sources.py` (`Reading`, `NOT_READABLE`, `with_readings`, `assess`, `Assessment.sentence`) |
| AC3 | `surfaces/discover.discover` returns a `Discovery`: `found` / `zero` / `not_assessable`, with the reason (the language it parses and the suffixes and counts the repository holds) and the per-language counts. The run's stats carry `surfaces`, `surfaces_state` and `surfaces_reason`; the snapshot records the same under `meta["surfaces"]`, so a run page can say why a count is 0. | `surfaces/discover.py`, `pipeline.py`, `web/app.py` (`could_not_read_lines`) |
| AC4 | Proven above on the corpus, and pinned by `test_a_java_product_run_says_which_files_it_skipped_and_whose_code_it_did_not_read` plus a corpus test that reads the live store read-only. | `tests/test_skipped_is_not_consulted.py` |
| AC5 | See below: verdict counts and pages. | — |
| AC6 | The suffix list is `config.FILE_KINDS`, a tuple of `FileKind(suffix, kind, capability)`, plus `IGNORE_PATTERNS`, `DROPPED_SUFFIXES` and `MAX_FILE_BYTES`. No suffix appears in the collector. `test_the_kind_list_is_configuration_and_whatever_it_holds_the_rest_is_reported` widens the list with `monkeypatch` — no code moves — and asserts the file left outside it is still reported. `.java` was **not** added: a longer list is the same bug with more entries. | `config.py`, `collectors/github.py` |

## AC5 — the two earlier corpora

Re-run, not reconstructed:

| corpus | verdicts | sentence |
|---|---|---|
| CotW (`cotw-levels-20261122T204947`) | 94 claims: 90 distinct / 1 unplaced / 1 gap / 2 review | *Assessed: code and test code were consulted and returned 95 items.* (unchanged) |
| ReqOverflow (`reqoverflow-dup-20261122T205100`) | 17 claims / 17 cases | *Assessed: test code was consulted and returned 158 items.* (unchanged) |

Byte comparison: every page the store could serve before the change (index, `/runs`, 40 run pages,
184 case pages — 228 files) was rendered with the pre-change code and again with the working tree,
both from the same store, read-only. All 228 were byte-identical immediately after the change. A
second comparison an hour later differed on 16 pages by the relative-age text alone ("8 hours ago" →
"9 hours ago"); the HTML content was identical.

With the fix in place, a fresh levels run re-reads `code` 45 from the product arm and `test_code` 50
from the test arm for CotW — 95 in total, the same figure the old single count reported.

## Decisions worth a reviewer's attention

1. **A file is counted for the capability its *kind* serves, not the arm it came from.** A `.js`/`.ts`
   file is a step definition to this collector, so the product repository's 27 assets count as test
   code (21 from the test repository, 27 from the product repository — the arm split is recorded in
   the reading's `arms`). That keeps the restfulbooker total at 48 and keeps `code` at zero, which is
   what AC4 asks for. It leaves TESTOPS-39's misfiling (product front-end files labelled `stepdef`) in
   place; fixing the vocabulary is not this ticket.
2. **`not_assessable` is reached only when the tree held files outside the kinds.** An arm that
   fetched nothing *and* skipped nothing is a real zero: the reader looked and there was nothing.
3. **The skip list is rendered on a run page only when it explains an unread capability.** Every run
   records it (AC1); a run that read all it needed is not made more truthful by a list of its
   `README.md` files, and CotW's page is not turned into a wall of `.md`.
4. **The surface reader still parses Python only.** AC3 asks it to say so, not to learn Java; a Java
   grammar is a separate decision.
5. **TESTOPS-42 untouched.** The cucumber-js binding gap is unchanged: the 44 cucumber-js bindings in
   this corpus are still read as none.

## Store

Four new snapshots were written by the evidence runs (they add, they do not replace):
`restfulbooker-levels-20261122T204834`, `restfulbooker-levels-20261122T204917`,
`cotw-levels-20261122T204947`, `reqoverflow-dup-20261122T205100`. No snapshot, artefact or blob was
modified or deleted.
