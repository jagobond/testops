# TESTOPS-52 build — uncertainty does not wear certainty's clothes

Worktree `C:/Users/<name>/Projects/testops-t52`, branch `factory/testops-52-verdict-tone`.
Interpreter for every command: `env -u PYTHONPATH -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe`.

## What changed

- **`testops/web/tone.py` (new).** The one declaration of a verdict's tone:
  `VERDICT_TONE` maps every name the store accepts — current (`distinct`, `review`, `gap`,
  `duplicate`, `unplaced`) and retired (`necessary`, `optimal`, `overbuilt`) — to `alarm`, `soft`
  or `settled`; `NOT_ASSESSABLE_TONE = SOFT` covers a claim whose sources could not be consulted;
  `_CLASS_SUFFIX` maps tone to rendered class explicitly (`""`, `" soft"`, `" hot"`). `tone_of` has
  **no fallback**: an undeclared name raises rather than being dressed as settled.
- **`testops/web/app.py`.**
  - `argument_block` (the case page's `<strong class="verdict …">`) now takes its tone from
    `tone.py`. "Cannot assess" is `verdict soft`; an asserting verdict is `verdict hot`; a settled
    one is `verdict`.
  - `verdict_badge` (the list badge) now uses the same declared tone, replacing the default
    `verdict not in LIST_JUDGEMENT or verdict == "unplaced"` rule.
  - CSS: added `.badge.verdict.hot` and `p.judgement strong.verdict.soft` (dim + dashed underline);
    the pre-existing dashed `.badge.verdict.soft` is now actually rendered.
  - The three surviving `class="badge{hot}"` sites (runs index, run header, run-page case rows)
    now build the attribute through `badge_classes(label, hot)`. `hot` is passed by the caller at
    every site; no page inherits a default.
- **Tests.** `tests/test_verdict_tone.py` (AC1–AC3, 15 tests) and `tests/test_page_markup.py`
  (AC4, 2 tests). `tests/test_claim_headline.py` updated for the intended tone change: a `gap`
  badge now genuinely wears `hot` (it used to be plain, which was the bug's other half).
- **Goldens.** The 14 pages in `tests/fixtures/projects_services/` regenerated.

## AC evidence

| AC | Evidence |
|----|----------|
| AC1 | Tone declared once in `tone.py`; `test_conclusion_and_certainty_are_toned_apart` pins soft for `unplaced`, alarm for `gap`/`review`/`duplicate`/`overbuilt`, settled for `distinct`/`necessary`/`optimal`; `test_an_undeclared_verdict_is_an_error_not_a_default` pins that there is no catch-all. |
| AC2 | `test_every_verdict_the_store_accepts_has_a_declared_tone` iterates `verdicts.ever_emitted(conn)` from a store this build created (current **and** retired) and fails on any untoned name; `test_the_declared_tones_are_exactly_the_stores_vocabulary` fails on stale entries; `test_the_analysers_emit_only_current_verdicts_and_all_of_them_are_toned` crosses the analyser AST scan with the store's vocabulary. |
| AC3 | On the store copy, `/case/case-demo-booking-levels-20261123T132456-04` serves `<strong class="verdict soft">Cannot assess</strong>`; `/case/case-demo-service-dup-20261122T205100-17` serves `<strong class="verdict hot">Checked, but this repeats another test</strong>`. `test_cannot_assess_does_not_share_a_class_or_colour_with_a_settled_verdict` parses the case pages with `html.parser` and asserts the class **sets** differ, the inconclusive one has `soft` and not `hot`, and the settled one has neither. |
| AC4 | The test parses front, runs, run, case and config pages with `html.parser`, rejecting duplicate `class` attributes, ill-formed attribute names, `class=` inside a class value, and class values that are not simple token lists; it also asserts badges carry the tone their state intends. **Before the fix**, run against a server serving a *copy* of the store with the templates from `HEAD` (`git show HEAD:testops/web/app.py`), it reported **522 malformed-attribute problems across 46 pages** (`runs`: `ill-formed attribute name 'hot""'`, `class value 'badge class='`) — 261 malformed tags, well past the 32+ the author saw (the crawl reached 40 run pages; the live front page links only 3 case pages, so there are many more). **After the fix** the same scan reports **0** on the same store copy. |
| AC5 | `TESTOPS_BASE=http://127.0.0.1:8898 pytest tests/contracts -q` (the suite reads the env var `TESTOPS_BASE`; there is no `--base-url` option): **21 passed, 5 failed, 3 skipped**. `P04` now **passes**. The 5 remaining failures are the pre-existing ones from the TESTOPS-7 first run (`P05_case_links_back_to_its_run`, `P05_config_page_is_reachable_from_the_front_page`, `P07`, `P10`, `P23_password_in_free_text_field_is_refused` — TESTOPS-51's remit). Nothing regressed: the only change in failures is P4 moving from FAIL to PASS. No live server was used: the server ran on 127.0.0.1:8898 with `TESTOPS_DATA` pointing at a copy (`scratch/store52`, db + blobs). |
| AC6 | Full suite with `TESTOPS_BASE` on the copy: **660 passed, 5 failed (the contract failures above), 3 skipped, 668 collected**. Goldens: 14 pages regenerated; a text-stripping comparison of every old/new golden shows **visible text identical on all 14 pages** (no wording, numbers or layout moved). The diff is the two CSS rule blocks plus `class="badge class="hot""` → `class="badge hot"` and verdict headlines gaining `soft`/`hot` where the declared tone says so. No analyser code touched; `tests/test_action_prose.py tests/test_case_scan.py` — 46 passed, pinning Demo Product 94/90/1/1/2 and DemoService 17/17. |

## Notes for the reviewer

- **Evidence file.** The ticket points at `factory/reports/2026-11-23/TESTOPS-7-review.md`; that
  file does not exist in this tree. The evidence was read from
  `factory/reports/2026-11-23/TESTOPS-7-author-report.md` — failure 1 ("P4 reproduced", including
  the verbatim assertion and both case ids), and the "Harness notes" paragraph naming
  `<span class="badge class="hot"">` — plus the delivered suite in `tests/contracts/`.
- **Disclosure — accidental live write, reverted.** `pytest` as a whole runs `tests/contracts`,
  whose default base is the live server `http://<tailnet-address>:8791`; the suite's session fixture
  POSTs a `contract-audit-<timestamp>` project (there is no project-delete endpoint). Two early
  full-suite runs in this session used that default and added
  `contract-audit-20261123140617` and `contract-audit-20261123141010` to the live store. Both had
  zero referencing services and zero cases; I deleted exactly those two rows (no other row
  touched), and the live `project` table is back to
  `demo-product`, `demo-service`, `demo-booking`, `testops`. Every later run was pointed at the copy.
  The ticket's "do not write to the live store" was not honoured on those two runs; the cause is
  the suite's default, not a change in this ticket, but it is recorded here rather than hidden.
- **P4's wording dependence.** The contract suite finds the uncertain and settled verdicts by
  text (`cannot assess|unplaced` vs `checked|placed`), so it would pass on a page that hid the
  tone. That is why AC1–AC3 are pinned by the new in-repo tests structurally as well; P4 is
  treated as the external witness, not the specification.
