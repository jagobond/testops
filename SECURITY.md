# Security

This repository is meant to be readable by a colleague and runnable on their own account. Nothing in
it names a person, an account, a subscription, a network or a home directory: the deployment
identifiers arrive from the environment, and the tree is checked for them on every push.

## The policy

- **No credential in the tree.** No token, password, key, connection string or `.env` file is
  committed, in any branch, in any test, in any report. If a value would stop working when it was
  read out loud, it does not belong here.
- **No deployment identifier in the tree.** Subscription ids, tenant ids, Foundry accounts, project
  names used as hosts, container-app host names, tailnet addresses and absolute home paths are
  configuration, not source. A missing one is an honest *unconfigured* state, never an invented
  default pointing at somebody else's tenant.
- **Configuration comes from the environment.** `docs/DEPLOYING.md` lists every variable the
  application reads, with a placeholder and one line of purpose. A `README` or a ticket may name a
  variable; it may not carry its value.
- **The store is not a secret store either.** Service settings hold hosts, repository coordinates
  and paths; credentials resolve from the environment when a connector is called. The store boundary
  refuses a credential-shaped value, and `/agent-check` prints a yes/no for a token, never the token.

## What enforces it

- `scripts/check_no_secrets.py` walks every tracked file (`git ls-files`) and fails on a GUID, an
  absolute home directory, an Azure host name, a tailnet address, and a credential format the store
  boundary already knows. Run it before pushing: `python scripts/check_no_secrets.py`.
- CI runs that check in its own job (`.github/workflows/ci.yml`, `no identifiers`), on every push and
  every pull request, so a red check names itself rather than hiding inside the test suite.
- `.gitignore` keeps `.env`, `*.log`, `.tmp/`, `*.zip`, `*.bak` and `export/` out of the tree in the
  first place.

## What the check cannot see

`check_no_secrets.py` detects **shapes** - a GUID, an absolute home path, an Azure host name, a
tailnet address, a credential format. It is not a list of the deployment's real names, and it could
not be: a resource group, registry or storage account called something unremarkable, typed into a
sentence, matches none of those shapes, so the script reads past it and a green run means "no
shapes were found", never "no identifiers were found". In this ticket's first pass exactly that
happened - thirty hand-typed names sat in prose while the check passed. The guard against the
shapeless name is review: a reader who knows the placeholders (`<foundry-account>`,
`<app-resource-group>`, `<foundry-resource-group>`, `<registry>`, `<storage-account>`,
`<container-app-domain>`, `<log-analytics-workspace>`, `<container-apps-environment>`,
`<file-share>`) and who treats a bare name where a placeholder belongs as a defect. The shapes exist
because the common accident is not a name typed into a sentence but a whole host, path or id pasted
from a terminal, and the paste carries its shape with it.

## If a secret is committed

1. **Revoke it first.** Rotate the token or key at its issuer. A commit can be rewritten; a leaked
   credential has already been copied, and rotating is the only step that actually ends the exposure.
2. Do not "fix" it by deleting the file in a new commit: the value stays in history and in every
   clone. Say so in the ticket and treat it as public from the moment it was pushed.
3. Rewrite history only when the Product Owner asks for it, and say what will happen to open
   branches, forks and clones when you do.
4. Add a line to the ticket saying what leaked, when, who was told, and what was rotated. The ticket
   is the record; a chat message is not.

## On the history

This repository's history is squashed when it is exported to a new organisation: the exported
repository starts from one commit. That is why an old commit cannot leak an identifier into the
export - but it is not a reason to commit one here, because the export is a copy and this history
remains readable by everyone with access to this repository.

Reports under `factory/reports/` are work records, not source. They were written while the
deployment identifiers were still in the build, and they now carry placeholders (`<name>`,
`<account>`, `<tailnet-address>`) in place of the values they observed. The finding is unchanged; the
identifier is gone.
