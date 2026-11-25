# TESTOPS-84 build — the block must admit what it could not delimit

2026-11-24, branch `factory/testops-84-honest-block`. Full suite: **1276 passed, 2 skipped** with

    env -u PYTHONPATH -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
      C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe -m pytest -q

Contract suite alone: **37 passed, 2 skipped**. Port 8791 and the live store were not contacted;
the page quoted below was rendered from the worktree's copied store, opened `mode=ro`.

## The fault, and what replaced it

TESTOPS-83 set a declaration's end to the signature when the brace walk could not close the body.
The caption then had `omitted = 0`, so no ellipsis appeared and no count was stated: two signature
lines sat on the page as though they were the whole declaration while the stored file continued.
That was a silent cut in the one state where the tool most needs to be honest.

A located declaration is now in exactly one of three states, and each has its own sentence:

| state | the page's sentence |
|---|---|
| complete and small | **"The whole declaration is shown."** |
| delimited but trimmed | **"The signature is 2 of 6 lines of this declaration (lines 42–43); the other 4 lines are the body, which this page does not print."** |
| undelimitable | **"The rest of this declaration could not be delimited: its opening brace was found and its closing brace was not, so this page shows only its beginning and cannot say how many lines follow."** |

The first has no ellipsis and no count; the second has a counted remainder and the ellipsis row
`aria-label="4 lines of the declaration not shown"`; the third has no count at all and its ellipsis
row says `aria-label="the rest of this declaration could not be delimited"`.

`case-restfulbooker-levels-20261124T123451-05` from the copied store — the case the review
complained about — now reads:

    The product’s own declaration, with the word that decided the match marked:
    room/src/main/java/com/automationintesting/api/RoomController.java:42 at commit efe2deb8 —
    view in repository. The signature is 2 of 6 lines of this declaration (lines 42–43); the
    other 4 lines are the body, which this page does not print.

    42     @RequestMapping(value = "/", method = RequestMethod.POST)
    43     public ResponseEntity<Room> createRoom(@Valid @RequestBody Room roomToCreate, ...)

## What changed

| file | change |
|---|---|
| `testops/queries.py` | `_locate_java_declaration()` now reports `delimited` and `unclosed_brace`: a `{` that is found and never closed (or a file that ends before the body begins) is an unknown extent, not a signature-sized declaration. A `;` declaration is delimited at its semicolon. `_declaration_lines()` returns what actually cut the block (`cap` when the 8-line ceiling stopped before the signature ended, `body` when only the body is absent). Records carry `delimited`, `cut`, `total` (only when delimited) and, for the undelimitable state, `why`. Python: `_locate_python_declarations()` reports whether the file parsed; an unparseable file that still holds the route's literal and the `def` it decorates is *undelimitable* and shows its beginning, not "no declaration". |
| `testops/web/app.py` | `_product_snippet_caption()` writes the three sentences above, so the cap is only named when the cap is the cause. `product_line_block()` always renders an ellipsis row for an undelimitable declaration, with an accessible name that states the inability rather than borrowing a count it does not have. |
| `tests/test_case_product_line.py` | 8 new tests (22 in the file): the no-closing-brace fixture, one test per state asserting the exact sentence, a cap that cuts a long signature (names the cap), the 404-line handler (names the body, not the cap), Python complete/trimmed/undelimitable, and a golden test over the three state pages. Golden comparison now normalises CRLF from a `core.autocrlf` checkout, because a line-ending translation is not a changed page. |
| `tests/fixtures/product_line/` | Three new goldens, rendered deliberately from the fixture with `app.age` frozen: `case-product-line-complete.html`, `case-product-line-trimmed.html`, `case-product-line-undelimitable.html`; plus `README.md` listing all four (the TESTOPS-83 `-missing.html` golden is unchanged and still passes). |

## Criterion by criterion

| id | what was done, and the evidence |
|----|--------------------------------|
| AC1 | `_locate_java_declaration()` returns `delimited=False` when the signature's `{` is found and the level never returns to zero, and `unclosed_brace=True` names that evidence. The page prints "The rest of this declaration could not be delimited: its opening brace was found and its closing brace was not…" and the ellipsis row, and states no count. Pinned by `test_a_method_body_with_no_closing_brace_is_never_rendered_as_complete` over `TRUNCATED_CONTROLLER_TEXT` (a method body with no closing brace), which also asserts no "lines of this declaration" and no "The whole declaration is shown". |
| AC2 | `_declaration_lines()` reports `cut`: `body` when the signature fits and only the body is absent, `cap` when the ceiling stopped before the signature ended. The caption says "The signature is 2 of 6 lines of this declaration… the other 4 lines are the body, which this page does not print", or "The 8-line cap shows 8 of 12 lines… including the rest of the signature". Pinned by the 404-line handler test and `test_a_cap_that_cuts_the_signature_says_the_cap_did_it`. |
| AC3 | Three states, three exact sentences asserted in `test_the_three_states_are_three_different_sentences`, one test per state plus a cross-assertion that neither of the other two sentences appears on the page. Complete: no ellipsis, no count. Trimmed: count + ellipsis. Undelimitable: a stated inability + ellipsis, no count. |
| AC4 | Python uses the declaration's real unit - decorator plus `def`, ending at the parser's `end_lineno` (the dedent). Complete (body on the `def` line) → "The whole declaration is shown."; a docstring-heavy handler → `2 of 35 lines` with an ellipsis and **no** "could not be delimited"; an unparseable file holding the route literal → "The rest of this declaration could not be delimited: the stored file could not be parsed, so this page shows only its beginning…" Pinned by three tests. |
| AC5 | Full suite 1276 passed / 2 skipped; contract suite 37 passed / 2 skipped. The three state goldens were regenerated deliberately from the fixture and are listed above and in `tests/fixtures/product_line/README.md`. |

## Decisions worth a reviewer's attention

1. **An undelimitable declaration has no `total`.** The record's `total` is `None` unless the end
   was established; the renderer therefore cannot print a count for a declaration whose length it
   never learned. The ellipsis row's accessible name changes with the state instead of reusing
   "N lines of the declaration not shown".
2. **"Complete" means the whole *declaration*, not the whole signature.** Since TESTOPS-83 shows
   only the annotation and signature, a normal method with a multi-line body is "delimited but
   trimmed" (state 2), which is true. State 1 is reserved for declarations whose extent is their
   signature (a one-line body, or an interface/abstract `;` declaration). This is why the corpus
   pages the review saw now say "2 of 6 lines", not "The whole declaration is shown".
3. **Python's third state is a file that will not parse.** The AST gives an exact end for every
   declaration it reads, so undelimitable there can only mean the bytes are not parseable; the
   route literal and the `def` directly below it are still evidence of where the declaration
   begins, so the page shows those lines and says the end could not be established. The docstring
   case is emphatically *not* this state: it parses, so it is counted.
4. **The golden comparison normalises CRLF.** `core.autocrlf=true` checks the golden out with CRLF
   while the page renders LF; the old byte comparison failed for a reason that has nothing to do
   with the page. The normalisation is only in the test harness, not in the product.
