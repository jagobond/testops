---
id: TESTOPS-103
title: Nothing in the tree says where it was made
feature: F2
status: building
autonomy: build
depends_on: TESTOPS-102
---

# TESTOPS-103 - A neutral corpus and no home-grown names

## Why

TESTOPS-102 removed the deployment identifiers. This ticket removes the *identities*: Harry's GitHub handle, and the
names of every project the tool was demonstrated on. The repository is going to an enterprise organisation that has its
own repository pairs; a fixture corpus naming a friend's book series, a band's website and a public demo project tells a
reader where the tool came from and what it was pointed at. Both are things his employer should not learn from a clone.

## The rename map

Apply everywhere - code, tests, fixtures, goldens, docs, tickets and reports. Case must be preserved: `COTW`, `CotW`,
`cotw` all map to the same target in their own case; a slug stays a slug.

| was | becomes |
|---|---|
| `jagobond` | `example-org` |
| `cotw-continuity` | `demo-product` |
| `cotw-bdd` | `demo-product-tests` |
| `cotw` (slug, project key, path segment, tag prefix) | `demo-product` |
| `COTW` (tag prefix `@COTW-10.AC4`) | `DEMO` |
| `Children of the Old War` / `CotW` (display names) | `Demo Product` |
| `reqoverflow` | `demo-service` |
| `restful-booker` / `restfulbooker` | `demo-booking` |
| `mwinteringham` | `example-org` |
| `mwtestconsultancy.co.uk` | `example.com` |
| `RuckoldtAndRylander` / `Ruckoldt & Rylander` | `Example and Co` |

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | No tracked file contains any of the names in the table. Prove it with `git ls-files \| grep -v -E '\.(png\|zip\|db)$' \| xargs grep -l -i -E '<the names>'` printing nothing - and paste both the command and the empty result. |
| AC2 | The rename is consistent, not textual-only: a project slug used in a URL, in a case id, in a `@DEMO-10.AC4` tag and in a stored statement agree with each other. Quote one case page rendered after the rename showing the new slug in the tag, the path and the statement. |
| AC3 | `tests/contracts/seed/seed.json` and `tests/contracts/seed/blobs/*` are content-addressed, so the blobs whose text changed no longer match their filenames. Rebuild them: apply the map, recompute the SHA-256 of each rewritten blob, rename the file, rewrite every reference in `seed.json`. A leftover filename that does not equal the hash of its contents is a failure - prove it with a script that recomputes and compares all of them. |
| AC4 | The page goldens under `tests/fixtures/projects_services/` are byte comparisons. Regenerate them through the same render path the tests use, with the same stubs (`app.age` fixed), and confirm one changed line per file rather than a wholesale rewrite. |
| AC5 | `scripts/check_no_secrets.py` gains these names as a forbidden vocabulary, so the guard fails on their return - with a comment saying why a *name* is in a check that otherwise looks for shapes. |
| AC6 | The full suite is green, and the corpus acceptance check (`scripts/replay_levels.py --acceptance`) still passes on a rebuilt run: the verdict counts may shift only if a rename genuinely changed a signature, and if they do, say which and why. |
| AC7 | `THIRD-PARTY-NOTICES.md` is the one exception and keeps the real upstream names, because a copied fixture's licence obliges attribution. Say so in the report, and say plainly what that leaves visible (the fixtures are copies, not this tool's work). |

## Notes for the builder

- Work in a worktree; the main checkout is being read by the Lead.
- Do the mechanical rename with a script, committed alongside, so the mapping is reviewable rather than buried in 3,800 hand edits. Put it in `scripts/rename_corpus.py` with the table as data.
- Fixtures are evidence of a *method*, not of a customer. Where a name appears inside copied third-party source (the seed
  blobs), rewriting it changes a byte-identical copy - that is intended here, but `PROVENANCE.md` must then say the copy
  was modified and how, because a provenance document that claims "no text modified" while the text differs is worse
  than none.
