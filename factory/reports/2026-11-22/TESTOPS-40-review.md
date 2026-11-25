# TESTOPS-40 review

Reviewer, 2026-11-22. Branch `factory/testops-40-decision-cover`, worktree clean apart from this
report. Full suite, run as required:
`env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1 C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe -m pytest -q`
→ **540 passed in 87.08s** (gitignored Demo Product store present in this worktree, so the corpus pins ran,
not skipped). Every behavioural result below is from my own probes and live pipeline runs over a
throwaway store, not taken from the build report.

## Verdict — PASS

The sentence is on the page, the commit- and data-insensitivity are pinned by tests that fail if
they change, the shifted twin asks again in both directions, the corpus counts are untouched, and
the 11 regenerated goldens differ by the added sentence and nothing else. One promise the sentence
makes is not kept in a narrow case (the net-zero twin edit), and the sentence is shown on pages
whose identity it does not describe — both are reportable, not blocking; see the concerns.

## The sentence vs behaviour (each case)

The sentence, as the reader sees it beside the Decision:

> A decision covers one assertion in one scenario: the same interaction and the same words, in any
> commit and with any test data; renaming or moving the scenario, or adding or removing an
> identical assertion in it, asks you again.

Each clause judged against what the product does. Pipeline runs over one store; decide a case,
apply the edit, re-run. "Holds" = the decided fingerprint stays suppressed and raises nothing;
"asks again" = a fresh case the reader must judge.

| Edit (as a user would do it) | What happens | Promise kept? |
|---|---|---|
| change the commit, re-run | HOLDS — identical fingerprints (`2ee4ba5d…`, `6dcdb9cd…`) before and after | Yes — "in any commit" |
| add a data table under the Given **and** under the assertion | HOLDS — identical fingerprints | Yes — "with any test data" |
| reformat above the assertion (comments at top of file and inside the scenario) | HOLDS — identical fingerprints, lines moved | Yes — implied by "one assertion… same words"; pinned by test |
| rename the scenario | ASKS AGAIN — new fingerprints, 2 fresh cases raised | Yes |
| move the scenario to another file | ASKS AGAIN — the subject carries the file path; fingerprints change | Yes |
| add a second identical assertion (decide the lone, add a twin) | ASKS AGAIN — the lone key is gone (`I4\|…` → `#1@2`/`#2@2`), new cases raised | Yes |
| delete one of two identical (fresh store, either twin decided) | ASKS AGAIN — the survivor's key is no longer the decided one; a case is raised; the decision never moves onto the survivor | Yes |
| reword the assertion | ASKS AGAIN — "same words" is the identity | Yes (implied) |
| **delete one identical assertion and add another in the same edit** | **HOLDS SILENTLY** — total stays 2, keys and fingerprints byte-identical (`2ee4ba5d…`/`6dcdb9cd…`) before and after | **No — the sentence says adding or removing an identical assertion asks again** |
| decide the lone assertion, add a twin, then delete the twin again (round trip) | second removal HOLDS silently — the key returns to the originally decided one | **No — same clause** |

The two broken rows are one hole: the sentence promises a re-ask per edit, but the product's
identity is the *count* of identical assertions, not the edits that produced it. Anything that
leaves the count unchanged — a swap, a round trip — keeps the decision. The build report calls this
the "honest limit" but confines it to the same-position case; the swap is a different shape and the
page does not carve either out. Mitigation: in every failing case the decision continues to cover
an assertion with *identical words, same interaction, same scenario* — the risk the count was
added to kill (covering an assertion nobody judged, wording changed underneath) is not reached.
That is why this is a concern, not a fail.

## Attacking @total

Churn attacks — each must leave a decision covering what it covered. Proven at the analyser level
over a scenario with two identical assertions (A, A) and one different assertion (B):

| Attack | Twin keys/fingerprints unchanged? |
|---|---|
| reword the unrelated assertion B | Yes — `#1@2`/`#2@2` and both fingerprints identical |
| add a prose step (unbound `And the sheet is loaded`) | Yes — the twins' keys and fingerprints identical; the prose step becomes its own new `unplaced` claim, which is a new case, not churn of the decision |
| reorder the non-identical steps (B before the twins) | Yes — same keys, same fingerprints; only the claim list order moves |
| add a third **different** assertion | Yes |
| add a third **identical** assertion | No — re-keyed to `#1@3`/`#2@3`/`#3@3`, new fingerprints: the promised re-ask |

