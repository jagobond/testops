# TESTOPS-45 review — the store refuses a verdict no analyser emits

Reviewed 22 Nov 2026 on `factory/testops-45-verdict-trigger` at `8368bbe`.
Suite from this worktree, clean env: `534 passed, 11 skipped in 101.20s` — matches the build report.

## Verdict

**PASS, with one finding that needs its own ticket.** AC1–AC6 are all met by real behaviour, not
by the test suite alone: every probe below was run with direct SQL against stores this review
created (and against a copy of the live store), independently of the builder's tests.

The finding: **history is not copyable across stores.** `INSERT INTO claim SELECT ...` carrying a
retired name (`optimal`) is refused by `claim_verdict_insert` (see *Attempts to slip past*). The
in-place migration is genuinely safe — nothing is copied — so AC3 holds. But the same refusal that
protects new writes also blocks restoring evidence into a fresh store: a store rebuilt from a SQL
dump of the live store would fail on the 128 historical rows, and there is no documented escape
hatch (no import mode, no documented `DROP TRIGGER` procedure). The vocabulary table says a retired
name "cannot be written again", which is defensible as design, but the operational consequence —
evidence you cannot reconstitute elsewhere — is not stated anywhere in the schema comment, the
ticket, or the build report. If the Product Owner accepts it, it should be accepted in writing; if
not, it needs a ticket. It is not a defect in what this ticket promised, so it does not block this
merge, but it must not be left implicit.

## Triggers fired

All fired by direct `conn.execute` on a v5 store built by `db.connect()`, no repository call. Seed:
one run, one snapshot, then:

