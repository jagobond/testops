# TESTOPS-24 build report — 2026-11-22

Branch `factory/testops-24-retention`, built from `c05f739`. The Product Owner's decision was
dedupe-by-content-hash. The build proves the dedupe already holds, measures growth instead of
estimating it, and adds one command that reports what the store holds and prunes only when told to
twice: `--prune` says *what*, `--yes` says *do it*.

There is no schedule and no default prune. A grep of the tree finds `retention` only in
`testops/retention.py`, `testops/cli.py` and `tests/test_retention.py`.

## What changed

**`testops/retention.py` (new).** The read model and the only deletion path.

- `report_rows` gives one row per snapshot: age, rows, measured payload bytes, distinct blob count
  and bytes, and whether any case referencing it has a `case_state` row or a suppression.
- `plan(keep)` decides what a prune would delete and why each survivor survives. It applies
  `--keep` per project, then protects snapshots referenced by a decision or a suppression, then
  the snapshot of the newest run per analyser (per project), then any snapshot a surviving finding
  still names a claim from.
- `prune(keep, yes=...)` re-derives the plan itself; a caller cannot hand it a list. Without `yes`
  it returns the plan and touches nothing. Blobs are unlinked only after the rows are committed,
  and only when no surviving artefact row references the sha.
- `store_footprint` is the before/after instrument: row counts per table, the database file's size
  from `os.stat`, and every blob file's size. It reads the file from the connection, not from
  config, so it cannot report on a different store from the one just written.

**`testops/cli.py`.** `testops retention` prints the store footprint and the snapshot table.
`testops retention --prune --keep N` prints exactly what would go and refuses with exit 2 unless
`--yes` is present. `--prune` without `--keep` is refused (an unbounded prune is not a retention
policy). The final line reports the database file before and after and says freed pages are
reused, not shrunk.

No schema change. No stored row is rewritten, and the four measurement runs described below are
ordinary runs appended to the store.

## AC1 — dedupe is proved, not assumed

**The real store, four runs.** The blob directory held **274 files / 2,215,928 bytes** before the
first run and was unchanged after every one of the four runs below (`files` 274 and
`bytes - db_bytes` 2,215,928 at each reading). The two runs over `demo-product@a3f19853` and the two over
`demo-service@78153818` each added **zero blob files and zero blob bytes**.

**The test** (`test_two_runs_over_an_unchanged_commit_add_no_blob_files_and_no_blob_bytes`) wires
the real duplication pipeline to the real 108-file corpus with a collector that calls
`blobs.put` on every file again for the second run — the same call the real collector makes. It
asserts the sorted list of blob paths and the directory byte total are identical, the distinct-sha
count is identical, and that artefact/observation/claim rows *did* grow. The collector is not a
stub that skips the dedupe; it is the dedupe, exercised twice.

## AC2 — measured growth, before and after, on the real store

Instrument: `retention.store_footprint`, taken on a fresh connection immediately before and after
each run. Bytes are the database file plus every blob file as `os.stat` reports them; rows are
counted per table. Nothing is annualised or scaled.

Store before the measurements: **7,906 rows, 3,952,640 B database, 2,215,928 B in 274 blobs**.

| run | snapshot | rows added | database bytes added | blob bytes added | blob files added |
|---|---|---:|---:|---:|---:|
| levels 1 — `demo-product-levels-20261122T111027` | `demo-product-levels-20261122-a3f19853-r7` | 486 | 311,296 | 0 | 0 |
| levels 2 — `demo-product-levels-20261122T111056` (same commit) | `demo-product-levels-20261122-a3f19853-r8` | 486 | 327,680 | 0 | 0 |
| duplication 1 — `demo-service-dup-20261122T111139` | `demo-service-20261122-78153818-r4` | 385 | 167,936 | 0 | 0 |
| duplication 2 — `demo-service-dup-20261122T111222` (same commit) | `demo-service-20261122-78153818-r5` | 385 | 167,936 | 0 | 0 |

Store after all four: **9,648 rows, 4,927,488 B database, 2,215,928 B in 274 blobs**.

What the rows are, measured from the deltas:

```
levels      1 snapshot + 1 run + 95 artefacts + 195 observations
          + 94 claims + 94 inferences + 3 cases + 3 findings = 486
duplication 1 snapshot + 1 run + 158 artefacts + 171 observations
          + 18 claims + 0 inference + 18 cases + 18 findings = 385
```

So the ticket's premise is measured, not repeated: an unchanged commit costs **486 rows for a
levels run and 385 rows for a duplication run**, and **zero blob bytes**. The "~250 KB per run"
figure in the TESTOPS-14 report was, as suspected, a snapshot-size estimate; the measured database
growth is 311–328 KB for a levels run and 168 KB for a duplication run on this corpus, all of it
rows. This branch's committed baseline is **277 tests**, and 11 are added here.

## AC3 — the report answers per snapshot

`testops retention` on the store after the measurements (first and last lines shown; the table is
one line per snapshot):

```
store      9648 rows · 4.70 MB in the database · 2.11 MB in 274 blob files

snapshot                                   project      age          rows      bytes  decision suppression
demo-service-20261120-78153818              demo-service  1d 19h        240   742.5 KB  no       no
demo-product-levels-20261121-a3f19853              demo-product         13h 18m      1693    1.29 MB  yes      no
demo-product-levels-20261121-a3f19853-r2           demo-product         12h 08m       486    1.43 MB  no       no
...
```

`tests/test_the_report_states_age_rows_bytes_decisions_and_suppressions` builds two snapshots and
asserts every column: age is a positive measured interval, `rows` counts the snapshot, its run and
its rows exactly, `bytes == row_bytes + blob_bytes`, a `needs_fix` decision sets `decided`, and a
suppression row sets `suppressed` without a decision. The per-snapshot bytes are the measured byte
length of each stored text value plus the on-disk blobs the snapshot references; a shared blob is
counted under each snapshot that references it and is broken out as `blob_bytes`.

## AC4 — the prune plan and the refusal

On a copy of the real store, `--keep 2`:

```
prune plan — keep 2 most recent per project
  delete demo-service-20261120-78153818 (demo-service, age 1d 19h, 240 rows, 742.5 KB)
  delete demo-product-levels-20261120-a3f19853 (demo-product, age 1d 15h, 546 rows, 1.03 MB)
  ... 10 more ...
  delete 0 blob files: every blob is still referenced by a surviving artefact
  kept:
      1  a case referencing it has a decision
      1  a surviving finding still names one of its claims
      2  one of the 2 most recent in demo-product
      2  one of the 2 most recent in demo-service
      2  the newest duplication run
      1  the newest level_fitness run

Refusing to prune without --yes. Nothing was deleted.
```

Three tests pin the rules: decisions and suppressions each protect a snapshot outside the keep
window, and the newest run per analyser protects its snapshot even when that snapshot is older than
every kept one (`test_pruning_keeps_decided_suppressed_and_newest_run_snapshots`,
`test_the_newest_run_per_analyser_is_never_pruned_even_outside_the_keep_window`). A fourth,
`test_keep_is_per_project_so_a_quiet_project_does_not_lose_its_history`, pins the per-project
reading of `--keep`.

**Why per-project is within the criterion.** A snapshot that is not among its own project's N most
recent is older than N snapshots of that project, and those are all snapshots in the store — so it
is older than the store's N most recent too. Every snapshot this command deletes satisfies (a)
under the global reading as well; it merely deletes fewer of the ones it is allowed to. The same
argument holds for the newest-run rule, which is applied per project and therefore protects at
least the global newest run of each analyser.

`test_prune_refuses_without_yes_and_changes_nothing` calls the API with `yes=False` and compares
every table's count before and after; `test_the_default_is_report_only_and_says_so` does the same
through the CLI, and also proves `--prune` without `--keep` is refused with exit 2.

## AC5 — surviving pages survive, shown on the real store and in a test

On a copy of the real store, after `--keep 2 --yes`: **12 snapshots and 5,444 rows deleted**
(12 snapshot, 15 run, 1,274 artefact, 1,950 observation, 970 claim, 916 inference, 65 case, 242
finding, 0 case_state). Seven snapshots remain. Three cases rendered through
`testops.web.app.case_page` before and after, byte for byte:

```
case-demo-product-dup-20261120T153507   5,679 bytes   identical: True
case-demo-product-dup-20261120T194032   5,679 bytes   identical: True
rev-duplicate                  11,015 bytes   identical: True
```