The promised re-ask, reproduced live over a real store: decide the second of two identical
assertions (`#2@2`), delete the first, re-run → the survivor is `I4|…`, its fingerprint is not the
decided one, nothing suppresses it, and the run raises one case. The mirror direction (decide the
first, delete it) also re-asks; on the old key the survivor inherited `#1` and the run went quiet —
that test fails on the reverted analyser, as the build claims (verified, see below).

Mutation check, reproduced: with `testops/analysers/level_fitness.py` reverted to `HEAD~2`,
exactly two of the eight tests fail —
`test_two_identical_assertions_carry_their_occurrence_and_the_count` and
`test_deleting_the_first_twin_never_moves_the_decision_onto_the_survivor` — and with the new key
all eight pass. `testops/` was restored byte-identical afterwards (`git status --porcelain`
empty).

## The 11 goldens

All 11 regenerated goldens checked programmatically, not by eyeball: for each file,
`old_content == new_content` after removing exactly the one added
`<p class="quiet">A decision covers …</p>` string — true for all 11, exactly one occurrence each,
and in each file the sentence sits immediately before the `<p class="code footnote">` element with
the surrounding bytes identical. Nothing else moved in any golden. `case-page-09` (no finding, no
Decision) is untouched, as the build says. The build's own caveat stands and I endorse it: the
byte-identical migration test's baseline is now post-TESTOPS-40 by construction, so it can no
longer catch a page regression that ships alongside a golden regeneration. That is a property of
the situation, not an error in this build.

## Key construction

Grep and read: `level_fitness.py:667` builds `base_key = f"{interaction}|{normalise(step.text)}"`;
`level_fitness.py:702-705` appends `#{seen}@{total}` only when the words repeat in the scenario.
No line, no commit, no data anywhere in the construction. Downstream,
`cases.py:29-30` fingerprints `analyser|subject_ref|evidence_key` where `subject_ref` is
`scenario:{path}#{name}` — which is exactly why rename and move re-ask.

Tested, not read: my probes show identical fingerprints after (a) comments added at the top of the
file and inside the scenario above the assertion (lines moved), and (b) a 40-bit commit change; and
different fingerprints after rename and move. The build's
`test_reformatting_a_scenario_with_twins_keeps_their_occurrence_keys` pins the same and asserts the
fixture really moved the lines.

## Counts

Demo Product **94 claims / 90 distinct / 1 unplaced / 1 gap / 2 review** — pinned and passing
(`test_action_prose.py` AC5, `test_case_scan.py` pins over the real store). DemoService
**17 claims / 17 cases** — pinned and passing (`test_duplication_v2.py`). All 56 tests in the three
count-pinning modules pass; the full suite is 540, matching the build.

## Three sharpest concerns

1. **The sentence over-promises on net-zero twin edits.** Delete one identical assertion and add
   another in the same edit (or add-then-remove across edits): the count is unchanged, the keys and
   fingerprints are byte-identical, and the decision holds silently — while the page's own words
   say "adding or removing an identical assertion in it, asks you again". The truthful contract is
   the tuple (scenario, interaction, words, count of identical assertions); the page should state
   the identity, not promise a re-ask per edit. `COVER_SENTENCE` lives in `testops/web/app.py`, so
   the amendment needs its own ticket.
2. **The sentence is shown on cases whose identity it does not describe.** It is rendered beside
   the Decision on every case with a finding, including the duplication analyser's cases (goldens
   03 and 10). A duplication decision's identity is `duplicate|scenario-name|signature` — nothing
   about "one assertion… same interaction and same words". On those pages the sentence is simply
   not the contract the reader is entering, in both directions.
3. **An older decision can silently resume cover after twin churn.** In one store: decide the lone
   assertion, add a twin (asked again, correctly), then delete the twin — the survivor's key is
   again the lone key and the *original* decision covers it with no new case. Also: decide the
   first twin, delete it, and a stale lone-key decision from an earlier shape of the file swallows
   the re-ask. Every such cover is over identical words in the same scenario, so the risk is low —
   but it means "asks you again" is not guaranteed even for the ticket's own edit sequence once the
   store carries history. Worth a line in the eventual contract wording.
