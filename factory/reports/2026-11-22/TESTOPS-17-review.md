# TESTOPS-17 review — No registry, no verdict

## Verdict — PASS

The three source states are held apart end to end — writer default, CHECK constraint, read model,
page sentence — every lie I could reach through the store was refused or degraded to "not assessed",
the migration on a real pre-v3 store kept the registry-backed assessment and demoted the default,
and the corpus did not move.

## Criteria

- **AC1 HOLDS.** `sources_assessed` (0/1) is stored beside `sources_missing`, and `claim_view`
  exposes a named `sources_state` (`not_assessed` / `none_missing` / `some_missing`,
  `testops/queries.py:97`) so no caller infers state from a falsy list. Probed: defaults give
  `not_assessed`; `assessed=True, missing=[]` gives `none_missing`. Not the same value.
- **AC2 HOLDS.** A never-assessed claim renders "Nothing was checked against any source for this
  claim, so nothing here says its sources were clean" — not a blank, not an exception
  (`testops/web/app.py:364`). Reached by writing with writer defaults and reading back through
  `claim_read` → `section_unchecked`.
- **AC3 HOLDS.** The assessed-none-missing claim keeps "Every source needed for this claim was
  available", guarded by `state == queries.SOURCES_NONE_MISSING and not recorded`. Rendered all
  three sentences from one store; all three are distinct strings and none overclaims (the
  not-assessed and some-missing sentences both explicitly deny cleanliness).
- **AC4 HOLDS.** Writer default yields `sources_assessed=0, sources_missing=NULL`; `add_claim`
  silently coerces a list passed without the flag to `not_assessed` (`testops/store/db.py:130`);
  the CHECK `claim_sources_assessed_pairing` refuses `assessed=1` with NULL and `assessed=0` with a
  list even on raw SQL INSERT. A rogue row that dodged the CHECK is refused again at the read model
  (`_sources_state` raises). Two independent layers.
- **AC5 HOLDS.** `tests/test_sources_assessed.py` (378 lines) asserts all three states from stored
  rows with the exact sentence for each; suite green: **177 passed**, 16s.
- **AC6 HOLDS.** Migrated the verbatim v2 fixture (`tests/v2_store.py`, DDL copied from c880a7d):
  claim 1 (snapshot records registry) → `assessed=1`, list kept, `some_missing`; claim 2 (same
  stored list, no registry meta) → `assessed=0`, list dropped, `not_assessed`. Counts: 1 assessed /
  1 not. The real store (migrated by the builder) reads: 723 v1 claims all `not assessed`, 282
  assessed, 282 not — no invented assessment anywhere.
- **AC7 HOLDS.** `scripts/replay_levels.py --acceptance` on the newest levels snapshot
  (`demo-product-levels-…`, test `a3f19853` / product `b901ea4d`): **94 claims, 90 distinct, 1 unplaced,
  1 gap, 2 review — PASS.**
- **AC8 WEAK (HOLDS via CI).** Green here on the repo venv (Python 3.12), 177 passed. No 3.11
  interpreter on this machine; the branch is pushed and `.github/workflows/ci.yml` runs the
  3.11/3.12 matrix — the same mechanism TESTOPS-5's review accepted.

## Trying to lie

Bypassed the pipeline exactly as for TESTOPS-5, writing claims straight at the database:

1. **Writer's defaults, nothing passed** → stored `(0, NULL)`, renders the not-assessed sentence.
   The clean bill is not reachable.
2. **`sources_missing=[]` with no assessment flag** (the TESTOPS-5 lie) → the writer rule coerces
   to `(0, NULL)`; the empty list is discarded, not promoted. Renders "Nothing was checked…".
3. **A named missing list with no flag** (`["jira"]`) → same coercion to not-assessed.
4. **`sources_assessed=True` with no list** → refused by the CHECK at INSERT
   ("assessed" with nothing to show).
5. **Raw SQL `assessed=0` with a list** → CHECK refuses.
6. **Raw SQL `assessed=1` with NULL** → CHECK refuses.
7. **A row written around the store entirely** (temp table without the CHECK) → the read model's
   `_sources_state` raises `ValueError` on both contradictions; loud, not plausible.
8. **Sentence-hunting**: the clean-bill string exists once in `testops/web/app.py:378`, inside the
   `SOURCES_NONE_MISSING` branch only. No path from `not_assessed` reaches it.
9. **Migration lie**: built the pre-v3 store with both claims carrying the *same* missing list, so a
   migration that judged by the list would promote claim 2. It did not — it judged by the snapshot.
   Corrupting the snapshot's meta to unparseable JSON and migrating again gave `not assessed` for
   that claim, list dropped, nothing invented.

Nothing lied. The only "loss" anywhere is attempt 3's silent list-discard (see concerns).

## Three sharpest concerns

1. **The clean bill has zero corpus witnesses.** Of 1287 claims in `data/testops.db`, 1005 are
   `not assessed` and 282 are `some_missing`; not one is `none_missing`, so the sentence this ticket
   protects is rendered in this corpus exactly zero times. The guard is proven by fixtures only —
   the same shape of gap TESTOPS-16's review recorded for its state (b). The next corpus with a
   fully-connected run should be checked against it.
2. **`add_claim` silently discards a passed list when the flag is falsy.** Honest direction (it can
   never manufacture a clean bill), but a caller that computed a real missing list and forgot the
   flag loses the fact without any signal. A raise would be stricter than a coercion; worth a
   decision in a later ticket rather than a docstring sentence.
3. **Migration is once-only and keyed on column existence.** A store that migrated wrongly (e.g. a
   registry meta that was corrupt at migration time) can never re-derive its source state — the
   `sources_assessed` column's presence short-circuits `prepare`. Idempotent and safe, but
   uncorrectable without a new column; the tradeoff deserves a line in `migrate.py`'s header, not
   just a docstring.

Also noted, per the ticket: the probe-swallowing limit (a probe that hides its own exception can
still misreport its state, and no store API can audit that) remains a known limit, out of scope here
as declared.

## Demo

**The problem.** A claim written with the analyser's default empty missing list — or any claim whose
sources were simply never looked at — rendered "Every source needed for this claim was available": a
guarantee manufactured by absence of information.

**What changed.** Whether a registry was consulted is now stored (`sources_assessed`), paired with
what it said (`sources_missing`) by a CHECK, surfaced as a named `sources_state` in the read model,
and the page sentence comes from the state. The default is "not assessed", and "not assessed" has
its own honest sentence. The migration settles existing claims from their snapshot's registry
record, never from the list they happen to carry.

**How we know it works.** 177 tests green; nine bypass attempts in this review all refused or
demoted to the honest sentence (details above); the verbatim v2 fixture migrates 1/1 (kept list vs
dropped list on identical rows); the real store shows 723 v1 + 282 v2 claims reading "not assessed"
and 282 keeping their assessments; corpus replay acceptance PASS at 94/90/1/1/2.

**What it does not solve.** The clean-bill state is corpus-unwitnessed (concern 1); a dropped list
at the writer is silent (concern 2); a migrated store's decision is irreversible (concern 3); and
the probe-integrity limit is unchanged.

**Where to look.** `testops/store/schema.sql:92` (CHECK), `testops/store/db.py:130` (writer rule),
`testops/store/migrate.py:120` (`_upgrade_claim_sources_to_v3`), `testops/queries.py:97`
(`_sources_state`), `testops/web/app.py:364` (three sentences), `tests/test_sources_assessed.py`,
`tests/v2_store.py`.
