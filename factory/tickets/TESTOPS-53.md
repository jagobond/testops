---
id: TESTOPS-53
title: Running the suite must not be able to write to the live store
feature: F2
status: done
autonomy: build
depends_on: TESTOPS-52
---

# TESTOPS-53 - Running the suite must not be able to write to the live store

## Why this exists

`pytest` now includes `tests/contracts`, whose default base URL is the **live server on 8791**, and whose session
fixture POSTs a `contract-audit-<timestamp>` project. So a plain `pytest` against this repo writes to the store the
product is running from. It happened twice during TESTOPS-52 (disclosed and reverted) and once during TESTOPS-7 (seven
empty projects). A test suite that mutates production by default is a hazard that will eventually cost evidence, and it
is the reason every future full run needs a warning label.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The contract suite **starts and owns its own server** on an ephemeral port with a **disposable store** built in a temp dir (seeded with whatever the tests need). No environment variable, no default, no fallback can point it at a persistent store. |
| AC2 | When the suite cannot start its own server it **skips** with a reason - it never falls back to a URL it was not given, and never guesses a host. |
| AC3 | A test pins the prohibition: the suite's configured base must never be the live host/port, and the fixture must refuse to run against a store that is not in a temp directory. Make it fail if somebody reintroduces a live default. |
| AC4 | **Proof by demonstration:** run the full `pytest` suite and show the live store's file hash and project list are byte-identical before and after (`sha256sum` on the db, plus the project list). Include both. |
| AC5 | CI runs the whole suite including contracts, on the temporary server, and fails the build on any contract failure - so the page promises become a gate rather than a report. Show the workflow file and a green local run of the same command. |
| AC6 | The suite still finds the six original failures when pointed at a deliberately broken page (prove one: reintroduce a settled-tone on `Cannot assess` in a scratch copy and watch P4 fail). A gate nobody has seen fail is decoration. |
