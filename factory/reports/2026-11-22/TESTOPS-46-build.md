# TESTOPS-46 build report — restore must not be a write

Built 22 Nov 2026 on `factory/testops-46-restore`, from HEAD `18eda94`
(`board: TESTOPS-45 done; TESTOPS-46 opened`). Ticket: `factory/tickets/TESTOPS-46.md`.
Evidence: `factory/reports/2026-11-22/TESTOPS-45-review.md`, section *Attempts to slip past*, row
`INSERT INTO claim SELECT ...` from a store holding a retired name — **refused**.

## The fault, restated

TESTOPS-45's INSERT trigger asked `NEW.verdict NOT IN (SELECT name FROM verdict_vocabulary WHERE
status = 'current')` — a live-run question. A restore is not a live run. Carrying `optimal` out of an
older store is the store keeping its own past; the v5 trigger refused exactly the rows a restore
exists to preserve. File-level backup was unaffected (it copies the SQLite file), but any row-level
export, restore or store-to-store copy failed on the data it was meant to protect.

## What was built

- `testops/store/schema.sql`
  - `claim_verdict_insert` now refuses only a name **this product has never emitted**:
    `WHEN NEW.verdict NOT IN (SELECT name FROM verdict_vocabulary)` — the whole table, current and
    retired. Its message names both sets and says retired names are "accepted only from a restore".
  - `claim_verdict_update` is **unchanged** in rule: `status = 'current'` only. Changing an existing
    row's verdict to a retired name is a rewrite of evidence, not a restore. Widening INSERT was
    sufficient for AC1, so UPDATE's protection was left intact rather than weakened without need.
  - The schema header states the two levels explicitly (database = ever emitted; code = current
    today) and says not to collapse them again.
- `testops/store/migrate.py` — `CURRENT_VERSION = 6`. `CREATE TRIGGER IF NOT EXISTS` cannot change a
  body, so a v5 store has both verdict triggers dropped in `prepare()` before `executescript`
  reinstalls the v6 bodies. No row is copied or rewritten. A new store gets them directly from
  `schema.sql`.
- `testops/store/verdicts.py` — the two sets are now named apart: `current()` (analysers today) and
  `ever_emitted()` (current ∪ retired, what the INSERT trigger and therefore a restore may carry).
  `validate_verdict` documents that callers pass `current()`. `inventory()` counts all three states:
  `current` per name, `historical` per retired name, `unknown` rows.
- `testops/store/db.py` — `add_claim` now calls `verdicts.validate_verdict(verdict,
  verdicts.current(conn))`. This closes a real gap: before this ticket `validate_verdict` existed but
  no product code called it, so "the code guard is strict" was a claim about a function nobody used.
  It is now the analyser emission boundary. Direct SQL writers (restore, migration) never pass
  through it, which is the point.
- `testops/cli.py` — `check-store` reports three states with counts: `current N (...)`,
  `historical N (...)`, `unknown N` (exit 1 when any unknown). The `allowed` line is kept.
- `tests/test_verdict_trigger.py` — rewritten around the two levels; 16 tests (4 are the AC2
  parametrised cases) including AC1–AC5 and a v5→v6 upgrade test.

## Acceptance criteria

| id | evidence |
|----|----------|
| AC1 | `test_a_store_with_retired_names_is_copied_row_for_row_with_identical_bytes`: a 128-row store (36/67/25) copied with `INSERT INTO claim SELECT * FROM src.claim` into a **fresh store with the v6 guard installed**; per-row dump SHA-256 identical before and after, per-name counts identical, and unknown still refused in the destination. Also proved on the real store: 2,310 claims (128 retired) copied into a fresh store, digest `5229e8f6…` identical on both sides. |
| AC2 | Direct SQL: `total_nonsense`, `Distinct`, ` optima l` and `''` all refused on INSERT with the trigger's message naming both sets, claim count still 0; UPDATE of a stored `gap` to `total_nonsense` refused and the stored value stayed `gap`. |
| AC3 | `test_the_analyser_path_is_stricter_than_the_trigger`: `optimal` accepted by direct INSERT; `validate_verdict("optimal", current(conn))` raises `UnknownVerdict`; `db.add_claim(..., "optimal", ...)` raises without reaching SQL; `ever_emitted` contains it and `current` does not. The installed INSERT SQL has no `status = 'current'` filter; the UPDATE SQL does. |
| AC4 | `test_check_store_distinguishes_three_states_with_counts`: `current 3 (gap 2, review 1)` / `historical 3 (optimal 2, overbuilt 1)` / `unknown 1`, exit 1. On the migrated live-store copy: `current 2182`, `historical 128 (necessary 25, optimal 36, overbuilt 67)`, `unknown 0`. |
| AC5 | `test_restore_copies_all_three_states_and_check_store_still_sees_them`: a store holding current + retired + unknown rows is restored verbatim, all rows byte-identical (digest equal), counts preserved, and `check-store` on the restored store still reports all three states. See the caveat below. |
| AC6 | Full suite: **548 passed, 0 skipped**. Demo Product `demo-product-levels-20261122T011316` = 94 claims / 90 distinct / 1 unplaced / 1 gap / 2 review; DemoService `demo-service-dup-20261122T205100` = 17/17 duplicate. Page/corpus arms ran, not skipped: a copy of the live store and its blobs were placed under the worktree's gitignored `data/` so the corpus tests executed against real evidence. |

## The AC5 caveat, stated plainly

A verbatim restore of a store that contains an **unknown** verdict cannot ride through the v6 guard —
AC2 exists precisely so that a value the product never emitted cannot become new evidence, and a
single `INSERT ... SELECT` with one unknown row is refused. AC5's test therefore does what a real
restore would: it proves the guarded copy is refused, then drops the destination's triggers for the
copy, copies every row byte-identically, and **reopens** the store, which reinstalls both triggers
from `schema.sql`. `check-store` then names the unknown rows (exit 1) and normal writes are refused
again. This is the documented escape hatch the TESTOPS-45 review said was missing; it is
detectable afterwards, unlike a silent acceptance. It is not offered for retired names, which need
no trigger drop at all.

## Which guard, if any, got weaker

Only the INSERT rule, and only in the way the ticket decided: three retired names may now be
inserted by SQL. Nothing else moved.

- **UPDATE of a stored verdict to a retired name is still refused** — rewriting history is not
  restoring it.
- **Live writes are stricter than before**, not weaker: `add_claim` previously accepted any verdict
  the trigger allowed (which was any current name plus anything with the trigger down); it now
  additionally refuses retired names in code.
- **Migrations are unaffected**: the v1→v2/v3 rebuild copies into `claim__rebuild`, which has no
  triggers, before `executescript` installs them — a retired row in a v1 store still migrates.
- **Backups are unaffected**: `~/AppData/Local/hermes/scripts/backup_hermes.py:139` copies the
  database with `sqlite3`'s backup API (page copy), not `INSERT`, so triggers never see it.
- No other row-copying tool exists in this repository. `migrate.py`'s rebuild and the tests above
  are the only `INSERT INTO ... SELECT` sites; both are listed here.

If a future reviewer disagrees with the INSERT widening, the only way to keep it is to accept that
a store cannot be reconstituted from its own history — which is the defect this ticket closes.

## Verification

```
$ env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
    C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe -m pytest -q
548 passed in 88.67s
```

Live-store copy (v5, 2,310 claims) opened with this build:

```
migrated store v5 -> v6
before 2310 5229e8f642af245fe3687c050bbaa9c3196e7cc7b1e6cb951c7942fb2400e070
after  2310 5229e8f642af245fe3687c050bbaa9c3196e7cc7b1e6cb951c7942fb2400e070  equal: True
current 2182 historical 128 {'necessary': 25, 'optimal': 36, 'overbuilt': 67} unknown 0
```

Row-level copy of that store into a fresh store: `rows 2310`, digest identical, `retired rows 128`.

## Notes / leftovers

- The worktree's gitignored `data/` now holds a copy of the live store and blobs so the corpus arms
  run; it is not committed and does not affect the main checkout, which was not opened or written.
- `check-store` still opens through `db.connect()` and therefore migrates a legacy store as a side
  effect (noted in the TESTOPS-45 review). Unchanged by this ticket.
- SQLite's `RAISE()` still cannot interpolate the offending value; the INSERT message now names both
  sets, and `check-store` / `validate_verdict` name the value.