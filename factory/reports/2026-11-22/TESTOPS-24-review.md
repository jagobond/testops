# TESTOPS-24 review — 2026-11-22 (reviewer)

Suite: 288 passed in 43.17s (.venv, clean invocation `env -u PYTHONPATH -u VIRTUAL_ENV
PYTHONNOUSERSITE=1 .venv/Scripts/python.exe -m pytest -q`); 284 passed, 4 skipped on 3.11 via
`uv run --no-project --python 3.11 --with pytest` with `PYTHONPATH=.` (bare invocation fails
collection with ModuleNotFoundError on both interpreters — pre-existing, not this ticket's fault).
All destructive work ran against copies of `data/` under the reviewer scratch dir; the product
store was never written to by me.

## Verdict — PASS

The command does exactly what the ticket says, every protection refused when attacked by hand, the
growth numbers reproduce from my own before/after measurements, and the shared-blob guarantee held
under a deliberate orphan attempt.

## Criteria

| AC | assessment |
|----|------------|
| AC1 | HOLDS. Two real duplication runs on a store copy: 274 blob files / 2,215,928 B before each run, +0 files / +0 bytes after each; rows did grow (+385 each). |
| AC2 | HOLDS with one caveat. I measured +385 rows / +167,936 db bytes / +0 blob bytes for the first duplication run — exact match to the build table. The second run added 159,744 db bytes, not the 167,936 the build claims for both runs (8 KB = page-allocation variance). Direction and magnitude reproduce; the build's claim of identical byte adds for the two identical runs is not stable. I did not re-run a levels run; its half of the table is unverified by me. |
| AC3 | HOLDS. Report prints age, rows, bytes, decision and suppression per snapshot; verified on the copy and unchanged row counts confirm it is read-only. |
| AC4 | HOLDS. Refusals verified by hand (below). Newest-run-per-analyser protection verified live: after keep-2 prune, `demo-product-levels-20261122-a3f19853-r8` (level_fitness) and `demo-service-20261122-78153818-r5` (duplication) both survived. `--keep` is per project, which deletes strictly fewer than the ticket's global reading — a defensible subset, argued in the build report. |
| AC5 | HOLDS. After `--keep 2 --yes`: 12 snapshots / 5,444 rows deleted (my deltas: snapshot −12, run −15, artefact −1,274, observation −1,950, claim −970, case −65 — matching the build). Three cases rendered before: 5,679 / 5,679 / 56,186 B. After, the two dup cases rendered byte-identical; the levels case was itself deleted (it existed in the deleted set), so its page is correctly gone, not broken. |
| AC6 | HOLDS, both directions. Shared-blob orphan attempt: keep-2 prune deleted 0 blob files, all 274 referenced shas still on disk, survivors render. Unique-blob orphan attempt (synthetic snapshot + blob referenced by nothing else): prune deleted exactly that blob (420 B) and its rows, left all 274 shared files untouched — disk 275/2,216,348 → 274/2,215,928. |
| AC7 | HOLDS. Plain `retention` exited 0 with the database mtime unchanged. `--prune` without `--keep` exited 2; `--prune --keep 2` exited 2 with "Refusing to prune without --yes"; all table counts identical after both refusals. Grep finds no cron/schedule/timer anywhere in the tree; `retention.py` has no import-time action. |
| AC8 | HOLDS. 288 passed (.venv 3.12), 284 passed + 4 skipped (3.11), both with env stripped. |

Verdict counts re-verified from the store: newest levels run `demo-product-levels-20261122T111056` in
snapshot `demo-product-levels-20261122-a3f19853-r8` holds 94 claims → distinct 90, unplaced 1, gap 1,
review 2. Exact.

## Refusals — what I did, what it did

1. Report-only default. Ran `retention` with no flags on a copy; exit 0, database file mtime
   unchanged, no blob touched. Nothing written.
2. Unbounded prune. `retention --prune` (no `--keep`): exit 2, "retention --prune needs --keep N.
   Nothing was deleted." Row counts identical.
3. Missing confirmation. `retention --prune --keep 2`: exit 2, "Refusing to prune without --yes.
   Nothing was deleted." All nine table counts identical before/after.
4. Newest run per analyser. After `--keep 2 --yes` on a copy, checked the newest level_fitness
   snapshot (r8) and newest duplication snapshot (r5) — both survived even though older snapshots
   in their projects were deleted.
5. Decided case. Snapshot `demo-product-levels-20261121-a3f19853` (decision: yes in the report) survived
   the same prune.
6. Shared blob. Attacked by pruning every snapshot that shares blobs (keep-1 on a second copy,
   then keep-2 on the synthetic-blob copy): zero blobs referenced by surviving artefacts ever
   disappeared; a blob referenced only by a deleted snapshot was the only file ever removed.

## Growth — measured by me, against the build table

Store before: 9,648 rows, 4,927,488 B db, 274 blob files, 2,215,928 B blobs. (Matches the build's
"after all four" state, confirming the same starting point.)

| run | rows added | db bytes added | blob bytes added | build claims |
|---|---:|---:|---:|---|
| duplication 1 (r6) | +385 | +167,936 | +0 | 385 / 167,936 / 0 — exact match |
| duplication 2 (r7) | +385 | +159,744 | +0 | 385 / 167,936 / 0 — rows and blobs match; db bytes differ by 8,192 |

Zero blob growth over an unchanged commit reproduces exactly; that is the substantive claim. The
byte-identical-second-run implication does not. The levels rows (486 / 311–328 KB) I did not
re-measure.

## Three sharpest concerns

1. `--keep N` is per project, not the ticket's "N most recent" global reading. Every deletion is
   still older than N snapshots globally, so the letter of AC4(a) holds and the command deletes
   fewer than allowed — but a reader invoking `--keep 2` expecting two snapshots total gets one
   per project. It is argued in the build report, not silent; the Lead should accept it
   explicitly.
2. The build's growth table implies the two identical duplication runs add identical bytes
   (167,936 twice). Measured: 167,936 then 159,744. Growth is rows-stable but not byte-stable;
   anyone budgeting in bytes should use the rows figure, which did reproduce exactly.
3. `case_page` returns `None` for a deleted case, so a caller that survives a prune and renders a
   stale case id gets a TypeError rather than an error page. Not an AC breach (the deleted case's
   page is correctly gone), but the web layer will surface this as a crash, not a 404, the first
   time a client holds a stale id.
