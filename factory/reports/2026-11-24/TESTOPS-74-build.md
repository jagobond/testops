# TESTOPS-74 build — the Java reader stops guessing

2026-11-24, branch `factory/testops-74-java-honesty`. Suite: **1159 passed, 2 skipped**
(`pytest -q`, from the project `.venv`, `PYTHONPATH`/`PYTHONHOME`/`VIRTUAL_ENV`/`CONDA_PREFIX`
stripped, `PYTHONNOUSERSITE=1`; baseline before this ticket was 1149 passed). Contract suite alone:
**37 passed, 2 skipped**. 10 of the new tests are in `tests/test_java_honesty.py`; three existing
assertions moved because the premise moved (listed at the end).

## What changed

| file | change |
|---|---|
| `testops/surfaces/java.py` | `routes()` is now a thin wrapper over a new `read()`, which returns a `Reading`: the type's name and superclass, its own class-level prefix, the routes it can place, the mappings it could **not** place (`Unread`), and the reason a class prefix could not be read. A path argument that is not a string literal is unread, with the expression recorded. `@RequestMapping` on a superclass is never guessed here: the file says what it extends, and the caller resolves it. A path may be a literal, an array of literals, or else it is unread — a bare `/` is never a fallback. |
| `testops/surfaces/discover.py` | Resolves a superclass's class-level `@RequestMapping` **one level** from the files in the same repository and re-reads the subclass with that prefix; records every resolution (`inherited_prefixes`) in the snapshot. When the superclass is absent, ambiguous, or itself inherits farther than one level, the subclass's mappings are unread and name the class. `Discovery` carries `unread` and `inherited`, and `record()` writes both. A repository whose only mappings were unread is `found`, not `zero`: the reader found declarations; it could not place them. |
| `testops/sources.py` | `Assessment` carries a `unit` (singular noun). The sentence reads "returned N files" when the snapshot recorded what it counted, and "N items" for a snapshot written before the field existed. `_reading_clause`/`_result_clause` take the same noun. |
| `testops/pipeline.py` | Writes `count_unit: "file"` into the snapshot meta (TESTOPS-74 AC4), beside the registry it describes. |
| `testops/web/app.py` | `could_not_read_lines()` renders the unread mappings under **What the surface reader could not read**: `2 mappings unread: path is a constant`, then each method, source and expression, and a statement that none is counted as a surface. |
| `tests/fixtures/java/*.java` | Five fixtures: `BaseController` (prefix, no route) and `BookingChildController` (extends it), `ConstantPathController` (`Paths.BOOKING`, `Paths.ITEMS`), `ConstantPrefixController` (`Paths.CATALOGUE` on the class), `OrphanController` (extends `RemoteBaseController`, not in the repo). |
| `tests/test_java_honesty.py` | **new**, 10 tests, one per AC plus the edges. |

## Criterion by criterion

| id | what was done, and the evidence |
|----|--------------------------------|
| AC1 | `test_a_prefix_inherited_from_a_base_controller_is_resolved_and_recorded` pins the route as `GET /booking/{id}` (and explicitly that `GET /{id}` is **not** emitted) and pins the recorded resolution — source, type, superclass, the file it was read from, and the prefix. `test_an_inherited_prefix_the_repository_cannot_supply_is_unread_and_names_the_superclass` pins the orphan: no surfaces, one unread entry naming `RemoteBaseController`, present in `record()`. `test_an_inherited_prefix_is_read_one_level_and_the_deeper_case_is_unread` pins the boundary: a grandparent's prefix is not chased, and the reason says "this reader reads one level" and names `GrandController`. `test_a_superclass_that_declares_no_prefix_...` pins the non-case: nothing to inherit is not a reason to refuse a route. |
| AC2 | `test_a_mapping_path_that_is_a_constant_is_unread_and_invents_no_route` pins both positional and `value =` constants: no surfaces at all, two unread entries whose detail is exactly `Paths.BOOKING` / `Paths.ITEMS`. `test_a_class_prefix_that_is_a_constant_...` pins `Paths.CATALOGUE` unread. `test_a_reader_refuses_a_path_that_mixes_a_literal_and_a_constant` pins `Paths.PREFIX + "/{id}"`. Every path is either a literal (one, or an array of literals) or unread: there is no branch that falls back to `"/"`. |
| AC3 | `test_unread_mappings_are_reported_where_the_run_says_what_it_could_not_read` drives a real levels run over an in-memory product with two constant-path mappings and asserts the page contains `What the surface reader could not read`, the literal sentence **`2 mappings unread: path is a constant`**, and both expressions. The record carries `surfaces: 0` and two unread entries, so the count and the section cannot disagree. |
| AC4 | `test_the_assessment_sentence_names_files_not_items` pins, on the rendered run page, the exact sentence `Assessed: code and test code were consulted and returned 3 files.` and asserts the word "items" is not on the page. The noun is recorded with the run (`count_unit`), not derived at render time, so `test_a_stored_snapshot_without_the_noun_keeps_the_sentence_it_rendered` — and the checked-in case-page golden — keep the wording they were rendered with. See the decision below. |
| AC5 | Re-read the corpus; 25 surfaces, unchanged, with a stated reason. Method and numbers below. |
| AC6 | Full suite and contract suite green. The checked-in case-page goldens (`tests/fixtures/projects_services/*.html`, byte-compared by `test_every_case_page_and_the_indexes_are_byte_identical_after_the_migration`) are unchanged and pass. Stored run pages render byte-identically: 7 pages (index, runs, the run, 4 case pages) rendered from a **copy** of the scratch store with the pre-ticket package and with this branch are identical, manifest for manifest. New runs change for two stated reasons only: the AC4 noun, and the AC3 unread section when there is something unread. |

## AC5 — the corpus, read again

