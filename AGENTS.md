# AGENTS.md — TestOps

## Factory Rule

Product code in `testops/` changes **only** through factory tickets. The Lead writes tickets and
never edits product code; the builder implements, the reviewer judges, the Lead merges.

Applies to every agent that opens this repository, including the Lead acting under time pressure
and including one-line fixes. If the change is worth making, it is worth a ticket; if it is not
worth a ticket, it is not worth making.

What the Lead may edit directly: `factory/**` (tickets, board, features, reports, candidates),
`PRODUCT.md`, `ROLES.md`, `docs/**`, and this file only with the Product Owner's approval.

## Standing additions

- **A missing source is never a zero.** Jira and ADO are absent at Quilter by policy; the tool must
  say "cannot assess" and never "nothing found".
- **No credentials in git, logs, tickets or reports.** Replace with `[REDACTED]`.
- **Versions bump, artefacts are never overwritten.** A re-run writes a new snapshot; it does not
  mutate the previous one.
- **The store is the product's memory.** Analyse and render from the store, never from a live
  source at read time.

## Verification

Run the suite from the project `.venv`, with `PYTHONPATH`, `PYTHONHOME`, `VIRTUAL_ENV` and
`CONDA_PREFIX` stripped and `PYTHONNOUSERSITE=1`, or the result is an environment error rather
than a pass.

## Running without the dev container

A bare checkout is a supported way to **edit**, and an unsupported way to **conclude**. The package
has no runtime dependencies, so `pip install -e ".[dev]"` and `./scripts/verify.sh` are enough to
work; what a bare checkout cannot do is stand in for the matrix. CI is the authority, not a local
pass: the `suite` job proves the 3.11 floor (a 3.12-only construct passes locally and then kills the
process serving the UI), the `identifiers` job proves nothing personal was committed, and the
`image` job proves the container works as the editor's user. Never describe a green local run as
"the suite passes" — say which interpreter, and say CI has not run.

When something does not work — a push refused, tests that fail only here — run
`./scripts/doctor.sh` before changing anything. It reports the interpreter, a stray `PYTHONPATH`, the
identifier guard, remote reachability, TLS trust (the corporate proxy re-signs HTTPS, and that
failure reads like an authentication problem), whether the account may write, and the store's state.
It prints no credential and its push check sends no objects.
