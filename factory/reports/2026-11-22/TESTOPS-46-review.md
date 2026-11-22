# TESTOPS-46 review — restore must not be a write

Reviewed 22 Nov 2026 on `factory/testops-t46` at HEAD `7f3efca`. Suite from the project venv
(`env -u PYTHONPATH -u VIRTUAL_ENV PYTHONNOUSERSITE=1 ...python.exe -m pytest -q`):
**548 passed, 0 skipped, 92.9s**. Live store exercised as a read-only copy
(`data/testops.db` copied to scratch; the original was never opened for write).

## Verdict

**PASS.** The asymmetry is real and tested from both sides; the widened INSERT is not a back door
into the live write path; restore is byte-identical end to end; the v6 migration replaces trigger
bodies rather than duplicating them; `check-store` distinguishes the three states. AC1–AC6 hold.
The three sharpest concerns at the bottom are all about the shape of the remaining trust boundary,
not defects in this build.

## The asymmetry (four probes)

Fresh v6 store, direct SQL (the path a restore uses), errors quoted verbatim:

1. **INSERT `optimal`** — SUCCEEDS (rows = 1). Restore works.
2. **UPDATE a stored `optimal` row TO `necessary`** — REFUSED:
   `claim.verdict is not one of distinct|gap|review|unplaced|duplicate: a stored verdict may not be rewritten to an unknown or retired name` — value still `optimal`.
3. **UPDATE a stored `gap` row TO `optimal`** — REFUSED, same message. So an existing row cannot
   be *converted* to a retired name either, not just an already-retired one rewritten.
4. **UPDATE to `total_nonsense`** — REFUSED (same message).
5. **INSERT `total_nonsense`** — REFUSED:
   `claim.verdict is not a verdict this product has ever emitted: current are distinct|gap|review|unplaced|duplicate; retired are necessary|optimal|overbuilt, accepted only from a restore`.

Installed SQL verified: the INSERT trigger has no `status = 'current'` filter; the UPDATE trigger
does. The four probes never collide.

## Back door (the real write path)

Every product writer of `claim` goes through `db.add_claim` (`pipeline.py` calls it twice; a
repo-wide search finds no other `INSERT INTO claim` in product code). Calling it for real:

```
db.add_claim(conn, run, 'level_fitness', '0.6.0', ..., 'optimal', ...)
→ UnknownVerdict: verdict 'optimal' is not one of distinct, duplicate, gap, review, unplaced; the store refuses an unknown verdict
```

No row written (count stayed 0). Same refusal for `overbuilt` and `necessary`. The guard is the
call, not the function existing: it runs at `db.py:147` before the INSERT. The honest statement of
the residual risk: **the database itself no longer enforces the analyser rule** — a future writer
that opens a connection and INSERTs directly can write `optimal` and the store accepts it
(deliberately, for restore). The protection for live runs is now entirely in code. The ticket
decided this and the schema header documents it; I confirm the build did not quietly go further.

## Restore end to end

Source: the live store copy, 2,310 claims (distinct 1626, duplicate 160, gap 29, necessary 25,
optimal 36, overbuilt 67, review 42, unplaced 325). SHA-256 over the full claim dump (all columns,
ids included) before the copy.

- **Retired names present:** `INSERT INTO snapshot/run/claim SELECT * FROM src.*` into a fresh
  v6 store — SUCCEEDED, 2,310 rows, digest identical before/after (`5a4ba248096f8d5b…`), all 128
  retired rows carried.
- **Current names only:** 2-row store restored, digest equal.
- **Unknown name (`total_nonsense`) present:** guarded copy REFUSED with the AC2 message above —
  confirmed, the build's claim is accurate. The workaround (drop the destination's two triggers,
  copy, reopen) works: digest equal, and reopening reinstalls both triggers from `schema.sql`;
  a post-restore INSERT of `total_nonsense` is refused again, and `check-store` names the row and
  exits 1. **Assessment: acceptable, not a hole** — it is loud afterwards (the unknown rows are
  reported as a defect, exit 1), and nothing is silently admitted. But it is a manual step a
  restore tool must know about, and the store carries no record that the guard was down during the
  copy; see concern 2.

## v6 migration

On a v5 store (v5 trigger bodies installed, `schema_meta` set to 5):

- Reopen prints `migrated store v5 -> v6` on stderr.
- `sqlite_master` afterwards holds **exactly two** claim triggers (`claim_verdict_insert`,
  `claim_verdict_update`) — replaced, not duplicated. The INSERT body has no `status = 'current'`
  filter; the UPDATE body does.
- Rows untouched: claim digest identical, 1 row before and after.
- A post-migration INSERT of `optimal` succeeds, so a store that came up from v5 can actually be
  restored into, not just opened.

## check-store

On the live store copy (2,310 claims):

```
current       2182 (distinct 1626, duplicate 160, gap 29, review 42, unplaced 325)
historical    128 (necessary 25, optimal 36, overbuilt 67)
unknown       0    — exit 0
```

On the restored unknown-carrying store: `current 1 (gap 1) / historical 0 / unknown 1`, the row is
named by id/run/verdict/subject, **exit 1**. Three states, real counts, correct exits.

## Three sharpest concerns

1. **The analyser rule now lives only in code, and the store cannot tell a live write of a retired
   name from restored history.** `check-store` reports retired rows as `historical` whichever way
   they arrived, so a future connector that INSERTs directly and emits `optimal` in a live run is
   indistinguishable from a legitimate restore — no alarm anywhere. The schema header documents
   the two levels, which is the mitigation the ticket chose; a reviewer accepting this ticket is
   accepting that the database is now the *looser* guard on the only write path that matters.
2. **The unknown-restore workaround is an undocumented-in-data escape hatch.** Dropping triggers
   leaves no marker in the store; the guard silently reappears on the next open. Detection after
   the fact is good (unknown rows flagged, exit 1), but the restore itself is unauditable: nothing
   in the store or its meta says "this copy happened with the guard down". A restore tool built on
   this pattern should record it (e.g. a `schema_meta` note), or the next incident will be
   indistinguishable from an operator who simply forgot to reopen.
3. **`check-store` still migrates as a side effect** (it opens through `db.connect()`, and the
   migration writes on open). Unchanged by this ticket and already noted in the TESTOPS-45 review,
   but it now matters more: a "check" of a v5 store is also a v6 upgrade of it, so the thing being
   checked is not the thing that was on disk before the check ran.
