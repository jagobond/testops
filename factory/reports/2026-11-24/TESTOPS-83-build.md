# TESTOPS-83 build — the two lines this case is made of

2026-11-24, branch `factory/testops-83-code-snippets`. Full suite: **1268 passed, 2 skipped**
(`pytest -q`, the project `.venv`, `PYTHONPATH`/`PYTHONHOME`/`VIRTUAL_ENV`/`CONDA_PREFIX` stripped,
`PYTHONNOUSERSITE=1`). Contract suite alone: **37 passed, 2 skipped**. Port 8791 and the live store
were not contacted; every check rendered the worktree's copied store.

## What changed

| file | change |
|---|---|
| `testops/queries.py` | New `product_line_for()` and its helpers: resolves the claim's recorded product surface against the run's stored artefacts and blob, and returns the Java annotation block + method signature (or the Python decorator + function signature), with file, line, commit, the matched word, and an honest line count. States: `ok`, `no_coordinates`, `not_stored`, `not_found`, `ambiguous`, `blind`. Also attaches the record at `claim["snippets"]["product"]`, and puts `detail` on the claim before snippets are attached (the case read model previously replaced `detail` after `_with_snippets`, so the product record was invisible there). |
| `testops/web/app.py` | `product_line_block()`: a labelled `<figure>` region (`aria-label="Product code at <path>:<line>"`), monospace `<pre tabindex="0">`, per-occurrence `<mark role="mark" aria-label="matched word: …">`, an ellipsis row with its own accessible name, and a caption naming file, line, commit, the stated maximum, the true declaration length and the number of lines not shown. Each absence has its own sentence. Snippets now name their commit; the assertion/step-definition captions also carry it (AC1). |
| `testops/services.py` | `credential_reason()`: the existing credential-shape screen exposed as a question, so the read model withholds a declaration that matches a known shape without re-implementing the rules. |
| `tests/test_case_product_line.py` | 14 tests: verbatim equality with the blob, the run's own commit (a decoy artefact at another commit is ignored), accessible marking, honest trimming of a 400-line handler, all five absences, credential withholding, markup escaping, no socket at render time, a Python route, and the checked-in not-located golden. |
| `tests/test_case_summary_and_code.py` | One assertion added: the test line's caption names its commit (AC1). |
| `tests/contracts/seed/make_seed.py`, `seed.json`, `blobs/`, `README.md` | Golden regenerated deliberately: the newest restfulbooker run (`restfulbooker-levels-20261124T123451`, five cases with product surfaces and their Java commits) is now part of the evidence slice, and the claims' inference rows travel with it (the product surface record lives there). 4 runs, 286 artefacts, 187 observations, 146 claims, 129 inferences, 26 cases, 187 blobs. |
| `tests/fixtures/projects_services/*.html`, `tests/fixtures/source_band/case-surfaces-band.html` | Regenerated for the shared stylesheet (the new `.sline.omission` rule is in every page). No page's content changed otherwise. |
| `tests/fixtures/product_line/case-product-line-missing.html` | New golden: the one case where the product line could not be located, rendered with the clock frozen. |

## What the case page now shows