| probe | result |
|-------|--------|
| INSERT `verdict='total_nonsense'` | `IntegrityError: claim.verdict is not one of distinct\|gap\|review\|unplaced\|duplicate: the store refuses an unknown verdict` |
| INSERT `verdict=NULL` | `IntegrityError: NOT NULL constraint failed: claim.verdict` (the column's NOT NULL, not the trigger — correct layer, correct refusal) |
| INSERT `verdict=''` | the trigger refusal, as above |
| INSERT `verdict='DISTINCT'` (wrong case) | the trigger refusal — matching is case-sensitive, as it should be |
| UPDATE existing row (`gap`) to `total_nonsense` | the trigger refusal; the stored verdict stayed `gap` |
| UPDATE the same row's `statement` (other column) | allowed — `BEFORE UPDATE OF verdict` correctly scopes itself |

After every refused INSERT the claim count was still 0.

## Attempts to slip past

| attempt | result |
|---------|--------|
| transaction with `PRAGMA ignore_check_constraints=ON` | refused. Expected — the pragma does not affect triggers — but confirmed. |
| trigger temporarily dropped | **accepted**, as expected: the row was written and, after commit, survived a reopen. What this proves: the guard is a property of the database file's triggers, and `db.connect()` reinstalls both triggers on the next open — but a store edited while the trigger was down keeps the bogus row and nothing detects it at open time. Only `check-store` finds it (verified: exit 1, row named). That is exactly what AC5 exists for, and it works. |
| `INSERT OR REPLACE` | refused. `INSERT OR REPLACE` still fires BEFORE INSERT triggers; no bypass. |
| `INSERT INTO claim SELECT ...` from a store holding a retired name | **refused** (`claim.verdict is not one of ...`). This is the finding above: the historical name cannot be carried into a new store by any SQL path. The migration works because it never copies rows; a restore does not have that luxury. |

## Retired rows and the migration hash

Done twice — once on a simulated v4 store (128 claims: `optimal` 36, `overbuilt` 67, `necessary` 25,
triggers dropped, `schema_version` set back to 4), once on a **copy of the real live store**
(`C:/Users/Chester/Projects/testops/data/testops.db` → scratch copy, 2,310 claims, still at v4 with
no triggers).

- Simulated v4 → v5 reopen: `migrated store v4 -> v5`, triggers installed, all 128 rows present, all
  2,310-row and 128-row SHA-256 digests of `SELECT * FROM claim ORDER BY id` identical before and after.
- Live-store copy: digest before `62d3b35bfda2d9d2…`, after migration `62d3b35bfda2d9d2…` —
  **identical**, and the same prefix the build report quotes (`62d3b35b…`).
- Rendering unchanged: `optimal` → `Checked` / `Optimal`, `overbuilt` → `Checked, but over-tested` /
  `Overbuilt`, `necessary` → `Checked` / `Necessary`, exactly today's output.

## Allowed set drift

None, in either direction. Verified independently, not only via the AC4 test:

- `verdict_vocabulary` (live query): current = `distinct, duplicate, gap, review, unplaced`;
  retired = `necessary, optimal, overbuilt`, each with `retired_by = 'TESTOPS-9'`.
- The two installed trigger bodies: both read `verdict_vocabulary ... status = 'current'`; both
  refusal messages parse to exactly the same five names.
- `testops/analysers` literals (grep of every `verdict =`/`verdict=` assignment): `duplicate`,
  `unplaced`, `gap`, `distinct`, `review` — the same five, nothing more.
- Documented names, all three places: `schema.sql` column comment, `Claim` docstring
  (`testops/analysers/base.py:27`), `Claim.verdict` field comment (`base.py:35`) — all
  `distinct | gap | review | unplaced | duplicate`.
- `store/verdicts.py` keeps no list of its own: it queries the table. The only second copy of the
  set is the literal inside the refusal message, which SQL forces, and which the AC4 test pins.

## check-store

Pointed with `TESTOPS_DATA` (the command takes no path argument; it reads the deployment's
`DB_PATH`, consistent with every other command).

| case | output | exit | created a store? |
|------|--------|------|------------------|
| (a) clean store | `allowed distinct, duplicate, gap, review, unplaced` / `historical 0` / `unknown 0 — every claim's verdict is current or a documented historical name` | 0 | n/a |
| (b) store with one `total_nonsense` row (trigger dropped to plant it) | `unknown 1` plus the row: `claim 1 run r1 analyser dup verdict 'total_nonsense' subject scenario:a#b` | 1 | n/a |
| (c) path that does not exist | `no store at ...\testops.db; nothing to check.` | 1 | **no** — checked with both an absent directory and an existing empty directory; no file appeared in either |
| (d) migrated live-store copy (128 retired) | `historical 128 (necessary 25, optimal 36, overbuilt 67) — retired names, read as stored, never rewritten` / `unknown 0` | 0 | n/a |

One side effect worth naming: `cmd_check_store` opens the store through `db.connect()`, so
checking a legacy store **migrates it** to v5 (installs the triggers) as a side effect. Additive and
harmless, but a command named "check" writing to the store is a small surprise; a reader should know.

## RAISE

The limitation is real and this review reproduced it independently: `RAISE(ABORT, 'x' || NEW.v)`
→ `near "||": syntax error`; `RAISE(ABORT, printf(...))` → `near "(": syntax error`. SQLite's
RAISE takes a literal only. The trigger's message therefore names the column and all five allowed
values but never the offending value.

Is that sufficient? Mostly, with a known gap. A developer whose INSERT just bounced sees the error
in the same statement they wrote, so the value is in front of them; the Python layer
(`verdicts.validate_verdict`) names it for anyone who wants the better sentence before touching the
database; and `check-store` names it for a value already in a legacy store. The gap is the failure
that surfaces from a path where the value is not visible — a bulk import, a future connector, an
error log with only the message: the reader knows *that* something was refused and *what is
allowed*, but not *what was sent*. They are sent hunting. That is the honest cost of SQLite's
trigger language, the build report states it plainly rather than hiding it, and the Postgres
re-implementation note shows the limitation was designed around, not ignored. Acceptable for this
ticket; the copyability finding above is the one that needs work.
