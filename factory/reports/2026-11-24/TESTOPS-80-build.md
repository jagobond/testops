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

## Amendment — review of 2026-11-24 (`factory/reports/2026-11-24/TESTOPS-80-review.md`)

Review verdict was **changes requested**: substance right, one real defect (its concern 1), one
wording fault (concern 2), one coverage gap (concern 3). All three are addressed below; the report
above is left as it was written.

### Fix 1 — the routes tag is emitted once per case (review defect)

The append block sat **inside `for claim in claims:`** (`testops/queries.py`), although it reads only
`meta`, `examined`, `needs` and `product_repo`. A case with two claims rendered the tag twice; a case
with zero claims rendered no tag at all while its verdict could still quote routes. No stored case and
no test had `claims != 1`, so the suite was green by coincidence of shape.

`source_band()` now builds the routes tag **before** the claims loop, at function-body indentation, and
the comment says why it must stay there. Pinned by
`test_the_routes_tag_is_emitted_once_per_case_whatever_the_claim_count`, which renders the same
snapshot with **zero, one and two** claims and asserts, for each, that the band carries exactly one
`aria-label="Product routes:` and exactly one `tag-kind">Product routes<`, that the tag is consulted,
and that the three rendered tags are identical — one fact, one tag, whatever the claim count. The test
helper `_case()` gained a `claims=` parameter for this (default 1, so every other test is unchanged);
it writes one finding whose `claim_ids` holds all of them, or none.

### Fix 2 — the number is called what it is: surfaces (review concern 2)

`surfaces` in the record is the routes the reader resolved **plus** the engine modules it found
(`surfaces/discover.py:301`), so saying `47 routes` for the CotW product told a reader that modules were
routes. `product_routes_tag()` now says what the number counts:

    found:  142 .java parsed, 25 surfaces (routes and engine modules)      consulted
    zero:   142 .java parsed, no routes found                             consulted

The choice between the review's two options was made in favour of **saying what the number is**, not
of carrying the split in the record: the record is written at run time, so a new field would leave the
existing records (26 snapshots in this store, every golden fixture) still reading as routes, and the
wording fix applies to every record ever written. The ticket's illustrative sentence
(`factory/tickets/TESTOPS-80.md`, AC1: "142 .java parsed, 25 routes") is therefore **deliberately not
matched word for word** — it is the sentence the review found untruthful on CotW. `zero` is unchanged:
with no surfaces there are no routes either, so "no routes found" is exact. Pinned by the AC1 and AC2
page tests and by the golden below.

### Concern 3 — one golden whose fixture carries a `surfaces` record

Added: **`tests/fixtures/source_band/case-surfaces-band.html`** (12,319 bytes), rendered from the
`_found()` record (142 .java parsed, 25 surfaces) by the same `_case()` helper the page tests use, with
`app.age` frozen. It is pinned by
`test_the_routes_tag_sentence_is_pinned_byte_for_byte_by_a_golden_page`, which renders the page again
and compares the bytes.

What changed: **no existing golden changed** — `git diff origin/main...HEAD -- tests/fixtures/projects_services/`
stays empty, because those fixture snapshots predate the `surfaces` record and the band on them renders
no routes tag. The new golden is the first, and only, checked-in page whose band contains the
routes-tag sentence, so a rendering regression in exactly that sentence now fails a byte comparison as
well as a page test. Regeneration, if ever needed, is a deliberate act: render `_case(tmp_path,
meta=_meta(surfaces=_found()), store="golden.db")` with `app.age` frozen to "a fixed time ago" and
write the bytes to that path — never overwrite it silently from a test run.

### Re-run after the amendment

- Full suite, from the project `.venv` with `PYTHONPATH`/`PYTHONHOME`/`VIRTUAL_ENV`/`CONDA_PREFIX`
  stripped and `PYTHONNOUSERSITE=1`: **1235 passed, 2 skipped** (1233 before the amendment; the two new
  tests are the three-shape test and the golden).
- Contracts: **37 passed, 2 skipped**.
- The real case, re-rendered on a **copied** store in scratch and served on an **ephemeral free port**
  (8791 and the live store never approached): `case-restfulbooker-levels-20261124T114627-05` still says

      142 .java parsed, 25 surfaces (routes and engine modules)   consulted

  with `169` and `reqnroll` absent from the band and the verdict sentence unchanged. A sweep of all
  **221** case pages in the copied store: 20 render a routes tag, **none renders two**, and no page
  pairs a repeats-product verdict with a not-consulted routes tag.
- CotW `case-cotw-levels-20261122T204947-01/02` (snapshot `cotw-levels-20261122-a3f19853-r11`, the
  case the review names) now renders `45 .py parsed, 47 surfaces (routes and engine modules)` — the
  number unchanged, the noun honest.