`case-restfulbooker-levels-20261124T123451-05`, from the copied store:

    The product’s own declaration, with the word that decided the match marked:
    room/src/main/java/com/automationintesting/api/RoomController.java:42 at commit efe2deb8 —
    view in repository. At most 8 lines are shown: lines 42–43 of a 6-line declaration, so 4 lines
    are not shown.

    42     @RequestMapping(value = "/", method = RequestMethod.POST)
    43     public ResponseEntity<Room> createRoom(@Valid @RequestBody Room roomToCreate, @CookieValue(value="token", required = false) String token) throws SQLException {

Every `Room`/`room` occurrence in those lines is a `<mark role="mark" aria-label="matched word: room">`,
so the shared word that decided the match is visible as text and announced, not signalled by colour.
The verdict sentence above it is unchanged: "the product already declares `POST /`".

`case-restfulbooker-levels-20261124T123451-01` renders the same block for `GET /` —
`@RequestMapping(value = "/", method = RequestMethod.GET)` and
`public ResponseEntity<Rooms> getRooms(...)` at `RoomController.java:22`.

The same page rendered from a store **built from the contract seed only** was checked: the figure is
present for both cases, so the regenerated golden really carries the snippet path.

## Criterion by criterion

| id | what was done, and the evidence |
|----|--------------------------------|
| AC1 | The assertion line is read from the stored blob, with its file, line and commit: `_assertion_snippet` now carries the claim's commit and `_snippet_caption` prints it beside `path:line`. The surrounding step context is the existing ±2-line window (the `When` that supplies the value and the `Examples` header are on the page). Pinned by `test_the_asserted_step_is_shown_inline_with_its_line_numbers` (commit) and the existing AC5 tests. |
| AC2 | `product_line_for()` resolves the recorded surface id (`api:POST /@room/src/.../RoomController.java:createRoom`) to the artefact at the product arm's own commit, reads the stored blob, and locates the declaration with the Java reader's lexer (a name in a comment or string is not a declaration). The annotation block and signature are shown with file, line and commit. Python route surfaces (`api:GET /booking`) resolve to the decorator and `def` signature by the surface reader's own rule. Where no file/declaration was located the page says so; nothing is guessed. Pinned by the verbatim test, the commit test, the Python test and the absence tests. |
| AC3 | Shown lines are the blob's own lines, whitespace untouched; a test asserts `(line number, text)` for every rendered line equals the blob. Escaped as text line by line, with only `<mark>` inserted around the matched word. |
| AC4 | No network at render time (`test_rendering_the_product_line_opens_no_socket` and the existing AC9 test); markup renders escaped; the shown declaration is screened with `services.credential_reason` (the same rules as the store guard) and withheld with a reason if it matches a credential shape. `hunter2-the-real-one` never reaches the page. |
| AC5 | At most `PRODUCT_SNIPPET_MAX` (8) annotation/signature lines are shown; when the declaration is longer the caption states the maximum, the true declaration length and how many lines are not shown, and an ellipsis row (`role="note" aria-label="N lines of the declaration not shown"`) marks the cut. A 404-line handler shows its annotation and signature and says 402 lines are not shown. |
| AC6 | `<figure role="group" aria-label="Product code at <path>:<line>">` names the region; `<pre tabindex="0">` is keyboard reachable; `<mark role="mark" aria-label="matched word: …">` gives the mark an accessible name and the CSS uses weight as well as the wrapper. |
| AC7 | Full suite 1268 passed / 2 skipped; contract suite 37 passed / 2 skipped. Goldens regenerated deliberately and listed above; the not-located case is the new `tests/fixtures/product_line/case-product-line-missing.html`, checked against bytes. |

## Decisions worth a reviewer's attention

1. **The line is located in the stored blob, not recorded by the old analyser.** The run predates
   this ticket, so its claims record a surface id with a path and a method name but no line. The
   page finds the declaration *in the run's own bytes*, using the same lexer that read the route;
   that is a lookup of the stored evidence, not a live checkout and not a guess. Future runs gain
   nothing special: the same resolution runs.
2. **The body is never shown.** AC5 says a 400-line handler shows its annotation and signature, so
   the window is annotation + signature; the omitted count still describes the whole declaration,
   so the trim cannot flatter a long handler.
3. **Python is resolved by the reader's rule, and ambiguity is an absence.** A Python route surface
   records no path, so the page searches the stored product files for a function whose declaration
   (decorator or body) holds the route literal. Two matches is `ambiguous` and the page says so
   rather than choosing.
4. **The seed now includes inference rows.** They were deliberately excluded as "rendered on no
   page"; that stopped being true when the product line became part of the page, so the slice now
   carries them. Without them the contract pages would show an absence no run produced.
5. **The synthetic not-located golden is the corpus caveat, not a fabricated case.** No recorded
   surface in the store fails to resolve, so the state can only be witnessed by a fixture; the
   golden is a checked-in page rendered from a fixture claim, not a row injected into the seed.
