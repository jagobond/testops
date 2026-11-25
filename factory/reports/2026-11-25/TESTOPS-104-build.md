# TESTOPS-104 build — a fresh install starts with no projects

2026-11-25. Branch `factory/testops-104-no-seed-projects`.

## Shape chosen (AC1)

`LEGACY_PROJECTS` is an **empty dict**, not deleted. The migration's structure is untouched as the
ticket requires: `store/migrate.py` still imports the mapping and `_seed_projects` still runs on a
store below v4, opening its transaction, counting existing projects and looping over the mapping —
with nothing in it, the loop inserts nothing. Deleting the mapping would have removed the one named
seam a pre-TESTOPS-38 store could ever be given projects through, and would have turned a
legitimate no-op into a missing branch. The comment above it in `testops/config.py` says this build
ships with no projects, that a project is added through `/config` as rows, and why the empty mapping
remains.

## AC2 — a fresh store has no projects

```
$ python -c "... db.connect(tempdir/'testops.db'); SELECT COUNT(*) FROM project / service"
store: <tempdir>\testops-104-9pi621nh\testops.db
schema_version: 8
row counts: {'project': 0, 'service': 0}
```

The migration still runs on a **pre-TESTOPS-38** store with the empty seed. New test
`test_a_pre_testsops_38_store_migrates_with_an_empty_seed_and_creates_no_projects` builds the real
v1 fixture (`tests/v1_store.py`, DDL copied from before TESTOPS-3), opens it, and asserts the store
reaches `CURRENT_VERSION`, its case row survives, and `project` / `service` are both 0. The upgrade
ran; it was not skipped.

## AC3 — tests changed

All in `tests/test_projects_services.py`:

- `test_the_migration_brings_the_projects_across_with_their_services` →
  `test_the_migration_seeds_no_projects_and_services_are_added_through_the_store`. It inherited
  the seed's rows. It now asserts the migration writes no project/service row and leaves case rows
  alone, then creates the same four projects and their services through `services.add_project` /
  `services.add_service` — the API `/config` calls — and keeps every original coordinate
  assertion.
- `test_every_case_page_and_the_indexes_are_byte_identical_after_the_migration`. The captured
  `index.html` counts the four configured projects plus run projects. The test now recreates the
  four through the store API before rendering; the byte comparison is unchanged.
- `test_the_cli_resolves_a_project_from_the_store_and_refuses_an_unknown_slug_by_name`. It needed
  `demo-product` to exist after migration. It now adds the projects through the store API first;
  both assertions (resolution succeeds, refusal names the slug and lists the store's projects) are
  unchanged.

A `_add_legacy_projects` helper performs the configuration once, explicitly, with the old
coordinates. New test added for the v1 no-op (above).

## AC4 — the comment

`testops/config.py` above `LEGACY_PROJECTS`: no projects ship; add one through `/config` as rows.
`_seed_projects`' docstring in `testops/store/migrate.py` says the empty mapping makes the upgrade a
legitimate no-op and that an existing store's project rows are never touched. No comment now
describes a seed that no longer exists.

## AC5 — suite and guard

```
1424 passed, 4 skipped in 414.62s
```

One more than TESTOPS-103's 1423 because this ticket adds the pre-38 no-op test. The command is the
one AGENTS.md requires (project `.venv`, environment variables stripped).

```
$ python scripts/check_no_secrets.py
read 886 files, no identifiers and no old names
```

## AC6 — documentation

- `docs/REDACTION.md` **does not exist** in this tree or anywhere in the repository's history
  (`git ls-tree -r HEAD`, `git log --all -- docs/REDACTION.md` — both empty). The ticket's premise
  that it implies a clean tree cannot be acted on; there is no such claim in `README.md`,
  `PRODUCT.md`, `SECURITY.md` or the ADRs.
- `README.md` Quick Start gained a note that a fresh install has no projects, that one is added on
  `/config`, and that the demo slugs in the example commands belong to the fixture corpus, not to a
  new store. The commands otherwise still read as if the projects existed.
- `factory/reports/2026-11-25/TESTOPS-103-build.md:14` carried the old corpus tag prefix literally,
  which `check_no_secrets.py` (TESTOPS-103) refuses. This was red on `main` before this build. The
  sentence now names the prefix by description, not by its forbidden text. Flagged for the Lead as
  an edit to another ticket's report.

## Environment note

The worktree's ignored `data/testops.db` was a stale pre-TESTOPS-103 copy (old corpus ids, schema
v7), which made 28 corpus-pinning tests fail before any source change. It was replaced with the
TESTOPS-103 worktree's build artefact (schema v8, renamed run ids) so the full suite could be run
honestly. Those tests skip in a clean checkout without a store; `main`'s own `data/testops.db` is
also stale and should be refreshed when this is merged.
