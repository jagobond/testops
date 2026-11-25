---
id: TESTOPS-51
title: The credential screen applies to every field, and a project can be deleted
feature: F1
status: done
autonomy: build
depends_on: TESTOPS-7
---

# TESTOPS-51 - The credential screen applies to every field

## Why this exists

A blind author typed `password=hunter2` into the service **Name** field. It was accepted, stored, and echoed back on
`/config`. The same value in the **repo** field is refused with HTTP 400 and a clear reason. The screen exists and is
applied per-field, so every field somebody adds later inherits the hole. `hunter2` is a joke; a real key pasted into the
wrong box is not.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | **One shared check**, applied to every user-supplied settings value and every human-entered name - present and future. A new field cannot opt out by existing; the check is applied at the boundary (the settings write path and the service/project create-edit paths), not sprinkled per field. |
| AC2 | Refusal is HTTP 400 with a reason a reader can act on, in the same non-blaming voice as the existing `repo` refusal, and the value is **neither stored nor echoed** - not in the form, not in the listing, not in the error page. |
| AC3 | Detection covers at least: `name=value` pairs whose name looks like a credential (`password`, `passwd`, `pwd`, `token`, `api_key`, `apikey`, `secret`, `bearer`, `authorization`, `private_key`, `access_key`, `client_secret`); issued-token prefixes (`ghp_`, `gho_`, `ghs_`, `github_pat_`, `sk-`, `AKIA`, `xoxb-`, `xoxp-`); PEM private-key blocks; and JWTs (`eyJ...` with three dot-separated segments). |
| AC4 | **False positives are refused too.** These must all be accepted: `example-org/demo-product`, `Jira board DEMO`, `ExampleAndCo`, `demo-product pipeline #2`, `example-org/demo-booking-platform`, `<tailnet-address>`, `localhost:8791`, `https://github.com/org/repo.git`, `DEMO`, `TOPS`, `test password reset flow`. Pinned by test - a screen that refuses ordinary words is worse than none. |
| AC5 | A test proves the screen is **not bypassable through a second path**: the same value posted to the service form, the project-create form and any inline settings edit is refused on every route, and the store shows no row was written. |
| AC6 | **A project can be deleted** from `/config` when it holds no runs, snapshots or cases; the control states what it will remove. A project that holds evidence refuses with a reason naming the counts - evidence is immutable and is not deleted by a config action. This retires the `contract-audit-*` accumulation the contract suite causes. |
| AC7 | The contract suite's **P23** test passes and no other contract test regresses; the suite is not edited by this ticket. |
| AC8 | Full suite green, case-page goldens unchanged (this ticket changes no case page). |
