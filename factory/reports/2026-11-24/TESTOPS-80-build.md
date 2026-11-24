# TESTOPS-80 build — the band's routes tag is answered by the surface reader

2026-11-24, branch `factory/testops-80-band-truth` (based on `ae85541`). Suite: **1233 passed,
2 skipped** (`pytest -q`, project `.venv`, `PYTHONPATH`/`PYTHONHOME`/`VIRTUAL_ENV`/`CONDA_PREFIX`
stripped, `PYTHONNOUSERSITE=1`; baseline on this branch was 1232 passed, 2 skipped, 1 failed — see
the note at the end). Contract suite alone: **37 passed, 2 skipped**. Goldens: **none changed** —
`test_every_case_page_and_the_indexes_are_byte_identical_after_the_migration` passes unmodified,
because every checked-in page's snapshot predates the `surfaces` record, so no band on those pages
moves.

## What changed

| file | change |
|---|---|
| `testops/queries.py` | New `product_routes_tag(meta, product_repo)` and `_parsed_languages(record)`: the one place that answers "were the product's routes read", from the snapshot's own `surfaces` record. `found` is a consulted tag whose detail is the reader's parsed count, its language and its route count (`142 .java parsed, 25 routes`); `zero` is consulted with `142 .java parsed, no routes found`; `not_assessable` is a dimmed "not consulted" tag carrying the reader's own reason. No `surfaces` record (a snapshot older than the record) renders no tag at all — not recorded is not "not consulted". `source_band()` now calls this instead of the `ecosystems.product` block, which is deleted. |
| `tests/test_case_source_band.py` | Four new tests, one per surface state plus the "no record" case; one new AC2 test (repeats-product verdict and an unconsulted routes tag cannot coexist, in both directions). Helpers extended to carry `surfaces`, a claim verdict and a product record. The old `test_a_product_the_readers_cannot_parse_is_a_dimmed_blind_spot_beside_the_evidence` was **removed**: it pinned the defect (routes answered by the ecosystem detector) and is replaced by `test_a_product_the_surface_reader_could_not_read_keeps_the_readers_reason`. |
| `tests/test_skipped_is_not_consulted.py` | One test-only maintenance change, not behaviour: the corpus probe `test_the_restfulbooker_run_names_the_java_it_could_not_read` pinned the run it describes (`restfulbooker-levels-20261123T132456`) instead of `ORDER BY started_at DESC LIMIT 1`. The sentence it asserts ("code was not read: 142 .java files …") is the pre-TESTOPS-70 record; the newest run in the worktree store (24 Nov, after the Java reader landed) reads Java and says `returned 190 files`. Left unpinned, the probe silently changed meaning with the corpus and failed before this ticket's change (verified by stashing the branch diff). |

## Criterion by criterion

| id | what was done, and the evidence |
|----|--------------------------------|
| AC1 | `test_the_routes_tag_reads_the_surface_reader_and_says_what_it_parsed` drives a snapshot whose `ecosystems.product` still says "none of the 3 ecosystems this build knows was recognised in the 169 files read (reqnroll, python-bdd, cucumber-js)" while `surfaces` is `found` (142 parsed, 25 routes). The band's Product routes tag reads **`142 .java parsed, 25 routes`**, is `consulted`, and the page contains neither `169` nor `reqnroll`. `test_a_reader_that_read_the_files_and_found_no_route_says_so` pins `zero` as **`142 .java parsed, no routes found`**, consulted. `test_a_product_the_surface_reader_could_not_read_keeps_the_readers_reason` pins `not_assessable` as a dimmed `tag unconsulted` carrying the reader's reason verbatim (`the product repository holds no file it can read: 23 .ts, 4 .js`). |
| AC2 | `test_a_repeats_product_verdict_cannot_sit_beside_a_not_consulted_routes_tag`: with a claim whose verdict is `repeats_product` (page says "already declares POST /") the Product routes tag is `142 .java parsed, 25 routes`, never "not consulted"; conversely, on a `not_assessable` snapshot the page says "not consulted" and contains neither "already declares" nor "already exposes this". Both directions are asserted on the rendered page, not on the store. |
| AC3 | The count comes from the reader's own `parsed` field and the suffixes it parses (`surface_discovery.LANGUAGES`), so `_parsed_languages()` cannot report the snapshot's artefact total: the AC1 test pins `142 .java` and asserts `169` is absent from the band. |
| AC4 | `queries.product_routes_tag` is the single computation of the band's route facts; `source_band` only places its tag. The test-ecosystem record is no longer consulted anywhere in the band, and is left doing what it can answer: the run page's per-repository "read as" line (contract P11) and the test-suite clause. |
| AC5 | Full suite and contract suite green (numbers above). No golden was regenerated because none needed to be; the byte-identical golden test passes unchanged. Page tests pin the exact sentence for each of the three states (AC1 row). |

## The live page, on a copied store

`data/testops.db` and `data/blobs` were copied to a scratch `TESTOPS_DATA` directory and the app was
served on **127.0.0.1:8799** for the check; port 8791 and the live store were not touched. Before,
`case-restfulbooker-levels-20261124T114627-05` said:

    Product routes  mwinteringham/restful-booker-platform  not consulted
                    none of the 3 ecosystems this build knows was recognised in the 169 files read
                    (reqnroll, python-bdd, cucumber-js)

while its verdict said "the product already declares `POST /`". After, the same page says:

    Product routes  mwinteringham/restful-booker-platform  consulted
                    142 .java parsed, 25 routes

and the verdict is unchanged. All 13 cases of that run render the same routes tag; no case page in
the copied store has a repeats-product sentence next to a "not consulted" Product routes tag.

## Decisions worth a reviewer's attention

1. **The tag is not a link.** The product repository tag already links the repo at its commit; a
   second link would make the reader choose between two identical destinations. The routes tag is a
   focusable note (`tabindex="0"`, `role="note"`) whose words carry the fact, which is what AC5 of
   TESTOPS-73 asks for.
2. **`zero` is a consulted tag, not a warning.** "Read them and found none" is a reading, and the
   band must not dress a fact as a blind spot. `not_assessable` is the only dimmed state.
3. **A snapshot without the record is silent.** The band already refuses to invent a missing source;
   rendering "not consulted" for a snapshot written before `surfaces` existed would be the same
   fault in the other direction.
4. **The ecosystem record is not deleted.** It still says which ecosystem each repository was read
   as (P11, and TESTOPS-42A's evidence), but only beside the test suite it can describe; the band no
   longer uses it to answer a question about the product's routes.