One snapshot survived solely because of the third protection rule, and it is a real reference, not
a fixture: `case-rev-duplicate` in snapshot `demo-product-20261120-a3f19853` carries claim id 1606 in its
finding, and that claim lives in `demo-service-20261122-78153818-r3`. Deleting r3 would have left a
surviving page with a claim it could not render, so the plan kept it. That is the defect AC5
guards against, found and prevented on the store's own data.

`test_pruning_the_oldest_levels_snapshot_leaves_surviving_pages_identical` does the ticket's
literal case: three real levels runs, six cases, no decisions; `--keep 2 --yes` deletes the oldest
levels snapshot and its two cases; the four survivors still hold, and three of them render with
identical bytes before and after.

## AC6 — a shared blob is never deleted

`test_a_blob_shared_with_a_surviving_artefact_is_never_deleted` runs two levels pipelines over the
same content so every corpus blob is shared, adds one blob referenced only by the oldest snapshot,
prunes it, and asserts the unique file is gone while every shared file is present and still
referenced by a surviving artefact row.

On the real copy, the prune deleted **0 blob files / 0 bytes**: all 274 files are referenced by a
surviving artefact, so the measured blob directory is 2,215,928 B before and after. Blob files that
no artefact row references at all are left alone on purpose — this command only removes bytes it
can tie to a deletion decision.

## AC7 — report-only is the default

No flags: the command prints the report and exits 0 without writing. `--prune` alone prints the plan
and exits 2. `--prune --keep N` prints the plan and exits 2 with `Refusing to prune without --yes`.
Only `--prune --keep N --yes` deletes. There is no timer, no cron entry and no import-time action in
`retention.py`.

## Verification

- Suite on this branch, clean invocation (`env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u
  CONDA_PREFIX PYTHONNOUSERSITE=1`), run in a worktree of `c05f739`:
  - Python 3.12.5 (`.venv`): **288 passed**, 58.15s. 277 collected before this ticket, 11 added.
  - Python 3.11 (`uv run --no-project --python 3.11 --with pytest`): **284 passed, 4 skipped**,
    64.67s. The four skips are the pre-existing pre-3.12 checks.
- Growth measurements above: taken with `retention.store_footprint` immediately before and after
  each of four real runs against `data/testops.db`, not from a fixture.
- Prune evidence above: taken on a copy of that store (`TESTOPS_HOME` pointed at the copy), so the
  product store was not pruned during this build.

## What this does not satisfy

1. **Pruning does not shrink the database file.** SQLite reuses freed pages; the copy's file stayed
   at 4.70 MB across the deletion. The command says so rather than implying a saving, and it does
   not `VACUUM` — rewriting the whole file is a different, larger action than deleting named rows
   and was not asked for. A future ticket could add `--vacuum` with its own confirmation.
2. **Per-snapshot `bytes` is payload, not SQLite pages.** It sums the byte length of stored text
   values plus the on-disk blob files. Page overhead and index bytes are not attributed to a
   snapshot; the store-level line at the top of the report is the file measurement. The build
   report's growth numbers use the file measurement, so AC2 is not affected.
3. **A shared blob's bytes are counted under every snapshot that references it.** That is why
   `blob_bytes` is reported separately; adding snapshot `bytes` values does not equal the store.
4. **The cross-snapshot claim rule keeps a whole snapshot.** If one surviving finding names one
   claim, the snapshot that holds it survives entirely. Surgical retention of single claims would
   be a finer policy and a larger one; keeping the snapshot is the conservative answer.
5. **`--keep` is per project, not per analyser.** Within one project, the N most recent snapshots
   survive whatever analyser wrote them. The newest-run rule means an analyser's current answer is
   always kept, but an older project snapshot can be dropped even if it is the only duplication
   snapshot of that age.
6. **Nothing schedules this.** That is deliberate (AC7), but it also means the store grows exactly
   as measured until someone runs the command. The `--yes` gate is the only guard against a
   careless scheduled invocation.

## Where to look

`testops/retention.py` (`report_rows`, `plan`, `prune`, `store_footprint`), `testops/cli.py`
(`cmd_retention`, `_print_plan`), `tests/test_retention.py` (AC1–AC7, 11 tests).