The corpus is `example-org/demo-booking-platform@efe2deb8`, as fetched by the TESTOPS-70 run
`demo-booking-levels-20261124T100624` and stored — 190 artefacts, of which **169 are product files
and 142 are `.java`**. The re-read took those files from the run's own blob store (the store is the
product's memory; no live source, no network, no token, therefore no `.env` to place or delete) and
ran this branch's `surface_discovery.discover` over them:

- state `found`, **142** files parsed, **25** surfaces, **14** distinct `VERB path` targets
- **0 unread**, **0 inherited prefixes**

**The count does not move, and here is why.** Neither defect fires in this corpus: none of the six
controllers extends anything — the only `extends` clauses are test classes and page objects
(`extends BaseTest`, `extends BasePage`), and none of them declares a mapping — and every mapping
path in the corpus is a string literal. The 25 surfaces are the same 25, derived from the same
declarations; the reader is now strict where the corpus happens to be simple, which is what a
regression-free fix should look like. That the *shapes* work is pinned by the fixtures instead
(none of which exists in the corpus, which is why the corpus cannot move).

## Decisions worth a reviewer's attention

1. **AC1 and AC2 conflict exists nowhere: both are "refuse to invent".** One shared rule: a route
   this reader cannot compute is not emitted. A prefix it cannot find is not replaced by "no
   prefix"; a path it cannot read is not replaced by `/`.
2. **Inheritance is one level and says so.** The reader records `superclass`; the repository
   resolver reads exactly that one file. A deeper chain is unread with the grandparent named, not
   silently walked — walking arbitrary depth would be a project-wide type resolver wearing a
   reader's clothes.
3. **A superclass in the repository that declares no prefix is not an error.** There is nothing to
   drop, and the route is emitted as before. Only an unknown prefix is unread.
4. **`found` with zero surfaces.** A repository whose only mappings are unread has read files and
   found declarations, so `zero` ("read and found nothing") would be the very wrong answer this
   ticket is about. The page states the count and the unread list side by side.
5. **AC4's noun is recorded, not retro-fitted — the one call a reviewer should check.** AC4 requires
   the sentence to define its noun; AC6 requires no case-page golden change, and the checked-in
   `case-page-09.html` embeds `returned 48 items`. Both are honoured by writing the noun into the
   snapshot (`count_unit: "file"`) and rendering it when present: every run made from now on says
   "files"; a snapshot written before the field keeps the sentence it was rendered with, exactly as
   every other derived-from-record sentence in this product does. The alternative — changing the
   builder unconditionally — rewrites that golden and every stored run page, which AC6 forbids. If
   the Lead prefers the retro-fit, it is a one-line change plus a golden update, and the reason to
   prefer it is that old pages keep an ambiguous noun.
6. **The unread section is grouped by reason, then named.** `2 mappings unread: path is a constant`
   is the summary a reader checks against the list beneath it; a bare count with no list would be
   the same silent exclusion one level down.

## Tests updated because the premise moved

- `tests/test_partial_reads_visible.py::test_a_run_that_skips_five_hundred_sql_files_says_so_though_its_code_read_fine`
  — the pipeline now records `count_unit`, so the sentence is `returned 3 files.`
- `tests/test_partial_reads_visible.py::test_a_lost_file_makes_the_sentence_partial_and_the_page_still_lists_it`
  — `returned 3 files (1 .py file unreadable).`
- `tests/test_skipped_is_not_consulted.py::test_a_kotlin_product_run_says_which_files_it_skipped_and_whose_code_it_did_not_read`
  — `test code was consulted and returned 2 files`.

The stored-snapshot pins (`DEMO_SENTENCE` 95 items, `DEMO_SERVICE_SENTENCE` 158 items) are untouched
and pass: those snapshots predate the noun.

## Amendment — the review's three concerns

`factory/reports/2026-11-24/TESTOPS-74-review.md` failed this build: two silently wrong routes
still got through, in the class of defect the ticket exists to close. All three concerns are fixed
in this amendment.

1. **A prefix on an implemented interface was dropped.** `java.Reading` now carries `interfaces`
   (`_implements` reads the header, skipping generic arguments), and the resolution loop in
   `discover.py` treats `extends` and `implements` alike: one level from the same repository,
   recorded in `inherited_prefixes` under the `interface` key, or unread with the interface named.
   `GET /{id}` is no longer emitted for `InterfaceChildController implements BookingPrefixApi`.
2. **A parent whose own prefix is a constant made the child unprefixed.** The parent's
   `class_problem` is now consulted: the child is unread carrying the parent's own reason
   (`class prefix is a constant`) and the parent's name and expression in the detail.
3. **A superclass file that exists but does not lex was reported as "does not hold".** Files this
   reader could not lex now have their declared type names read without lexing (comments stripped),
   so the refusal says the repository *holds* the file and this reader could not read it, naming
   the path.

Pinned by five new tests in `tests/test_java_honesty.py` (interface prefix resolved and recorded;
unheld interface -> unread naming it; interface with no class prefix -> not refused; constant
parent -> unread with the parent's reason; unlexable superclass -> "could not read", not "does not
hold"), plus four new fixtures. Full suite **1164 passed, 2 skipped**; contract suite **37 passed,
2 skipped**. Corpus re-read unchanged: **142 parsed, 25 surfaces, 0 unread, 0 inherited, 14
targets** — no surface disappeared. No case-page golden changed, and the 7 stored run pages
rendered from a copy of the scratch store are byte-identical to the build commit's rendering.

## Store and network

No port was opened (pages were rendered by calling the app directly), port 8791 was never contacted,
and the live store was never opened. The corpus re-read used the read-only scratch store's blobs and
the page comparison used a copy of that store (`…/cache/scratch/data74copy`). No credential was
needed, written or printed.
