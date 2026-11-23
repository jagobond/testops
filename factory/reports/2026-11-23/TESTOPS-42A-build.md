# TESTOPS-42A build — the seam, detection, and a counted inventory

**Authorship note.** The builder session wrote all of this and verified it, then hit its iteration limit before
committing and before writing this report. The Lead wrote this file afterwards from the builder's own closing summary
and from the tree on disk, ran the suite once on the resulting tree, and committed. No product code was written or
changed by the Lead. The reviewer should treat every claim below as the builder's claim and verify it independently.

## What is in the tree

- `testops/extract/ecosystems/` — the protocol (`detect(files)`, `bindings(files)`, `drivers(files)`, declared name) and
  a registry that raises on duplicate names, on ambiguity, and on no match (`UnknownEcosystem`). No silent default.
  - `reqnroll` — supported; re-exports `BINDING`, `SIGNALS` and `LAYER_ORDER` so the .NET path is the same code, moved.
  - `cucumber_js`, `python_bdd` — detected, but `bindings`/`drivers` raise `UnsupportedEcosystem`. They never return
    `[]`, because an empty list is the lie TESTOPS-39 caught.
- Pipeline, rebuild and sources route extraction through the module; snapshot metadata records `ecosystems` per
  repository; a detected-but-unsupported test arm makes the run `not_assessable` with zero claims; `sources` rebuilds
  that sentence from the record, and the run page, runs index and blind-spot grouping print it.
- `docs/ecosystem-inventory-cucumber-js.md` — the deliverable. Counts from the stored blobs, a per-ecosystem vocabulary
  finding, and a 6.25-day per-piece estimate.
- `tests/test_ecosystems.py` — 15 tests covering AC1–AC5 and AC7.

## Verification, as the builder left it

- **AC3, proven live rather than by absence:** a levels run rebuilt over the stored CotW blobs gives 94 claims / 90
  distinct / 2 review / 1 unplaced / 1 gap — identical to the stored run; ReqOverflow duplication gives 17 duplicate
  claims in 17 cases; case-page goldens byte-identical.
- **AC4 on `restfulbooker`:** the run is `not_assessable`, the sentence reads "cucumber-js is unsupported: this build can
  recognise JavaScript step definitions and cannot read them, so it will not guess what they do", the page prints "44
  cucumber-js step-binding declarations in 5 files", and neither banned phrase ("no layers found", "steps could not be
  tied to a layer") appears.
- **Suite on the committed tree:** `579 passed` in 138s. (Run by the Lead, after the builder's own 579-passed run on the
  same tree.)

## The finding that changes T42-C

The layer vocabulary **must be per-ecosystem**, and the reason is measured, not argued:

- .NET recognises **type names** (`IPage`, `HttpClient`, `IMediator`, `DbContext`); JS must recognise **call names**
  (`cy.get`, `cy.request`, `fetch(`).
- .NET's driver is a class in a `*Driver.cs` file; Cypress's is a command registered at runtime, whose name appears in no
  filename. `build_driver_map` finds 0 drivers here, correctly, because there are none.
- .NET's per-file layer is right because a step file names its driver class. Cypress's per-file layer is **wrong**:
  `room-management.js` holds UI and API commands side by side (measured: 11 commands, 2 files, both layers in both).
- `LAYER_ORDER` and the analysers stay shared — the layer names are the vocabulary the verdicts are written in.

A complete cucumber-js extractor turns this corpus from **0 of 43** assertions placed into **17 of 43**, with 26
unplaced for a true, actionable reason (the feature text names messages no binding matches). Any ticket promising 43
clean claims would be lying about the corpus.

## Cost

6.25 engineering days, itemised in the inventory: scanner 0.5, matcher 0.5, scoping 0.25, custom-command model 1.5,
JS/TS vocabulary 1, call-graph inference 1.5, tests 1. Pipeline wiring was paid by this ticket.

## State of the worktree

A copy of the live store sits in `data/` in this worktree, gitignored, so the real-corpus tests ran rather than skipped.
It is not committed and should be deleted when the worktree is pruned.
