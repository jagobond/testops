# Provenance of this fixture

This directory is not a synthetic corpus and not original work. It began as a verbatim subset of a
public sample repository, copied here as test data for the duplication analyser; since TESTOPS-103
its text no longer carries the upstream names (see Modifications below).

## Upstream

- Repository: https://github.com/reqnroll/Sample-ReqOverflow (`reqnroll/Sample-ReqOverflow`)
- Commit copied: `78153818b81d7c9a324af81b4e95f65aead705b4` (short form `78153818`), committed
  2026-01-15, message "update dependencies and code cleanup"
- Licence: MIT. Copyright (c) 2013-2024 Reqnroll and Gaspar Nagy, https://www.specsolutions.eu.
  The upstream notice is carried verbatim in `LICENSE` in this directory.

## When and how it arrived

Copied into this repository on 2026-11-22 (commit `768562f`, ticket TESTOPS-21), read back from the
stored snapshot `demo-service-20261120-78153818` of the run `demo-service-dup-20261120T153431`.

## What was copied

Every `.cs` and `.feature` file from the three test projects of the sample - 108 files in total,
18 `.feature` files and 90 `.cs` files. The table names the upstream project, which is what this
document is about; the directory holding each one here carries the neutral name beside it:

| upstream project | here | files | `.feature` | `.cs` |
|---------|---------------|-------|------------|-------|
| `ReqOverflow.Specs.API` | `DemoService.Specs.API` | 31 | 4 | 27 |
| `ReqOverflow.Specs.Controller` | `DemoService.Specs.Controller` | 44 | 10 | 34 |
| `ReqOverflow.Specs.WebUI` | `DemoService.Specs.WebUI` | 33 | 4 | 29 |

## What was left out, and why

- `ReqOverflow.Web` (75 files) - the application under test. The analyser reads test suites, not the
  product; those 75 files would be carried for nothing.
- `ReqOverflow.Tests` (4 files) - unit tests for the sample's own services, outside the BDD suite.
- The three test projects' `.csproj` files (3) - deliberately not copied. This fixture is data for a
  Python analyser, not a buildable .NET project; leaving the project files out means no build target
  exists for CI to pick up (TESTOPS-25 AC5).
- `ReqOverflow.Specs.Controller/Features/_Glossary.md` - documentation, not a scenario or step
  definition.
- Solution and repository-level files: `ReqOverflow.slnx`, `ReqOverflow.ControllerAutomation.slnx`,
  `ReqOverflow.slnx.DotSettings`, `.config/dotnet-tools.json`, `.editorconfig`, `.gitattributes`,
  `.gitignore` and `README.md`. Upstream's root `LICENSE` was not copied to the repository root; the
  same notice is carried in this directory as `LICENSE`.

## Modifications

The copy was modified by TESTOPS-103. The mapping is `scripts/rename_corpus.py`'s table, applied to
every copied file, and for this fixture it is: `ReqOverflow` -> `DemoService` (identifiers, so the
namespaces and type names), `reqoverflow` -> `demo-service` (the slug, the stored run and snapshot
ids this document quotes) and `Sample-ReqOverflow` -> `demo-service` (the repository coordinate the
fixture is stored under). Nothing else was touched: the same 108 files, the same scenarios, steps,
`using` directives, comments and licence header, and the same byte-order-mark difference.

The `LICENSE` file was **not** modified: the copyright line and the permission text are byte for
byte what upstream ships, and `tests/test_third_party_attribution.py` pins their SHA-256.

Together with one mechanical difference that predates the rename: upstream carries a UTF-8
byte-order mark on 21 of the 108 files - all 18 `.feature` files and the three `MSTestSettings.cs`
files - and the copy here does not carry it. No line, comment, copyright line or credential was
altered, added or removed by that. The files are stored in this repository with LF line endings, as
upstream stores them.
