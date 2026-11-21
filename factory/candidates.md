# Candidates

Proposals awaiting a glance. Candidates are not commitments; tickets are.

- **`pyproject.toml` package list is stale.** It declares `testops.cases` (a module, not a package)
  and omits `testops.web` and `testops.scripts`. A fresh `pip install -e .` therefore produces an
  install that cannot import the web UI — which matters because the factory builds in worktrees and
  a reviewer needs a reproducible install. Candidate for a hygiene ticket.
- **`testops/cases_dir_backup/`** is debris from the module-shadowing incident. Nothing imports it.
  Candidate for deletion in the same hygiene ticket.
- **Azure spike scripts at the repo root** (`cost_probe.py`, `deploy_hello.py`, `invoke_hello.py`,
  `poll_agent.py`, `hello/`, `hello.zip`, `deploy.log`) are not TestOps product. Candidate to move
  under `spikes/foundry/` so the product root stays legible.

- **TestOps has no tests at all.** `pytest` was not even installed until the scaffolding step;
  the analysers were validated with throwaway scripts whose numbers are now unreproducible
  (`probe_*.py`, agreement/precision runs). Promoted directly to TESTOPS-2 rather than parked
  here, because it blocks the review gate for every other ticket.
