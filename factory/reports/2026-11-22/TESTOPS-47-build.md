# TESTOPS-47 — build report

Verdict: **each analyser states the cover of its own decision, and the level sentence states
identity instead of promising an event.**

TESTOPS-40 put one sentence on every case page. It was right for the level analyser and wrong twice:
a duplication decision's identity is `duplicate|scenario-name|signature`, not "one assertion… the
same words", and the level sentence promised that adding or removing an identical assertion asks you
again — which a net-zero twin edit (delete one, add another) contradicts, because the count is
unchanged and the decision holds.

The fix is structural, not a second sentence chosen by the page. **The analyser that raises a claim
declares its own cover beside its verdict and action**, the page renders the declaring analyser's
sentence, and there is no default anywhere: a module without `COVER` raises when the page asks for
it. That default — one global sentence — was the bug.

## What changed

| File | Change |
|------|--------|
| `testops/analysers/base.py` | `COVER: str` joins the `Analyser` contract, documented as required with no fallback (AC5). |
| `testops/analysers/level_fitness.py` | Declares `COVER`: the identity — scenario, interaction, words, count of identical assertions — plus the one cover the store cannot prevent (AC2, AC4). |
| `testops/analysers/duplication.py` | Declares `COVER`: its own identity, scenario and signature, and what disturbs it (AC3). |
| `testops/analysers/__init__.py` | `cover(name)` returns `REGISTERED[name].COVER`; no default, no fallback. |
| `testops/web/app.py` | `COVER_SENTENCE` deleted. `decision_form` takes the case's analyser and renders `cover(analyser)`. |
| `tests/test_analyser_cover.py` | 8 tests: registry walk, no-fallback lookup, level identity, net-zero claim, both pages' sentences, AC4 clause and behaviour. |
| `tests/test_decision_cover.py` | The TESTOPS-40 page test now reads `level_fitness.COVER`; its other seven tests are untouched. |
| `tests/fixtures/projects_services/case-page-*.html` | 11 goldens regenerated — sentence only. |
| `factory/reports/2026-11-22/TESTOPS-47-build.md` | This report. |

## AC1 — the declaring analyser's sentence, and only its sentence

`decision_form(conn, row, case_id, findings, row["analyser"])` ends with

```
out.append(f'<p class="quiet">{esc(cover(analyser))}</p>')
```

`cover()` is `REGISTERED[name].COVER`: no `getattr(..., default)`, no module-level sentence to fall
back to. The unregistered-analyser guard already refuses such a case before this line (TESTOPS-35).

Both directions are pinned on real pages rendered from a copy of the any-case fixture store:
`case-page-03` (duplication) shows the duplication sentence and does **not** contain
`level_fitness.COVER`; `case-page-01` (level fitness) shows the level sentence and does **not**
contain `duplication.COVER`. A page cannot show a contract its analyser did not declare.

## AC2 — the level sentence states the identity, not an event

> A decision covers one assertion in one scenario: the same interaction, words, and count of
> identical assertions, in any commit and with any test data; removing an identical assertion can
> let an earlier decision cover again.

36 words, one full stop, under the lint's 45. It names the tuple the suppression key is built from
— scenario, interaction, words, count — and the two things the key deliberately ignores: commit and
test data. It promises no event, so a net-zero edit cannot falsify it.

`test_the_level_sentence_states_the_count_and_promises_no_event` pins the tuple words and asserts
the sentence does **not** contain "asks you again".

`test_the_net_zero_twin_edit_leaves_the_pages_claim_true` runs the ticket's edit over one store.
Decide both twins (`I4|…label#1@2`, `#2@2`), apply the net-zero edit — one identical assertion out,
one in, so the count stays two — re-run: every evidence key and fingerprint is byte-identical to the
first run, both decisions still suppress, and the run raises no case. The page says the cover is
that tuple; the tuple is unchanged, so the page is true. (The two assertions are indistinguishable
by words, so the edit's only trace in the file is a comment above the scenario, which also re-pins
that a moved line is not part of the identity.)

## AC3 — the duplication sentence states its own identity

> A decision covers one duplicated scenario, recognised by its steps and data tables rather than
> the commit; renaming or moving the scenario, or changing the steps in either copy, asks you again.

