# ADR-1 — A project is a group of services

**Status:** accepted 2026-11-22 (Product Owner). **Supersedes:** nothing. **Blocks:** Jira and ADO source
connectors, and any second team's use of TestOps.

## Context

TestOps today identifies a "project" by a free-text string on the run and case rows, set by the CLI
(`--project demo-product`). The Demo Product work needs more than that: two git repositories, a Jira board and two ADO pipelines
all belong to one thing a person calls "the Demo Product project". At Quilter the same shape repeats with different
resources. Nothing in the schema can express it, so every new source would arrive as another special case keyed by
that string.

The Product Owner's words: *"a configuration page allows a user to set up 'projects', and then to add services to
that project. TestOps then treats those project resources as single groups of context/analysable data."*

## Decision

**A project is an identity. A service is a resource inside it.**

- **Project** — a slug, a display name, and nothing else. It owns no data and knows no technology.
- **Service** — one analysable resource, typed by connector: `git_repo` (role: `product` or `test`), `jira_board`,
  `ado_pipeline`. Carries its own settings and its own credentials *reference* (never the secret).
- **Run** records which services it consulted, which it could not, and why — the existing `not_assessable`
  discipline, applied per service rather than per analyser.

Existing rows keep working: `project` stays the column and holds the project slug. `demo-product` and `demo-service` become
two projects with their current resources registered, and every existing page renders unchanged.

## Consequences

1. **No analysis may assume a service exists.** A project with a git test repo and no Jira board must produce a
   page that says the board was not connected — which the honesty rules already demand, now with a real reason.
2. **Adding a service is configuration, not code** — a new row and, at most, a new connector module. Adding a
   *project* must require no code at all.
3. **Credentials are references.** `service.settings` may hold a host name, a project key, a repo path; it may never
   hold a token. Secrets resolve from the environment or the OS keyring at call time. A config file that leaks is
   not the same failure as a database that leaks, and we are not having the first.
4. **The web app must stay containerisable.** No absolute Windows paths in config, storage reached through the
   existing content-addressed blob layer, and the UI must run with `data/` mounted rather than embedded. This is
   the "will run on Azure/Foundry later" constraint arriving as a design rule rather than a rewrite.
5. **Order of work:** the model and the config page come *before* the Jira and ADO connectors. Building connectors
   first would bake the special case in and we would migrate twice.

## Not decided here

Whether a service can belong to two projects (shared libraries, shared boards). Start with one; if a real case
appears, add the join table then rather than guessing now.
