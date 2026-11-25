# TESTOPS-77 build — a refusal is only honest if its reason is true

2026-11-24, worktree `C:/Users/<name>/Projects/testops-t77`, branch
`factory/testops-77-reasons`. Store: the worktree's own `data/` was read only; the corpus was read
from the cached checkout, and pages were rendered from a **copy** of the scratch store. Port 8791
was never opened and the live store was never contacted.

Suite: **1220 passed, 2 skipped** (`pytest -q`, project `.venv`, `PYTHONPATH`/`PYTHONHOME`/
`VIRTUAL_ENV`/`CONDA_PREFIX` stripped, `PYTHONNOUSERSITE=1`; baseline before this ticket was 1211
passed). Contract suite alone: **37 passed, 2 skipped**. Nine new tests are in
`tests/test_java_honesty.py`; one existing assertion changed because the wording it pinned was the
defect (the interface case), and two new fixtures cover the code-position shapes.

## What changed

| file | change |
|---|---|
| `testops/surfaces/discover.py` | `_declared_type_names` now reads the lexer's token stream instead of a regex over comment-stripped text: comments, string/char literals and text blocks are consumed first, so only a type keyword in code position (followed by a name, not preceded by a dot) counts. `_inherited_prefix` takes the kind (`superclass`/`interface`) and picks the noun in the reason; a name held more than once is refused as ambiguous, and a file that does not lex but declares the type is reported as held-but-unread. A new `_refusal` combines several failing sources so the sentence is true of all of them, and the two-prefix case no longer claims anything was not read. |
| `testops/surfaces/java.py` | Reason vocabulary: `REASON_PREFIX_NOT_READ` (superclass), `REASON_INTERFACE_NOT_READ`, `REASON_TYPE_AMBIGUOUS`, `REASON_PREFIX_SOURCES_UNREAD`, `REASON_PREFIX_MULTIPLE`. No ticket id or criterion number in any of them. |
| `tests/fixtures/java/LiteralMentionOnly.java` | An unlexable file whose only mention of `PhantomBase` is inside a string and a comment; it really declares `LiteralMentionOnly`. |
| `tests/fixtures/java/UnlexableBase.java` | An unlexable file that really declares `UnlexableBase` — the held-but-not-read case. |
| `tests/test_java_honesty.py` | Nine tests: code-position reading, literal-vs-declaration, the four refusal shapes, and the page-wide ticket-id grep. |

## Criterion by criterion

| id | what was done, and the evidence |
|----|----------------------------------|
| AC1 | `_declared_type_names` calls `java.lex` and harvests only `word` tokens in `TYPE_KEYWORDS` followed by a `word`, skipping `Foo.class`. `test_declared_type_names_come_from_the_lexer_not_from_literals_or_comments` pins the literal fixture to exactly `["LiteralMentionOnly"]`; `test_a_superclass_named_only_in_prose_...` pins that the child's refusal says "does not hold" for `PhantomBase`, not "holds but this reader could not read"; `test_a_superclass_really_declared_by_an_unlexable_file_is_held_and_says_so` pins the real-declaration side of the same branch. |
| AC2 | All four shapes pinned. Superclass: reason names the superclass, detail names `MissingSuperclass`. Interface: `REASON_INTERFACE_NOT_READ`, reason says "interface", never "superclass"; detail names `MissingApi`. Ambiguous: a name declared by `one/BaseController.java` and `two/BaseController.java` is refused as `REASON_TYPE_AMBIGUOUS`, detail names both files. Both-at-once, nothing missing: two inherited prefixes are `REASON_PREFIX_MULTIPLE`, detail names the superclass **and** the interface, and asserts neither "does not hold" nor "was not read" appears. Both-at-once, both absent: the detail names both types with their kinds. |
| AC3 | `test_no_reason_a_page_renders_names_a_ticket_or_a_criterion` asserts every exported `REASON_*` string, every rendered unread reason and detail, and the page's reader text contain no `TESTOPS-` and no `AC\d`. (CSS comments in `<style>` do name tickets; they are not reader text, and `lint.reader_text` excludes them.) |
| AC4 | Reproduced over the corpus checkout (142 `.java` files): state `found`, **142 parsed, 25 surfaces, 0 unread, 0 inherited, 14 distinct targets** — unchanged. No corpus file exercises either path: no controller in the corpus extends an unmapped type, and no type name appears only in a literal in a file that fails to lex; the fixtures do. |
| AC5 | Full suite and contract suite green. No case-page golden or fixture HTML changed (`git status` is source + tests only), and the byte-identical golden test passes in the suite. Stored run pages: the seven pages of the pinned run `demo-booking-levels-20261124T100624` (index, runs, run page, four case pages) were rendered from copies of the scratch store with the pre-ticket package (`git archive HEAD`) and with this branch, and the two manifests are **identical**, page for page. |

## Decisions worth a reviewer's attention

1. **The reason is data, so the noun lives in it.** An interface-borne refusal must not say
   "superclass": the kind now travels into `_inherited_prefix` and selects the reason, so pages
   group by a sentence that is true of the entries under it. No page needed a renderer change.
2. **Ambiguity is not absence.** A type held more than once is `REASON_TYPE_AMBIGUOUS`, with both
   files named in the detail so a reader can go and look. It is not "does not hold" and it is not
   "was not read".
3. **The both-at-once case names neither as missing.** Two inherited prefixes with nothing absent
   says exactly that (`REASON_PREFIX_MULTIPLE`) and names both types; two absent types name both.
   Neither sentence borrows the superclass wording that started this ticket.
4. **Several refusals are one sentence, not the first one.** When more than one inherited type
   cannot be read, the reasons are combined: one shared reason stays the summary, otherwise the
   summary names no single type and the detail names each with its kind.
5. **Code position, not "not obviously prose".** Reusing the reader's own lexer means the rule is
   the same one that already stops `"@GetMapping"` in a string being a route — one lexing model,
   not a second regex that can drift from it.

## Store and network

No port was opened (pages were rendered by calling the app directly against store copies), port
8791 was never contacted, the live store was never opened, and no credential was written or
printed.
