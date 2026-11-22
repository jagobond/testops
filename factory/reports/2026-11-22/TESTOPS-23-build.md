# TESTOPS-23 build report — 2026-11-22

Branch `factory/testops-23-copy`, built from `feature/f1` at 18814b9. The Product Owner read
`case-cotw-levels-20261122T011316-03` and said the verbiage was "still not right" but could not say
why. The ticket's answer is that the page narrated the analyser; this build makes it tell one
argument, and makes the rule that produces that argument work for any claim.

## The diagnosis, as one fault

The seven named faults are one: **the page narrates the analyser instead of telling the reader one
argument.** It restated the claim three times, spent a numbered section on the provenance of a
heading, wrote sentences about "the words" a rule had read, headed paragraphs with fragments, called
one actor three things, badged an absence ("Browser not needed") and presented the scenario's other
steps as equal-weight support.

## What changed

**`testops/web/app.py` — the case page is one argument, said once.** The page now has five
sections:

1. **What is asserted, and what settles it** — one paragraph. It opens with the verdict, quoted the
   asserted step with its Gherkin keyword, states the fact that settles it, states what the test
   does about that (and, for a review claim, the cost), and ends with the stored action. Nothing is
   repeated: the quote appears once in prose and the action is not re-narrated.
2. **The step that is asserted** — the feature excerpt with the line marked, and the step
   definition that runs it, both read from the stored blobs.
3. **The other steps in this scenario, for context** — one group, introduced together, and it says
   in words that they are not evidence. When they share an instrument the intro says it once
   ("each of them uses a browser") instead of ending every line with the same clause.
4. **What could not be checked** — unchanged sentences; absence is still a state.
5. **Decision** — the same decision form, once per case.

The argument is built by a rule (`argument_middle`, `_settles_clause`, `_does_clause`,
`verdict_label`), not written for one claim:

| verdict | the middle sentence, from the stored row |
|---|---|
| distinct | "That is settled by {label}, and the test {instrument}." |
| review | "That is settled by {label}, and the test {instrument}, which is a dearer way to reach it." |
| gap | "Nothing but a browser settles it, and the test {instrument}." or "Nothing reaches what would settle it, and the test {instrument}." |
| duplicate | "That is settled by {label}, and another scenario in this run already asserts the same thing, so the project runs it twice." |
| unplaced | "Nothing in that assertion says what it is compared with, so nothing settles it. The test {instrument}." |

Provenance (scenario title, `file:line`, commit, permalink) is now a labelled footnote
("Where this comes from:") directly under the quoted assertion, not section 2. Scenario titles are
still labelled as the author's own name for the scenario, not a requirement.

`established_by` — the rule in its own vocabulary — is no longer rendered anywhere. Where the rule
matters the page states the fact it found ("That is settled by the page the server sends").

The `statement` field — the analyser's essay — is no longer rendered on the case page or the home
list. The home list now shows the asserted step (in the test's words) and falls back to the stored
statement only for v1 claims. Without that, the first screen a reader meets still said "The run only
reads the responses the server sends…".

Gherkin keyword: the quote comes from the stored feature line, so it reads "Then each fact's
data-fact-id is the same on both loads". An `And`/`But` assertion is quoted as `Then`, because out
of context those words continue a sentence the reader cannot see; the excerpt below still shows the
line exactly as the file holds it.

The pass note (a scenario whose assertions need different things) is reworded for the page from
stored counts (`pass_labels`), and `queries.pass_note_from_rows` is unchanged for any caller that
wants the analyser's own sentence.

**`testops/queries.py`** — `_evidence_item` carries `layer`; `_attach_pass` carries `pass_labels`;
`latest_per_analyser` carries `assertion` / `case_assertion`. No claim row is read differently; the
verdict set cannot move.

## Verdicts unchanged

`scripts/replay_levels.py --snapshot cotw-levels-20261122-a3f19853-r6 --acceptance`:

```
94 claims, 90 distinct, 1 unplaced, 1 gap, 2 review — PASS
41 scenarios and 2 of them explaining more than one label
```

## Evidence

Suite, clean invocation (`env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX
PYTHONNOUSERSITE=1`):

- Python 3.12.5 (`.venv`): **241 passed**, 28.7s. 220 before this ticket, 21 added.
- Python 3.11.15 (`uv run --no-project --python 3.11 --with pytest --with-editable . pytest`):
  **237 passed, 4 skipped**, 28.6s. The four skips are the pre-existing pre-3.12 checks.

Corpus prose lint (the ticket's AC8 lint, `tests/test_case_argument.py::lint`) over **every one of
the 94 claims of the real run**, each claim rendered through `app.case_page` from a scratch copy of
`data/testops.db` (the product store is never written):

```
claims in run: 94
pages linted: 94
pages failing the lint: 0
```

The lint fails a page for: "the words"; analyser narration ("classified this way", "the assertion is
about", "answers to one run", "the run only reads/drives"); a retired verdict label; a fragment
pseudo-heading (`<p><strong>Label.</strong>`); a double space; a sentence over 45 words; the quoted
assertion appearing more than once in prose. The suite runs the same lint over a real pipeline run
(every claim, including distinct ones that raise no case) and over one seeded case per verdict.

## What it does not solve

- **Stored analyser copy is still analyser copy.** `statement`, `established_by` and
  `proposed_action` are generated by the analysers and are unchanged; the page stops re-serving two
  of them but still renders the proposed action verbatim (semicolon clauses are split into
  sentences at render time, which is the one shaping it gets). Rewriting them belongs to the
  analyser tickets, and would move stored claim text.
- **The action can carry product jargon.** "At this level nothing establishes what it asserts" is
  the analyser's phrase for the testing level. It is not footnoted or explained; a reader infers it
  from the header ("Level fitness") and the preceding sentence.
- **No browser was available to the suite.** Read-aloud was done on the rendered text; the layout
  (verdict in bold, footnotes as small print) is asserted structurally, not measured.
