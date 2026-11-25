# TESTOPS-103 build - nothing in the tree says where it was made

2026-11-25. Branch `factory/testops-103-neutral-corpus`, merged to `main`.

**This report was written by the Lead, not the builder.** The builder staged its work, then exited non-zero without
committing or filing anything - the same failure as TESTOPS-102's first run. Everything below is what the Lead
verified afterwards, by running the checks rather than reading a summary.

## What changed

- The corpus was renamed across code, tests, fixtures, page goldens, the content-addressed seed and the docs, through
  `scripts/rename_corpus.py` (a data table, not hand edits). Old -> new: the private project keys became
  `demo-product` / `demo-service` / `demo-booking`, the two personal handles became `example-org`, and the tag prefix
  that named the old corpus became `@DEMO-n`.
- `tests/contracts/seed/blobs/*` are named by the SHA-256 of their contents, so each rewritten blob was rehashed,
  renamed and its reference in `seed.json` updated. **Verified independently: 187 blobs, 0 whose filename disagrees
  with its contents.**
- The page goldens under `tests/fixtures/projects_services/` were regenerated through the render path: 16 files, and a
  scan of them for the old names returns **0**.
- `scripts/check_no_secrets.py` gained the names as a forbidden vocabulary, so the guard now fails on their return
  rather than only on shapes.

## Verification

| check | result |
|---|---|
| old names anywhere in the tracked tree | only the three attribution artefacts (below) |
| seed blob hashes | 187 blobs, 0 mismatched |
| goldens | 16 files, 0 occurrences |
| suite | **1423 passed, 4 skipped** - the same count as before the rename, so nothing was lost in the churn |
| export guard (`scripts/check_no_secrets.py` on the export) | `read 877 files, no identifiers and no old names` |

## The one deliberate exception

`THIRD-PARTY-NOTICES.md`, `tests/fixtures/demo-service/PROVENANCE.md` and the test that asserts the attribution stays
keep the real upstream name, because the fixtures are copies and the licence obliges attribution. `PROVENANCE.md` now
states that the copies were **modified** and how. Removing these requires replacing the copied corpus with synthetic
fixtures, which is a separate piece of work and the honest way to reach a tree with no third-party names at all.

## Export hygiene

`scripts/export_clean.sh` drops `scripts/rename_corpus.py` (the mapping table names what was removed) and replaces the
mapping table in this ticket with a pointer. A copy that shipped either would leak exactly what the ticket took out.

## Residuals

- The corpus is renamed, not anonymised: `demo-booking` is still a hotel-booking product, recognisable to anyone who
  knows the upstream. If a colleague must not be able to tell what was tested, synthetic fixtures are the fix.
- `scripts/rename_corpus.py` lives on in the private repository, which is correct - it is the record of the mapping.
