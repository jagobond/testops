# TESTOPS-9 — build report

Verdict: **implemented, suite green (514 passed, 0 skipped), no behaviour change, no migration.**
The three documented verdict lists now name exactly what the analysers emit, and
`tests/test_verdict_vocabulary.py` fails in both directions if they drift again.

## The defect, as it actually stands in this tree

The ticket names three places and says `testops/store/schema.sql` carries "column comments and a
CHECK mentioning `optimal` / `overbuilt` / `necessary`". Two of those are accurate; the CHECK is not
there and never was.

The real stale descriptions were:

| Place | Stale text |
|-------|-----------|
| `testops/store/schema.sql:69` | `verdict TEXT NOT NULL, -- optimal \| overbuilt \| necessary \| unplaced \| duplicate` |
| `testops/analysers/base.py` (`Claim` — no docstring existed) | `verdict: str  # optimal \| overbuilt \| necessary \| unplaced \| duplicate` |

The analysers emit `distinct`, `gap`, `review`, `unplaced`, `duplicate`. The "three places" are two
files and three lists: the schema column comment, a `Claim` docstring (added by this ticket, because
the dataclass had none to correct), and the field comment beside `Claim.verdict`.

### The CHECK constraint: before / after

**Before — absent.** `grep -n "CHECK" testops/store/schema.sql` on the branch head lists five
constraints, none about verdicts:

```
89:  CONSTRAINT claim_v2_requires_provenance CHECK (
102:  CONSTRAINT claim_sources_assessed_pairing CHECK (
181:  type TEXT NOT NULL CHECK (type IN ('git_repo', 'jira_board', 'ado_pipeline')),
182:  role TEXT NOT NULL DEFAULT '' CHECK (role IN ('', 'product', 'test')),
183:  name TEXT NOT NULL CHECK (length(trim(name)) > 0),
189:  CONSTRAINT service_role_for_git_repo CHECK (
```

**After — still absent, deliberately.** There is no verdict CHECK to paste before/after. I checked
every local and remote ref (`git grep "verdict IN\|CHECK *(verdict"` across `refs/heads` and
`refs/remotes`) and the full history of the file (`git log --all -S"overbuilt" -- testops/store/schema.sql`
→ only `c67954b` "Baseline"), so no branch ever carried one. I did not invent one:

- AC4 forbids touching stored rows, and the live store holds **128 claims under retired names**
  (`overbuilt` 67, `optimal` 36, `necessary` 25). A CHECK would reject rows that are the product's
  memory; SQLite cannot add a table constraint to an existing table anyway, so enforcing one would
  require a migration this ticket explicitly forbids.
- AC3 forbids behaviour change. A CHECK is behaviour; a comment is words.
- The guard the ticket actually asks for is the test, and it now exists.

### The schema line, before / after

Before:

```sql
  verdict TEXT NOT NULL,                   -- optimal | overbuilt | necessary | unplaced | duplicate
```

After:

```sql
  verdict TEXT NOT NULL,                   -- distinct | gap | review | unplaced | duplicate
```

Plus a paragraph above `CREATE TABLE claim` saying the vocabulary is the analysers' own, naming the
test that enforces it, and recording that pre-vocabulary rows keep retired names and are read, never
rewritten (pointing at `LEGACY_JUDGEMENT` in `testops/web/app.py`). The retired names are not listed
there on purpose — a list is what goes stale.

## What changed

| File | Change |
|------|--------|
| `testops/store/schema.sql` | Verdict column comment corrected to the emitted set; note above the table explaining the vocabulary and the retired-name rows. |
| `testops/analysers/base.py` | `Claim` gains a docstring with a `Verdicts:` line; the `verdict` field comment corrected. |
| `tests/test_verdict_vocabulary.py` | New. Reads the emitted set from the analysers by AST and compares all three documented lists to it. |

No analyser logic, pipeline, query, renderer, scoring or schema structure changed. No migration.

## How the test reads the emitted set

`emitted_verdicts()` parses every `testops/analysers/*.py` with `ast` and collects the string
literals in the two shapes a verdict actually takes:

