# TESTOPS-47 — review (round 2)

Reviewer: second round. Round 1 ran out of budget mid-probe and claimed nothing; this round
re-does the verification with standalone direct harnesses (no pytest, no conftest, no store
guard): the pipeline is driven directly against scratch stores under the reviewer's scratch
directory (`probe47r2.py`, run with the project venv interpreter and env stripped as the
ticket requires). Full probe log: scratch `probe47r2.log`.

## Verdict

**PASS**

## No default

A bare module (`name` only, no `COVER`) was registered as `REGISTERED["fake"]`:

- `cover("fake")` raised `AttributeError: module 'fake_analyser' has no attribute 'COVER'` —
  no default, no borrow.
- A real case row in a copy of the fixture store was re-labelled with the fake analyser and
  `app.case_page` asked to render it: it raised the same `AttributeError` at the page's
  `cover(analyser)` call. A case whose analyser declares nothing cannot be rendered; it does
  not inherit another analyser's contract.

The two real sentences, quoted from freshly rendered pages of a scratch copy of the fixture
store (`case-page-03` duplication, `case-page-01` level fitness):

> A decision covers one duplicated scenario, recognised by its steps and data tables rather
> than the commit; renaming or moving the scenario, or changing the steps in either copy,
> asks you again.

> A decision covers one assertion in one scenario: the same interaction, words, and count of
> identical assertions, in any commit and with any test data; removing an identical assertion
> can let an earlier decision cover again.

The duplication case shows the duplication sentence only and the level case the level
sentence only; neither page contains the other analyser's wording.

## Probes

Level-fitness pipeline runs over one scratch store per probe, repository stubbed in memory
(the `LevelRepo` pattern), decisions recorded with `cases.set_state(..., "resolved", ...)`.

**(a) commit change holds the decision** (re-confirmed from the round-1 direct log,
`probe_direct.log`): decide the lone assertion, change the commit, re-run — identical
fingerprint (`5faec7fd…`), `suppressed` still true, no case raised.

**(b) net-zero twin edit — decide, then re-run.** Two twins (`I4|…label#1@2`, `#2@2`), both
decided; then one identical assertion deleted and another added (count still two, comment
the only file trace). Re-run: every evidence key and fingerprint **byte-identical** to the
first run (`7ae1b735…`, `184fbc30…`), both original decisions still suppress, **no new case
raised**. Is the page's identity claim still TRUE? Yes: the page says the cover is the tuple
(scenario, interaction, words, count of identical assertions); that tuple is unchanged by the
edit, so the decision holding is what the page states, not a contradiction of it. The page no
longer promises "adding or removing … asks you again", so nothing it says is falsified.

**(c) rename the scenario — asked again.** Decide the lone assertion, rename the scenario
("the citation is announced" → "…somewhere else"), re-run: **a new case was raised** — the
fingerprint changed (`5faec7fd…` → `6e3266a4…`), because the fingerprint carries the scenario
reference. The original decision did not silently cover the renamed scenario.

**(d) move the scenario to another file — asked again.** Decide, move
`features/fact_sheet.feature` → `features/elsewhere/fact_sheet.feature`, re-run: **a new case
was raised** — fingerprint changed (`5faec7fd…` → `61bf3f71…`). Same reading: the subject
moved, so the reader is asked again, and the old decision does not cover the moved copy.

## AC4 round trip

Decide the lone assertion (fingerprint `5faec7fd…`); add a twin — two cases raised, correctly
asked again; delete the twin — re-run raises **no case**, the survivor's key is the lone key
again and the **original decision covers it** (suppression row intact). The page's clause
warns the reader **before they click**: the sentence rendered on every level-fitness case
ends "removing an identical assertion can let an earlier decision cover again", so a reader
who resolves the twin case is told in advance that the earlier decision may resume cover.
AC4's choice (surface it, do not key history) is what the page says and what the behaviour
does.

## The 11 goldens

Programmatic strip check, old = pre-ticket golden at `f6f0c02`, new = `HEAD` (the working
tree is identical to HEAD), for all 12 case pages. For each changed page, exactly one cover
paragraph (`<p class="quiet">A decision …</p>`) was found in each version; both substituted
out and the remaining bytes compared: **strip-equal for all 11** (`case-page-01` through
`-08`, `-10`, `-11`, `-12`). `case-page-09` is byte-identical to the pre-ticket golden (no
finding, no sentence). `index.html` and `runs.html` are byte-identical. No file shows
anything else moved.

## Suite

```
env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1 \
  C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe -m pytest -q
561 passed in 94.53s
```

No skips. The first attempt hung: pytest auto-collected round 1's untracked leftover probe
`tests/test_zz_probe47.py` (a direct-harness prototype left in `tests/`, the same pytest
probe that hung round 1 — its `LevelRepo` re-patches `pipeline.db.connect` inside pytest and
never returns). It is not part of the build's commits; it was deleted as reviewer litter and
the clean run above collected without it. Nothing in the product or the build's 8 committed
tests was touched.

## What I did not verify

- The `testops` **lint/prose tooling beyond what the suite covers** — I did not re-run the
  corpus counts against a rebuilt store (the build's Demo Product 94/90/1/1/2 and DemoService 17/17
  pins were taken from the suite's own count tests, which pass).
- The goldens' strip check covers the fixture pages, not a full re-render of every case page
  in a live store.
- Anything outside the five scoped items.
