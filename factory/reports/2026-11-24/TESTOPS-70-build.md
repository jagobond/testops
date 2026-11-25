# TESTOPS-70 build — a Java product reader

2026-11-24, branch `factory/testops-70-java-surfaces`. Suite: **1117 passed, 2 skipped**
(`pytest -q`, from the project `.venv`, `PYTHONPATH`/`PYTHONHOME`/`VIRTUAL_ENV`/`CONDA_PREFIX`
stripped, `PYTHONNOUSERSITE=1`). Contract suite alone: **37 passed, 2 skipped**. 17 of the new tests
are in `tests/test_java_surfaces.py`; the rest are unchanged except the four tests that asserted
`.java` was an unread kind (listed at the end).

## What changed

| file | change |
|---|---|
| `testops/surfaces/java.py` | **new.** A Java reader: lexer (comments, strings, chars and text blocks consumed as such), then a structural walk of type declarations, their annotations and their members. It reads the six Spring mapping annotations, class-level `@RequestMapping` prefixes, and the claim ladder. |
| `testops/surfaces/discover.py` | `LANGUAGES` is now `{".py": "Python", ".java": "Java"}`. Java files are parsed per file; a Java surface is `layer="api"`, `target="GET /booking/{id}"`, and its id carries the source and method so two methods on one route stay two surfaces. `parsed` counts `.py` files plus the `.java` files that actually lexed and parsed; an unparseable `.java` is not counted as read. The `not_assessable` reason now names both languages. |
| `testops/config.py` | `.java` added to `FILE_KINDS` as a `source` kind (`FileKind(".java", "source")`), so the collector fetches it instead of refusing it as unsupported. The `.py` note no longer says "the only source kind declared". |
| `testops/collectors/github.py` | docstring only: `.java` was added to the kind list because a reader reads it; the reporting rule for everything outside the list is unchanged. |
| `tests/fixtures/java/*.java` | six synthetic Spring controllers (below). |
| `tests/test_java_surfaces.py` | **new**, 17 tests. |

Nothing in the web layer changed, and no golden file changed.

## Criterion by criterion

| id | what was done, and the evidence |
|----|--------------------------------|
| AC1 | `.java` is in `LANGUAGES` and is parsed, not scraped: `test_java_is_a_language_the_reader_parses_and_its_files_are_reported_as_parsed` pins `parsed == 2` for two controllers, and `test_java_is_no_longer_a_kind_the_collector_refuses` runs the collector over an in-memory tree and pins that `src/App.java` is fetched (counted as `code`), that `.java` is absent from the unsupported-kind report, and that `.kt` is still reported. On the corpus, 142 `.java` files parse and 142 are reported. |
| AC2 | All six annotations produce surfaces. `@GetMapping`, `@PostMapping`, `@PutMapping`, `@PatchMapping`, `@DeleteMapping` are pinned by target; `@RequestMapping` is pinned with `value`, with `path`, with `method = RequestMethod.GET`, and with `method = {GET, POST}`. Class-level `@RequestMapping("/booking")` prefixes method paths. The three joining cases are pinned twice — once on the function (`test_the_three_joining_cases_are_pinned`: `/booking`+`/`→`/booking`, `/booking`+`/{id}`→`/booking/{id}`, no prefix+`/booking`→`/booking`) and once through the reader. |
| AC3 | Target reads like the Python one (`GET /booking/{id}`), layer is `api`, and ids are stable: two runs of `discover` over the same text yield identical id lists. `test_two_methods_mapping_the_same_route_are_two_surfaces` pins two declarations on `GET /dupes/same` as two surfaces with two ids and two different claims. The corpus shows the same at scale: 25 surfaces over 14 distinct `VERB path` targets (five `GET /`, three `DELETE /{id:[0-9]*}` across different services). |
| AC4 | Claims fall back in order: `@Operation(summary=...)`, else the first sentence of the method Javadoc, else the humanised method name (`getBooking` → `get booking`). Pinned on `POST /booking` (summary), `GET /booking/{id}` (Javadoc, first sentence only) and `PUT /booking/{id}` (name). An unannotated method is not a surface at all (`anUnannotatedHelper`). The model allows an empty claim list; the reader never produces one because a method always has a name, and the run page renders no surface section at all, so nothing on it can imply that a missing claim is a finding. |
| AC5 | Three states stay distinct. `found`: a Java repository with routes. `zero`: `PlainController.java`, parsed, no routes, empty reason. `not_assessable`: only when nothing parses, e.g. two `.kt` and one `.tsx` file, with the reason naming Python, Java and `2 .kt` (the TESTOPS-41 test was moved onto `.kt`). A mixed repository reports both languages and their counts (`{".java": 1, ".py": 1}`) and yields surfaces. At run level, `test_a_java_product_run_reports_surfaces_and_its_page_never_says_not_assessable` drives a real levels run over an in-memory Java product and asserts `surfaces_state == "found"`, a `found` snapshot record with `parsed == 1`, and that the run page contains neither "What the surface reader could not read" nor "not assessable". |
| AC6 | Fixtures under `tests/fixtures/java/`: `BookingController` (class prefix + method paths, all five verb annotations, Javadoc, `@Operation` summary, an unannotated method, a commented-out mapping and a mapping inside a string literal as decoys), `MultiPathController` (`{"/a", "/b"}`), `RequestMappingController` (`method = RequestMethod.GET`, a multi-path/multi-verb mapping, and the `path` alias), `BookingApi` (an interface), `PlainController` (no annotations), `DuplicateRouteController` (one route, two methods). No test reads the network or clones anything; the collector test points `get_json` at an in-memory tree. |
| AC7 | See below. |
| AC8 | Full suite and contract suite green; 208 case pages and the index are byte-identical; five run pages differ by one clause each (below). No golden fixture changed. |

