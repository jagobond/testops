---
id: TESTOPS-46
title: A store can no longer be restored from its own history
feature: F2
status: done
autonomy: build
depends_on: TESTOPS-45
---

# TESTOPS-46 — Restore must not be a write

## Finding (TESTOPS-45 review)

TESTOPS-45 added triggers that refuse any verdict outside the vocabulary table. The table holds the five current names
and the three retired ones, but the trigger treats the list as *what is current*, so:
**`INSERT INTO claim SELECT ...` carrying a retired name (`optimal`) from an older store is refused.**

File-level backup is unaffected — the nightly copy moves the SQLite file. But any row-level export, restore, or
store-to-store copy now fails on exactly the data it is meant to preserve. A guard that prevents you restoring your own
history is protecting the wrong thing.

## Decision taken here (Lead's call)

The two guards have different jobs and were collapsed into one:

- **At the database:** a verdict must be *a name this product has ever emitted* — current or retired. This preserves
  restore and keeps garbage out.
- **In the code:** an analyser must emit *a name current today*. `store/verdicts.validate_verdict` stays strict, so no
  code path can write a retired name in a live run.

Restoring history is not writing new history, and the store should treat them differently.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Row-level copy from a store holding retired names into a fresh store succeeds, with all rows byte-identical after the copy (hash the dump before and after). This is the AC that must not be dodged. |
| AC2 | A verdict that is neither current nor retired is still refused on insert and update. Prove by direct SQL. |
| AC3 | New analysis runs still cannot write a retired name: the Python validator refuses it, and a test proves the analyser path is stricter than the trigger. State the distinction in the schema comment so the next reader does not re-collapse them. |
| AC4 | `check-store` distinguishes three states: unknown verdict (never emitted), retired verdict (historical), current. Report counts for each. |
| AC5 | The restore path is exercised by a test that copies a store containing all three states and verifies counts and hashes. |
| AC6 | No behaviour change: CotW 94/90/1/1/2, ReqOverflow 17/17, pages unchanged, suite green. |

## Notes

- If allowing retired names at the database makes some other guard weaker, say which and stop — do not trade a real
  protection for a restore path.
- Check the nightly backup script (`~/AppData/Local/hermes/scripts/backup_hermes.py`) only moves files; if any tool of
  ours ever copies rows, it is subject to this ticket and should be listed.
