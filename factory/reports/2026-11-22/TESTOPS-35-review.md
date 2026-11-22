# TESTOPS-35 — review report

Reviewer session, 2026-11-22. All work on copies under `C:/Users/Chester/AppData/Local/Temp/rev35` and
`rev35b`; the live store was opened only through `file:...?mode=ro`.

## Verdict — PASS

The scrub command, the 404 and the store guard all behaved exactly as specified under adversarial probing on
copies, the registered case was never touched, and the live store is byte-identical to where the build found it.

## Criteria

- **AC1 — HOLDS.** `scrub-fixtures --dry-run` then `--yes` on a copy removed exactly the planned rows, counted
  from SQLite's own rowcounts; run/snapshot/artefact/observation/claim counts unchanged (39/22/2460/3662/2053
  before and after); a second dry run reports 0.
- **AC2 — HOLDS.** A case with unregistered analyser `x` answers 404 with the TESTOPS-30 page in its
  unregistered variant (names the analyser, points at `scrub-fixtures`); a registered case answers 200; after
  scrubbing, the same id answers the retention variant of the same page. The dashboard (`latest_per_analyser`)
  does not list the fixture case either before or after scrubbing.
- **AC3 — HOLDS.** See "The guard".
- **AC4 — NOT INDEPENDENTLY EXERCISED (weak by omission, not by contradiction).** The prompt files exist and
  read plainly (REVIEW-WORKFLOW.txt + the standing rule in all 24 review-*.txt); I did not re-run a review
  against them to prove a reviewer would follow them. The guards make the failure mode hard regardless.
- **AC5 — HOLDS.** A surviving case page (`case-cotw-dup-20261120T153507`) renders sha256-identical from a
  pristine copy of the live store and from the post-scrub probe copy (both `59941be8…`, 5,677 bytes).

## Deletion probes

Planted in a copy of the live store (all pinned to the real `reqoverflow-dup-20261120T153431` run):

| case | analyser | findings | decision | suppressions |
|------|----------|----------|----------|--------------|
| rev-madeup | `made-up-analyser` | 1 (`revprobe-unique-0001`) | yes (resolved, reviewer-probe) | 1, unique |
| rev-casing | `LEVEL_FITNESS` (case-variant of a registered name) | 2 — one fingerprint shared with a surviving registered case's finding, one unique | no | 1 unique; shared fingerprint's suppression pre-existing ("real decision" by harry) |
| rev-empty-registered | `duplication` (registered) | 0 | yes (open) | 0 |

`--dry-run`: reported 3 fixture cases, `case_ 3 · finding 4 · case_state 1 · suppression 2`, listed the
suppression fingerprints, showed rev-madeup's decision, and touched nothing. Note what it did **not** count:
the shared fingerprint's suppression (a surviving finding still carries it) and rev-empty-registered entirely.

`--yes`: removed `suppression 2 · finding 4 · case_state 1 · case_ 3`; totals `case_ 171→168`,
`finding 670→666`, `case_state 9→8`, `suppression 3→1`. Post-state verified:

- rev-empty-registered and its decision survive untouched — a registered case with zero findings is never
  deleted, even with a recorded decision on it.
- The shared fingerprint's suppression survives (3 findings still carry it); the two probe-only suppressions
  are gone. No suppression that protects surviving evidence was removed.
- Zero orphan rows: no case_state or finding without its case.
- `LEVEL_FITNESS` was deleted. This is a deliberate exact-match rule (`is_registered` compares literally
  against `duplication`/`level_fitness`), not an accident — but it is **undocumented**: nothing in the CLI
  output or module docstring says analyser matching is case-sensitive, so a store holding a legitimately-cased
  variant would be scrubbed without the report saying why. Flagged below.
- **"Something real"**: the probe deliberately put a decision (a `case_state` row recorded by an actor) on a
  fixture case. The command deletes that decision, says so in the report ("decision resolved by
  reviewer-probe"), and leaves no orphan. The module docstring declares this deliberate ("its recorded
  decisions were written by the harness, so they go"), and the dry run surfaces it before `--yes`. I judge
  this correct — a decision recorded by a review harness on a case no analyser could have raised is
  apparatus — but it is the sharpest edge in the design and depends entirely on the analyser registry being
  right.

## The guard

Wrote a probe test (`tests/test_zz_reviewer_guard_probe.py`, since deleted) whose first test called
`sqlite3.connect(live_store)` and wrote a table — the exact call that wrote the original fixture — and whose
second test wrote to `tmp_path`.

- With the suite's guard active, the live-store test **failed** at the connect itself with
  `StoreWriteRefused: a test tried to open the product store for writing: C:\Users\Chester\Projects\testops\data\testops.db`;
  the tmp-path test passed. This is a refusal at the open, not a warning and not a post-hoc digest.
- Incidental second proof: the full suite ran while the probe file was still on disk, and the session
  `repo_guard` failed teardown with `a test wrote into the repository: {'added':
  ['tests/test_zz_reviewer_guard_probe.py']}` — the repository digest caught an added file too.
- Clean re-run after deleting the probe: **351 passed, 7 skipped** (matches the build report), `import testops`
  resolves to `C:\Users\Chester\Projects\testops-t35\testops\__init__.py`, worktree `git status` clean.

## Live store untouched

Before and after all review activity, `C:/Users/Chester/Projects/testops/data/testops.db`:
mtime `1795349163.497` (2026-11-22 12:06:03), 5,697,536 bytes, sha256
`dc3071175d4cdc8e2445d413f7614449016358b3eb61172743334a738e6a6ce2`; 168 cases, 667 findings; `rev-duplicate`
still present (its removal is the Product Owner's command to run, not the reviewer's).

## Three sharpest concerns

1. **Case-sensitivity of the registry is a silent deletion rule.** `LEVEL_FITNESS` is scrubbed as a fixture
   with no line of output explaining that matching is exact. A typo'd or re-cased legitimate analyser name in
   any future store would be destroyed as apparatus. The report should say the match is exact, or the
   registry should normalise case.
2. **The whole guard rests on `is_registered` being complete.** A future analyser module forgotten in
   `testops/analysers/__init__.py` turns every one of its real cases into scrub candidates with a real
   recorded decision attached — the command would then delete genuine decisions. The registry is read from
   the modules themselves, which helps, but nothing cross-checks it against the run table's distinct
   analysers; a `--dry-run` diff of "analysers present in the store vs registered" would make an incomplete
   registry visible before any `--yes`.
3. **AC4 is attested, not demonstrated.** The prompts say the right things, but nothing in this review proved
   a reviewer following them would actually stay inside the copy — the guard in the suite is what makes the
   boundary hold, and it only binds pytest runs, not an ad-hoc script like the one that caused the ticket.
   The CLI-side residual risk is unchanged: any script outside the suite can still open the live store
   read-write. A `TESTOPS_HOME`-or-read-only default in `db.connect()` would close that for product code too.