## AC7 — the corpus, read again

Real run against `example-org/demo-booking-platform@efe2deb8` with the production pipeline
(levels run, GitHub collector, both arms), written to a **throwaway store** under the Hermes scratch
directory — the worktree's `data/testops.db` and the live store were opened read-only or not at all.
The token was placed in a temporary `.env` in the worktree, used, and deleted in the same command;
`test -s` proved the file held the variable before the run and `test -e` proved it gone after.

- run `demo-booking-levels-20261124T100624`, snapshot `demo-booking-levels-20261124-fe8537db`
- surfaces: **found**, **142** files parsed, **25** surfaces
- read: `{"code": 142, "test_code": 48}` → "Assessed: code and test code were consulted and returned
  190 items." (the same run before this ticket said *cannot assess: code was not read*)
- languages: `142 .java`, `23 .ts`, `4 .js`; the page no longer prints
  *What the surface reader could not read*
- test-side arithmetic unchanged: 43 claims, 4 cases — the same as
  `demo-booking-levels-20261123T132456`, because the level analyser does not consume surfaces.

Five named route declarations and what each claims (the corpus has no Javadoc and no `@Operation`,
so every claim here is the humanised method name — the third rung of the ladder, honestly):

| route | source | claim |
|---|---|---|
| `GET /` | `booking/src/main/java/.../BookingController.java` | `get bookings` |
| `GET /{id:[0-9]*}` | `booking/src/main/java/.../BookingController.java` | `get booking` |
| `POST /login` | `auth/src/main/java/.../AuthController.java` | `create token` |
| `PUT /{id:[0-9]*}/read` | `message/src/main/java/.../MessageController.java` | `mark as read` |
| `GET /room/{id:[0-9]*}` | `report/src/main/java/.../ReportController.java` | `get specific room report` |

All 25 were re-derived from the snapshot's own blobs after the run and matched the run's record
(`parsed 142, surfaces 25`), so the count and the reading are the same fact.

## AC8 — page promises and goldens

Every page the worktree store can serve (1 index, 47 run pages, 208 case pages; 256 files) was
rendered twice: once with `FILE_KINDS` as it stood before this ticket, once with it as it stands now.
**251 identical, 5 changed**, and each change is the same one clause — the new kind stated as a zero
in the per-repository read sentence:

> … 0 .cs files **, and 0 .java files**.

That is TESTOPS-55's promise doing its job: a kind the collector reads is stated for every repository,
and 0 is a fact. No case page changed, the index did not change, and no golden fixture changed. Old
demo-booking run pages still print "142 .java files … this run did not fetch" for the skipped files
of *that* run; the stored record is a fact about that run and is left alone, exactly like any other
historical skip.

## Decisions worth a reviewer's attention

1. **A parser, not a pattern.** The reader lexes first, so `@GetMapping("/fake")` in a comment and
   `"@GetMapping(\"/fake\")"` in a string are not routes. Two tests hold that line; the raw-text
   alternative would have reported 2 fake routes in the fixture.
2. **Ids carry the declaration, not just the route.** `api:GET /booking/{id}@<path>:<method>` (with a
   `#2` suffix if even that repeats) is stable for the same source and cannot fold two declarations
   into one. Python's `api:<route>` id would have made AC3's duplicate-route requirement impossible.
3. **Unspecified `@RequestMapping` verb is `ANY`.** Spring matches every method; `ANY` is the honest
   token rather than inventing `GET`.
4. **Per-service base paths are not joined.** The corpus mounts six services under different paths;
   the reader sees six independent controllers, so five `GET /` surfaces appear. Each is a real
   declaration with its own claims — the duplicate is reported, not hidden. Knowing the mount point
   is a deployment fact this reader does not have.
5. **`.java` in the product arm is product code, including `src/test/java`.** That follows the
   existing kind rule (a `source` file takes the arm's capability), and it inflates the corpus `code`
   count to 142, which is the number of files actually fetched and read. It is the same shape as the
   pre-existing TESTOPS-39 misfiling of product `.js`/`.ts` as step definitions; that vocabulary is
   still out of scope.
6. **The empty-claim case is modelled but not fabricated.** A method always has a name, so the
   reader's third rung always fires; the claim list type permits empty, and the page has no surface
   section that could turn an empty list into a finding.

## Tests updated because the premise moved

- `tests/test_skipped_is_not_consulted.py::test_the_collector_records_every_file_it_refused_with_the_reason_and_kind`
  — the refused file is now `.kt`, not `.java`.
- `tests/test_skipped_is_not_consulted.py::test_the_kind_list_is_configuration_and_whatever_it_holds_the_rest_is_reported`
  — widens with `.kt` instead of `.java`; `.scala` is the file left outside.
- `tests/test_skipped_is_not_consulted.py::test_a_boundary_in_a_language_the_reader_cannot_parse_is_not_assessable`
  — `.kt` files, and the reason is asserted to name both readers.
- `tests/test_skipped_is_not_consulted.py::test_a_kotlin_product_run_says_which_files_it_skipped_and_whose_code_it_did_not_read`
  (renamed) — 142 `.kt` skipped, because a Java product is now read.
- `tests/test_counts_that_say_what_they_count.py::test_the_skipped_section_never_reads_as_a_read_count`
  — `.kt` in the skipped section, so the page test does not use a kind this build now reads.

## Store

One evidence snapshot was written, and it went to the scratch store
(`…/cache/scratch/data70/testops.db`), not to `data/` and not to the live store. The worktree store
was read only, through `file:…?mode=ro`.
