---
id: TESTOPS-38
title: A project is a group of services, and a user sets it up without touching code
feature: F2
status: done
autonomy: build
depends_on: TESTOPS-37
---

# TESTOPS-38 — Projects and services

## Why (Product Owner, 22 Nov)

> "The two CotW repos, the CotW Jira board, and the ADO pipelines for the two repos should all be grouped into the
> CotW Project. When I eventually clone the TestOps repo at work, I need to be able to set up other projects that
> will be groupings of other repos, Jira boards and pipelines… a configuration page allows a user to set up
> 'projects', and then to add services to that project."

Read `docs/ADR-1-projects-and-services.md` first; it is the decision this ticket implements.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | The store represents a project (slug, name) and its services (type, role, settings) in their own tables, with the existing `project` column on runs and cases holding the slug. A migration brings `cotw` and `reqoverflow` across with their current resources registered as services. |
| AC2 | **Every existing case page renders byte-identically after the migration.** A test renders a sample of pages before and after and compares. |
| AC3 | A configuration page lists projects and their services and can add, edit and remove a service without a code change and without restarting the server. Adding a whole project is the same operation. |
| AC4 | Each service records its own last-consulted state and reason, and the page's "what could not be checked" section names the service and the reason (not connected / policy / absent). A project with no Jira board says so per service. |
| AC5 | **No secret in configuration.** `service.settings` holds hosts, keys, paths — never a token. A test refuses a settings value that looks like a credential (long high-entropy string, `token`, `password`, `secret`, `Bearer `) and says why. Secrets resolve at call time from the environment. |
| AC6 | **Container-ready:** no absolute host paths in configuration or defaults; the store and blob directory come from one settings object that can point at a mounted volume; `python -m testops.cli serve` runs with only that object set. A test starts the app against a temporary data directory outside the checkout and renders a case page. |
| AC7 | Nothing in the analysis may assume a service exists: a project with a git test repo and no product repo produces `not_assessable` with the reason, not a crash and not a silent zero. |
| AC8 | The CLI takes `--project <slug>` resolved from the store, and refuses an unknown slug by name. Existing invocations used today keep working. |

## Notes

- Deliberately **no** Jira or ADO connector in this ticket. The model first; the connectors land on top of it in the
  next tickets. Building them first would bake in the special case.
- The config page is not authentication-hardened; it is a local tool. Do not add a login. Do add the secret refusal
  in AC5, because that one protects a real harm.