32 words, one sentence. It states what the key is (`scenario + normalised signature`, data tables
included per TESTOPS-31), what does not disturb it (the commit), and what does (rename, move, a
change to either copy's steps). The duplication page passes the prose lint
(`test_a_duplication_case_shows_the_duplication_sentence_and_not_the_level_one`); no straight quote
survives, because "copy's" would have tripped that rule and was reworded.

## AC4 — the twin-removal cover is stated on the page; the key is not given history

**Choice: surface it.** The level sentence ends "removing an identical assertion can let an earlier
decision cover again." `test_a_decision_recorded_before_a_twin_covers_again_after_the_twin_is_removed`
exercises it end to end: decide the lone assertion, add a twin (asked again, correctly, two cases),
delete the twin — the survivor's key is the lone key again, the original decision suppresses it, and
no case is raised. The wording is true because the behaviour was run, not assumed.

**Why not make the key carry history.** Preventing the resume means the key must depend on
something outside (scenario, interaction, words, count) — a run identity or an edit identity. Any
such ingredient re-keys a decision after every deploy or reformat, which is exactly the behaviour
TESTOPS-40 removed and the Product Owner would not tolerate (a decision would re-ask on every
commit). Every cover this hazard produces is still over identical words, the same interaction and
the same scenario; the risk it was invented to kill — a decision covering changed wording — is not
reached. Stating it costs one clause; preventing it costs the commit-insensitivity the product
promises. Recorded in the analyser's own comment as the reason.

## AC5 — a new analyser cannot inherit another's wording

`test_every_registered_analyser_declares_its_own_cover_sentence` walks `REGISTERED` (not the two
names typed here): every entry must declare a non-empty `COVER`, `cover(name)` must return it, it
must be one sentence under the word budget, and no two analysers may share one wording.

`test_the_page_lookup_has_no_fallback_for_an_analyser_that_declares_nothing` registers a bare
analyser and asserts `cover()` raises `AttributeError`. Together these make the failure mode
impossible: a new analyser without a declaration fails CI and the page, rather than borrowing the
level analyser's contract.

## AC6 — the goldens, verified programmatically

11 of 12 case pages changed (`case-page-09` has no finding and no Decision, so no sentence);
`index.html` and `runs.html` are byte-identical. Method, run against `HEAD` and the working tree:

- for each golden, extract the cover paragraph (the `<p class="quiet">A decision covers …</p>`
  between `</form>` and the debug footnote); exactly one occurrence in the old and new file;
- substitute it out of both and compare the remaining bytes: **equal for all 11**;
- index and runs pages: **byte-identical**.

So each golden's diff is the cover sentence and nothing else. `case-page-03` and `-10` moved from
the level sentence to the duplication one; the other nine keep the level contract in its new
identity wording.

Corpus counts are untouched: CotW **94 claims / 90 distinct / 1 unplaced / 1 gap / 2 review**,
ReqOverflow **17 claims / 17 cases**, pinned by the existing count tests, which pass. Only page text
and a declaration changed; no verdict, key or fingerprint moved.

## Test suite

```
env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
  C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe -m pytest -q
561 passed in 94.23s
```

8 new tests; before this ticket the same tree collected 553. Run against a copy of the CotW build
store placed in this worktree's gitignored `data/` (copied read-only from the main checkout's store),
so the corpus pins ran rather than skipped.

The byte-identical migration test's baseline is regenerated, so it proves the migration leaves the
pages alone but no longer proves the pages did not change — a regenerated golden is a weaker proof
than a captured-before one, as TESTOPS-40's report also recorded. The independent `HEAD`-versus-tree
strip check above is what covers that gap for this ticket.

## What the Product Owner should know

- A duplication case now states the duplication contract, and a level case the level contract; one
  analyser can no longer describe another's decision.
- The level contract is the tuple — scenario, interaction, words, how many identical assertions —
  not a promise to ask again after an edit. A swap that keeps the count keeps the decision, and the
  page now says so instead of contradicting it.
- Removing a twin can restore cover to a decision recorded before the twin existed. The page states
  this; it is the price of decisions surviving every deploy and every reformat.