- `verdict = "..."` (the level analyser's four assignments),
- `Claim(..., verdict="...")` (the duplication analyser, and a literal passed directly).

`Claim(..., verdict=verdict)` passes the local already covered by the assignment scan and is skipped
explicitly. Any *other* non-literal verdict raises, so a builder cannot make the scan quietly check a
smaller set than the code emits. The set is therefore what the code can write, not what one fixture
happened to exercise.

Each documented list is extracted by one anchored regex per place, so a place that stops documenting
its verdicts fails rather than silently contributing an empty set. The comparison is equality, reported
as two named differences:

```
stale         = documented - emitted   -> "names verdicts no analyser emits"
undocumented  = emitted - documented   -> "does not document verdicts the analysers emit"
```

## AC2: both directions fail, demonstrated

Direction 1 — I temporarily added `overbuilt` to the schema comment:

```
AssertionError: schema.sql verdict column names verdicts no analyser emits: ['overbuilt'].
The analysers emit ['distinct', 'duplicate', 'gap', 'review', 'unplaced'].
1 failed, 4 passed
```

Direction 2 — I temporarily removed `duplicate` from the schema comment:

```
AssertionError: schema.sql verdict column does not document verdicts the analysers emit: ['duplicate'].
It documents ['distinct', 'gap', 'review', 'unplaced'].
1 failed, 4 passed
```

Both mutations were reverted; `git diff` shows only the intended changes. A third test,
`test_the_comparison_reports_both_directions`, pins the comparison itself with synthetic sets, and
`test_the_analysers_emit_a_vocabulary_at_all` stops a broken scan from making the comparisons vacuous.

## Acceptance criteria

| id | evidence |
|----|----------|
| AC1 | `tests/test_verdict_vocabulary.py::test_documented_verdicts_are_exactly_the_emitted_ones` runs once per place (schema column, `Claim` docstring, field comment). Each documented set equals the AST-read emitted set. |
| AC2 | `test_the_comparison_reports_both_directions`, plus the two live mutations recorded above with their exact failure output. |
| AC3 | Full suite `514 passed, 0 skipped` (including the corpus arms below). CotW levels: 94 claims with `{"distinct": 90, "unplaced": 1, "gap": 1, "review": 2}` (`test_action_prose.py::test_the_corpus_still_carries_the_verdicts_the_ticket_pins`). ReqOverflow duplication: 17 claims / 17 cases / 17 findings (`test_duplication_v2.py`, five separate assertions). |
| AC4 | No migration, no writer path touched. The measurement copy of the store is byte-identical to the live one (`sha256 99f30117419ce8a2e7baba5bc11b66e7b795040828a7ce777e782e865d488d65` both), and the live store's mtime is unchanged (`2026-11-22 21:17:00`). All 2,310 claim rows remain, including the 128 retired-name rows. |

## Test runs (from the worktree, main checkout's interpreter)

```
$ env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1 \
    C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe -m pytest -q
514 passed in 97.40s (0:01:37)
```

The corpus tests skip in a clean worktree because `data/` is gitignored and holds the build's store.
To make the AC3 counts verifiable here, I copied `data/testops.db` and `data/blobs/` from the main
checkout into this worktree's (gitignored) `data/`. The suite's store guard permits only `?mode=ro`
access, and the copy's hash matches the original after the run. Removing `data/` returns the suite to
`505 passed, 9 skipped`; nothing in the branch depends on it.

## What I did not touch, and why

Other places still mention retired names. None is a description of what an analyser emits, so none is
in this ticket's scope:

- `testops/web/app.py` `LEGACY_JUDGEMENT` — renders stored rows written before the vocabulary settled.
  Removing it would hide real evidence; the schema note now points at it.
- `testops/score/level.py` `VERDICT_MAP`, `tests/fixtures/level_sample_20.json` — the hand-annotated
  evaluation key was written in the old vocabulary; the map translates it. Data, not documentation.
- `testops/scripts/annotate_key.py` — translates the old key into current verdicts.
- `testops/judgement/prompts/level_fitness.md` — still asks a model for
  `optimal|overbuilt|necessary|unplaced`. This one is a genuine stale description, but it drives a
  model tier that nothing imports (`testops/judgement/client.py` has no callers), and it is outside
  the three places the ticket names. **Recommend a follow-up ticket**: either wire the prompt to the
  current vocabulary or delete the unused tier. A builder should not silently expand scope by fixing
  it here.

## Reviewer's quick checks

1. `git diff` — two prose edits plus one new test file; no logic.
2. Mutate any of the three lists and re-run the new test; it must fail naming the direction.
3. Run the full suite with `data/` present to see the pinned corpus counts.
