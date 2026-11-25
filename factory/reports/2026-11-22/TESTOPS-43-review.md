# TESTOPS-43 review — a sentence that hides its own partial reads

Reviewed 2026-11-22 against branch `factory/testops-43-partial-reads` (af84327), tree clean.
Suite: `env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1
C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe -m pytest -q` → **456 passed, 1 failed**.
The one failure (`test_every_case_page_and_the_indexes_are_byte_identical_after_the_migration`,
differs at byte 59, `\n` vs `\r`) reproduces identically on a `main` worktree checked out the same
way — it is a CRLF fixture artifact of this environment, not this branch. All evidence below is
from probes I built myself against the real `pipeline._readings`, a real `Registry`, the real
`could_not_read_lines` renderer, and the live store; none copied from the build report.

## Verdict — PASS

The zero-hiding aggregate now names each capability when a capability returned nothing or lost
files; a fully-read run still renders the old short sentence; every skip appears on the run page
whatever the verdict; the live Demo Product and DemoService sentences are byte-identical to `main`'s.
Three opacity margins remain, listed below; none is the fault the ticket named.

## Sentences rendered (three stores, quoted)

Built as in-memory `Collected` arms through the real `pipeline._readings` and `Registry.assess`,
and rendered with `Assessment.sentence()`; the skip section rendered with the real
`could_not_read_lines` (tags stripped).

**Store 1 — code reads 0 of 40 (all unsupported), test code reads 12.** State `not_assessable`.

> Cannot assess this claim: code was not read: 40 .java files in the product repository were
> skipped because .java is not a kind this collector reads (unsupported kind), so no product code
> file was fetched; test code was consulted and returned 12 items.

A reader can name the loss without clicking: which capability lost, which kind, how many, why.
The run page also renders "Files this run could not read — The repositories hold 40 files in 1
kind that this run did not fetch. … 40 .java in the product repository — unsupported kind" with
the 40 names behind the disclosure.

**Store 2 — code reads 40, skips 500 `.sql` (unsupported), test code reads 12.** State `found`.

> Assessed: code and test code were consulted and returned 52 items.

The sentence itself is silent about the 500 — by design: `.sql` is a kind no reader here ever
had, so it is not the capability's loss (that separation is argued in `Reading`'s docstring and
I accept it). But the reader can still name the loss without clicking: the run page now renders
the skip section for every run that skipped anything, whatever the verdict —

> Files this run could not read
> The repositories hold 500 files in 1 kind that this run did not fetch. Nothing in this run says
> what they contain, so nothing here counts them as consulted.
> 500 .sql in the product repository — unsupported kind. [Name them: db/M0.sql … db/M499.sql]

That is AC3: the skip was recorded in the store and is now on the page, always.

**Store 3 — code reads 30 of 40 (10 `.cs` over the size cap = lost), test code reads 12.**
State `found`.

> Assessed: code and test code were consulted and returned 42 items (10 .cs files unreadable).

The partial read is named in the sentence with a count — see concern 2 for what a reader can
and cannot derive from it. The run page also lists the 10 `.cs` names. Assessing `code` alone
gives the fully explicit form: "Assessed: code was consulted and returned 30 items (10 .cs files
unreadable)."

**Cross-check (the ticket's own 2-and-0):** code a real readable zero, test code 2 →
"Assessed: code returned 0 items; test code returned 2 items." The 2-and-0 and the 1-and-1 can
no longer be confused.

## AC4 diff (both strings)

I checked out `main`'s `testops/sources.py` to a temp file, imported both modules side by side,
and rendered identical assessments under each — legacy no-readings records, readings-without-
skips records, a zero record, and the live store's own snapshot registries (Demo Product r9–r11,
DemoService r6–r8, both `needs` and `consults` per analyser). Every pair IDENTICAL. The strings:

- Demo Product r11 `level_fitness.needs` —
  main: `Assessed: code and test code were consulted and returned 95 items.`
  branch: `Assessed: code and test code were consulted and returned 95 items.`
- DemoService r8 `duplication.needs` —
  main: `Assessed: test code was consulted and returned 158 items.`
  branch: `Assessed: test code was consulted and returned 158 items.`
- `consults` rows (blocked Jira/ADO sentences) identical in full, quoted in the probe output.

Mechanism verified: the new `note` suffix is `""` when no reading lost anything, so the
zero-skip f-string reproduces `main`'s string byte for byte. AC4 holds.

## Prose

Read aloud: all three sentences stay one sentence, none becomes a paragraph. Store 1 is long
(40 words) but is a single clause chain a tired reader can follow to the semicolon. "Consulted"
survives only where it is no longer misleading: in store 2 "consulted" is now true without
caveat about what the capabilities read, and the 500 sit in their own labelled section; in
store 3 "consulted and returned 42 items (10 .cs files unreadable)" carries the loss in the
same breath. Vocabulary: no "capability", no "arm"; "kind" survives in the page copy ("in 1
kind", "3 other kinds unreadable") — it is mild jargon but it names a real grouping and the
count carries the meaning even if the word is skipped. AC6 holds.

## Template check

There are no templates: the web surface is server-rendered Python. Grep for `.html`,
`jinja`, `template` over `testops/` finds nothing. The assessment sentence is built exactly
once, in `sources.py` (`queries.py:337` and `queries.py:604` call `assessment.sentence()`),
and `app.py` embeds the stored string verbatim (`esc(assessment["sentence"])`). The
"Files this run could not read" copy is built in `app.py`, but that is the skip section's own
page copy (AC3's), not the capability sentence AC5 guards. AC5 holds.

## Three sharpest concerns

1. **The aggregate still hides the per-capability split whenever nothing is zero and nothing
   was lost.** Store 2's sentence says "returned 52 items"; a reader cannot tell 40-and-12 from
   24-and-28 without the single-capability view, which the run page does not render. AC1 read
   literally requires the split always; the build splits only when an aggregate would hide a
   zero or a loss. That is a defensible reading of the ticket (the finding was the 2-and-0),
   and I pass it — but the margin is one skipped-.cs file away from mattering, and a later
   ticket that widens the split trigger should decide it once, not case by case.
2. **In a partial aggregate, the parenthetical rides on the total, and the subtraction lies.**
   Store 3: "returned 42 items (10 .cs files unreadable)" — 42 includes test code's 12, which
   lost nothing, so the reader who computes 42 − 10 = 32 gets the wrong read count (the truth is
   30). AC2 asks for "how many files were read"; the sentence gives a total and a loss, and the
   read count is only correct in the per-capability sentence the page never shows. The honest
   forms are "code returned 30 items (10 .cs files unreadable); test code returned 12" (the
   ticket's own note) or a split triggered by any `lost` entry, not only by a zero.
3. **The skip list is unbounded.** `could_not_read_lines` emits one `<li>` per skipped file with
   no cap; a repository whose tree holds thousands of unsupported files puts thousands of list
   items on the run page. The counts and reasons are capped by design (one line per kind); the
   disclosure is not. A limit with an explicit "and N more in the store" would keep the page
   honest and renderable.
