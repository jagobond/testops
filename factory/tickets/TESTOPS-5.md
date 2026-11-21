---
id: TESTOPS-5
title: Sources are declared, not assumed — the capability registry
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-16
---

# TESTOPS-5 — Source capability registry

## Why

TestOps must run at Quilter where the only reachable source is GitHub, through a customised MCP server.
Jira and ADO are not merely missing — they are *blocked by policy*, and no PAT can be created for them.
The product decision (T-D18) is that absence is a declared state, never a zero.

Today the "which sources were missing" list is assembled ad hoc: TESTOPS-14 records config-derived
`sources_missing` in snapshot meta, and the case page renders whatever that string says. There is no
place where a source's state is *declared*, so an analyser cannot ask "can I see requirements?" and a
reader cannot tell "no requirements exist" from "nobody could look".

This ticket builds the registry before any analyser that needs it, so coverage is written against a
declared capability rather than against whatever happens to be configured that day.

## The two states that must never collapse

| store state | meaning | rendered as |
|---|---|---|
| source absent / blocked | nobody looked | `not_assessable`, with the reason and who blocked it |
| source present, returns nothing | we looked, there is nothing | a zero that means zero |

A verdict that treats an absent source as a clean one is the failure this ticket exists to prevent.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | A registry of sources, each declaring an identity and a capability set (requirements, test-execution evidence, code, test code). Adding a source must not require editing an analyser. |
| AC2 | Each source has a state: `available`, `absent`, or `blocked`, with a reason for anything not available ("no credentials and policy forbids creating them"). State comes from explicit configuration or an explicit probe — never from a swallowed exception. |
| AC3 | Every run records the registry state in its snapshot, so a reader can reconstruct what the run could and could not consult without re-probing anything. |
| AC4 | `sources_missing` on a claim is derived from the registry, not from a hard-coded list. A test adds a fake absent source and proves claims that need it come out `not_assessable` with the reason attached. |
| AC5 | An absent source and an empty source produce different verdicts and different sentences — proven from stored rows, in both directions. |
| AC6 | A source that declares `available` but fails when used makes the run fail loudly. Degrading to `absent` mid-run would silently rewrite history. |
| AC7 | The case page's "what could not be checked" section reads the recorded registry state and names the reason, not just the source. |
| AC8 | No credentials in the repo, in logs, or in the database. A test asserts no source requires a secret to be *declared*. |
| AC9 | Verdicts unchanged on the corpus: 94 claims, 90 distinct, 1 unplaced, 1 gap, 2 review. |
| AC10 | Suite green on both interpreters; CI enforced. |

## Notes

- Keep the seam thin. A `SourceKind` with `id`, `capabilities`, `state()` and one rule — never let an
  analyser import a concrete collector.
- The GitHub MCP adapter is explicitly **out of scope**: this ticket declares GitHub as available through
  the existing local/remote git path. Quilter's MCP transport is a later ticket, and the registry is what
  makes that a substitution rather than a rewrite.
- Jira and ADO are configured `blocked` with the Quilter reason, so the product demonstrates the state it
  will actually be in — not a hypothetical.
