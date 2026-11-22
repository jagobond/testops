# TESTOPS-27 build report — 2026-11-22

Branch `factory/testops-27-action-line`. The reviewer's finding on TESTOPS-23/26 was that
`action_line` cut the stored action at the first `"; "` and trusted the tail to be a restatement.
Today every stored tail was one, so the cut was right by luck: an analyser that wrote two orders in
one string would lose the second, and the reader - who believes they hold the whole instruction -
is the one person who cannot detect it.

## The rule (AC1), and where to disagree with it

The rule now lives in `testops/web/app.py`, immediately above the two sets it uses and the
function that applies it (`second_half_is_instruction`), because the ticket asks for it to be
readable by the next person rather than inferred:

1. **Kept when it opens with an instruction verb** - the imperative an analyser uses to tell
   someone to act on a step (`keep one`, `move the step …`, `delete it`). The reader can act on it
   alone.
2. **Dropped when it opens with a word that ties it back to the clause before it** (`this`, `at`,
   `a`, `the`, `which`, `because`, …) **and holds no instruction verb anywhere in it**. Such a tail
   is the reason for the head; on its own it names no one to act.
3. **Everything else is kept.** The rule fails open on purpose. A lost instruction is invisible to
   the reader; a stray explanatory clause is visible and can be skipped. The evidence needed to
   overrule the rule is a stored tail whose verb is not in `INSTRUCTION_VERBS`; that set is where a
   new analyser verb goes when it is written.

The rule is not a claim that the store's tails are always reasons. It is the decision made where
the cut happens, stated so a reviewer can point at a string and say "this one is wrong".

## What the real corpus holds

`data/testops.db`, run `cotw-levels-*`: all 94 level-fitness claims. Three tail shapes exist, one
per verdict that writes a semicolon:

```
distinct   No change: keep the step "…" where it is; this level is the cheapest one that establishes it.
gap        Move the step "…" into a test that drives a browser, or delete it; at this level nothing establishes what it asserts.
unplaced   Rewrite the step "…" … then re-run; a judgement with no comparison in it cannot be checked at any level.
```

All three open with a continuation word and carry no instruction verb, so all three are dropped, as
before. `tests/test_action_line.py` proves each one rather than assuming it: the test reads the
head and the tail out of the analyser's own output, asserts the tail's opening word is one that
points back at the head, asserts no word of the tail is an instruction verb, and asserts the page's
line is the head - so a future analyser that writes an order after a semicolon fails this test
instead of losing it quietly (AC2).

The duplication analyser's claims carry the one tail in the store that is an instruction:

```
Raise this with the team: this copy calls the HTTP client … ; keep one.
```

That was being cut. It is now rendered `… in-process. Keep one.` - two sentences, not a run-on
(AC3). No stored claim of the 94-claim level run changes shape; the store is untouched.

## The two sentences (AC3)

`action_line` joins a kept tail with `. ` and an initial capital, and gives a dropped one a single
full stop. Both shapes have a test, including one through `argument_block` so the check is on the
markup the reader meets, not only on the helper.

## AC4 — the corpus floor

`tests/test_case_scan.py::test_no_action_on_the_real_run_is_cut_into_a_stub`, skipped when the
store is absent like its neighbours, walks all 94 actions of the pinned run and asserts no action is
cut below 40 characters unless the whole action was shorter. The run keeps 53 to 175 characters.

The floor is applied to the part of the stored action the page keeps, and the test says so and
proves why. The page also shortens by referring to the step as "this step", because the step is
quoted directly above the action (TESTOPS-26 AC2): the test asserts the reader's line is *exactly*
the kept head with `the step "<step>"` swapped for the reference, so the shortening is only the
step's own words and no instruction is lost that way. This is why 90 of the 94 actions read
`No change: keep this step where it is.` - 38 characters, all of them the stored head. Applying a
literal 40-character floor to that sentence would fail the product on a complete instruction, and
the only fix available would be to rewrite the analyser's copy, which changes no stored row (the
store is memory) - so the floor is on the cut, and separately on the reader's text wherever the
page did not shorten by reference.

## AC5 — the Gherkin keyword is named as a keyword

`The test asserts Then each fact's …` became `The test asserts the step Then each fact's …` in all
seven places the sentence is built - the four verdicts plus the not-assessable branch - so the
sentence cannot drift per verdict. Read from the stored run, one per verdict:

```
distinct  The test asserts the step Then there is one sheet per entity, and the response the server sends settles it.
unplaced  The test asserts the step Then that count is correct for the store it was run against, but nothing in it says what it is compared with, so nothing settles it.
gap       The test asserts the step Then each fact's citation is in an element reachable by an accessible name, but nothing short of a browser settles it, and the test drives the HTTP API instead.
review    The test asserts the step Then every rendered fact sits in an element carrying a data-fact-id, but the page the server sends settles it, and the test drives a browser to read it.
```

## Verification

- Verdicts: `scripts/replay_levels.py --acceptance` - **94 claims, 90 distinct, 1 unplaced, 1 gap,
  2 review - PASS**, 41 scenarios, 154 bindings (AC6). Unchanged.
- Suite, clean invocation (`env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX
  PYTHONNOUSERSITE=1`):
  - Python 3.12.5 (`.venv`): **295 passed**, 30.2s (277 before, 18 added).
  - Python 3.11 (`uv run --no-project --python 3.11 --with pytest --with-editable . pytest`):
    **291 passed, 4 skipped**, 31.6s. The four skips are the pre-existing pre-3.12 floor checks.
- Both directions were demonstrated to bite, by mutating `second_half_is_instruction` and reverting:
  - always `False` (drop everything): 9 fail, including all six "opens with an instruction" cases,
    the duplicate action reaching the reader, and the two-sentence render.
  - always `True` (keep everything): 8 fail, including the three restatement proofs and the AC4
    corpus floor.
- `tests/test_case_argument.py`'s AC5 assertion was updated for the new sentence shape.

## What it does not solve

- **The rule reads the first word, and an instruction can be written without one.** `Keep one`,
  `keep it` and `then re-run` are covered; a tail such as `it is worth keeping one` opens with a
  continuation word and is dropped - correctly, since it is not an order - but a tail written
  `, and you should keep one` after a comma rather than a semicolon is not looked at at all. The
  cut is only ever at `"; "`, so a store with two orders joined another way is out of scope here
  and belongs to the analyser that would have to write it.
- **The stored analyser copy is still the analyser's.** The page curates it; the analyser's
  duplicate action ("Raise this with the team") reads as a note to the team rather than an
  instruction to the reader. That is a copy ticket, not this one.
- **The 38-character distinct action.** Every distinct claim reads `No change: keep this step
  where it is.` It is the whole stored head; the shortening is the step quoted above it. If the
  Product Owner wants that line to carry more, the analyser's copy is where it has to change, and
  the store's 94 claims would keep reading as they do until a new run.
