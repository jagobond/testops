# TESTOPS-102 build report

## Verdict

Implemented, then **amended on the Lead's review**. The code-level criteria stand: the derived
addresses come from `TESTOPS_FOUNDRY_ACCOUNT` / `TESTOPS_AGENT_PROJECT` and report unconfigured when
either is absent, the scan is green and runs in CI as its own job, and the suite is green.

The first version of this report said "the tree carries no deployment identifiers". That was
overstated, and the Lead proved it: an independent scan found 30 identifiers typed by hand into
prose - resource group, registry, storage account, Foundry account and container-app host names -
which the checker never looked for because they have no shape. They are scrubbed now, and the
paragraph below is what the report should have said the first time.

## What changed, per criterion

**AC1 - `testops/judgement/client.py` holds no account, project or host name.** `DEFAULT_PROJECT` is
deleted. Both derived addresses are built from `foundry_account()` and `project_name()`; with either
absent `endpoint()` and `agent_endpoint()` return `""` (no URL is invented) and
`missing_variable()` names the setting that is missing, in that order (account first). The model URL
now uses the *account* as the host and the project only in the path, which is what TESTOPS-101
recorded. `agent.config()` carries `missing` so `Config.why_not` / `foundry_why_not` name the
variable instead of blaming a token; `Config.configured` now requires an endpoint as well.
`/agent-check` gained "Foundry account" and "Project" rows that say which variable supplied each
part, and the endpoint row says `unconfigured: <variable> is not set` rather than describing a
derived URL it did not build. `agent.served_sentence` / `foundry_sentence` say the same.

**AC2 - `agents/narrator/deploy.py`.** The endpoint and agent-name literals are gone. It reads
`TESTOPS_PROJECT_ENDPOINT` and `TESTOPS_AGENT_NAME`, and `required()` exits 2 naming the variable
that is unset. The model deployment name also comes from `TESTOPS_AGENT_MODEL` (default
`deepseek-flash`).

**AC3 - subscription id.** `cost_probe.py` and `scripts/draw_azure_diagram.py` read
`AZURE_SUBSCRIPTION_ID`; both refuse to run without it (cost_probe exits 2 with a sentence, the
diagram prints "(subscription id not set)"). The diagram's output path is now an argument instead of
a home path.

**AC4 - scratch deployment scripts.** `deploy_hello.py`, `invoke_hello.py`, `poll_agent.py` and
`hello.zip` are `git rm`-ed. The small `hello/` source directory stays: it is referenced from the
README as an example and contains no host or identifier.

**AC5 - `scripts/check_no_secrets.py`.** Walks `git ls-files`, prints `file:line: shape: detail` for
each hit, exits 1 with a count, and on a clean tree prints `read N files, no identifiers` and exits
0. Shapes: GUID; absolute home path (`C:\Users\<name>`, `/home/<name>`, `/Users/<name>`);
`*.services.ai.azure.com` / `*.azurecontainerapps.io`; `100.64.0.0/10`; and credential formats,
asked of `testops.services.credential_reason` - the store boundary's own screen. Two narrow
exemptions, both stated in the script and below. `tests/test_no_identifiers.py` pins that every
shape fires and that placeholders do not.

**AC6 - CI.** `.github/workflows/ci.yml` has a separate `no identifiers` job (checkout, Python 3.12,
run the script) on push and pull_request.

**AC7 - `.gitignore`.** `*.zip`, `*.log`, `.tmp/`, `*.bak`, `export/`. Proof:
```
.gitignore:24:*.zip      artifact.zip
.gitignore:12:*.log      app.log
.gitignore:15:.tmp/      .tmp/x
.gitignore:25:*.bak      backup.bak
.gitignore:26:export/    export/project.json
```

**AC8 - `SECURITY.md`.** Policy, what enforces it, what to do if a secret is committed (revoke
first), and the squashed-history/export note.

**AC9 - `docs/DEPLOYING.md`.** Every variable the code reads, derived by grep over `os.environ` /
`getenv` and the constant lookups: `TESTOPS_FOUNDRY_ACCOUNT`, `TESTOPS_AGENT_PROJECT`,
`TESTOPS_AGENT_ENDPOINT`, `TESTOPS_FOUNDRY_ENDPOINT`, `TESTOPS_AGENT_ROUTE_ENDPOINT`,
`TESTOPS_AGENT_MODEL`, `TESTOPS_AGENT_NAME`, `TESTOPS_AGENT_TIMEOUT`, `TESTOPS_AGENT_TOKEN`,
`TESTOPS_AGENT_CLIENT_ID`, `TESTOPS_AGENT_FALLBACK`, `TESTOPS_DATA`, `TESTOPS_HOME`, `TESTOPS_ENV`,
`FOUNDRY_PROJECT_ENDPOINT`, `AZURE_AI_MODEL_DEPLOYMENT_NAME`, `PORT`, `IDENTITY_ENDPOINT`,
`IDENTITY_HEADER`, `FOUNDRY_AGENT_INSTANCE_CLIENT_ID`, `TESTOPS_PROJECT_ENDPOINT`,
`AZURE_SUBSCRIPTION_ID`, `AZURE_DEVOPS_PAT`, `TESTOPS_FLOOR_PYTHON`.

**AC10 - the suite.** The tests that pin the derived URL now configure the account and project
(`example-account` / `example-project`) and pin the unconfigured case as well
(`test_endpoint_and_model_come_from_the_environment`). `test_agent_check.py` configures both
variables in its autouse fixture; `test_agent_foundry.py` sets them where it exercises
`agent.config()`. Nothing was weakened: the URLs, the why-not sentences and the fallback boundary
are asserted as before.

## The scan, before and after

Same script, same rules, run against the tree the branch started from (`c02ac66`) and against the
branch. These counts are **shapes**, not identifiers - the distinction the Lead's scan exposed:

```
before: 362 identifier(s) in 879 tracked files
        (323 home path, 16 tailnet address, 12 azure host, 6 guid, 5 credential)
after:  read 879 files, no identifiers
```

The independent check the Lead asked for greps the tree for the names in the table below. It prints
nothing on this branch; the command is the Lead's own, and writing its pattern out in full would put
the identifiers back into the file you are reading.

The suite: 1423 passed, 4 skipped (7 min 17 s), run with
`env -u PYTHONPATH -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1
C:/Users/Chester/Projects/testops/.venv/Scripts/python.exe -m pytest -q`. The project's own screen
prints `read 880 files, no identifiers`.

## The scrub: names with no shape

The check reads shapes - a GUID, an Azure host name, a tailnet address, a home path. A resource
group called `alpha-beta-1234` typed into a paragraph matches none of them. The Lead's independent
scan found 30 such identifiers; every one of them is one of these eight families, scrubbed in text
and docstrings across `README.md`, `factory/reports/2026-11-24/` (twelve in `azure-deploy.md`
alone), `factory/reports/2026-11-25/TESTOPS-102-build.md`, `factory/tickets/TESTOPS-88.md`,
`factory/tickets/TESTOPS-101.md` and `scripts/draw_azure_diagram.py`:

| was | now |
|---|---|
| the Foundry account name | `<foundry-account>` |
| the app's resource group | `<app-resource-group>` |
| the neighbouring Foundry resource group | `<foundry-resource-group>` |
| the container registry | `<registry>` |
| the storage account (and its file share) | `<storage-account>` / `<file-share>` |
| the container-app default domain label | `<container-app-domain>` |
| the auto-created Log Analytics workspace | `<log-analytics-workspace>` |
| the container apps environment | `<container-apps-environment>` |

**What the checker can and cannot do.** It detects *shapes*. A bare account, registry or
resource-group name typed by hand has no shape, so the script is blind to it, and a green run says
only "no shapes" - not "no identifiers". The guard against the shapeless name is the reviewer's eye
plus the list above; the shape rules exist to catch the whole-host paste, which is the common
accident. `SECURITY.md` now states this limit.

**`scripts/draw_azure_diagram.py` stays, and its labels now come from the environment.** It is a
picture of one deployment, so it cannot use placeholders as code: `RG`, `ACR`, `ENVNAME`, `APP`,
`LOG_ANALYTICS_WORKSPACE`, `FOUNDRY_RG`, `AZURE_SUBSCRIPTION_ID` and `AZURE_SUBSCRIPTION_NAME` are
read at draw time, and the placeholder is what appears when one is unset. The committed PNG was
regenerated with nothing set, so the picture in the tree is the placeholder picture.

**`scripts/deploy_azure.sh` no longer supplies a name.** `RG`, `ACR` and `ENVNAME` are required:

```
: "${RG:?set RG to the target resource group}"
: "${ACR:?set ACR to the container registry name}"
: "${ENVNAME:?set ENVNAME to the container apps environment name}"
```

`LOCATION` keeps `eastus`: a region is not an identity. `APP` keeps `testops`: the application's own
name is product, not somebody's account.

## What I deliberately did not change, and why

- **`DEFAULT_MODEL = "deepseek-flash"` and `DEFAULT_AGENT_NAME = "testops-narrator"` stay.** A model
  deployment name and this repository's own agent name are not account, project or host identifiers;
  both are overridable, the agent name is now required by `deploy.py`, and the ticket names only the
  account, project and host.
- **The store boundary's credential screen is reused, not widened.** The tree check asks only for
  the *format* reasons (`PEM`, JWT, authorization header, known issued prefix, inline URL password).
  The screen's entropy and naming rules are for values a person types into a store; a repository is
  full of SHA-256 digests and of tests that write `key=hunter2` to prove the screen refuses it.
- **Tests are exempt from the credential-format shape only.** Identifier shapes apply to tests:
  they now use `example-account`, a TEST-NET address, a reserved host name and a GUID assembled from
  parts. A test of the screen has to contain the shape it refuses, and a file under `tests/` is not
  where a credential would be deployed from. This exemption is the ticket's own reading
  ("a GUID-shaped identifier outside `tests/`"); everything else is enforced everywhere.
- **`tests/contracts/seed/blobs/` is exempt from the GUID shape.** Those files are verbatim
  third-party source addressed by content hash; rewriting one would change the seed and its
  manifest. Every other shape still applies there.
- **`factory/` history was scrubbed mechanically.** 156 files (prompts, tickets, reports) had
  the developer's home path → `C:/Users/<name>`, the tailnet address → `<tailnet-address>`, the account host
  → `<account>.services.ai.azure.com`, and two sample credentials redacted. The findings and the
  prose are unchanged; this is the one bulk edit in the branch and should be reviewed as a whole.
- **The demo resource names no longer stay anywhere.** An earlier draft kept them in
  `scripts/deploy_azure.sh` as `${VAR:-default}` values on the argument that they are not one of the
  ticket's five shapes. That reading was too narrow: the ticket's rule is that a deployment
  identifier is configuration, and a default is a name this file supplies. The three variables are
  now required, and the prose that carried them says `<placeholder>` instead.

## Residuals

1. **A name with no shape is invisible to the gate.** This is the residual the Lead's scan found: a
   bare account, registry, resource-group or host name typed into prose matches none of the five
   shapes. The scrub above is complete as of this branch, and the list of placeholders is what a
   reviewer checks a new paragraph against. A future paste of the same kind will pass CI.
2. The scan reads text. A credential or identifier assembled at runtime from fragments - or inside a
   `*.png`, `*.zip` or `*.pdf` - is not seen. `tests/test_no_identifiers.py` itself relies on that.
   The committed architecture PNG is now a placeholder rendering, for the same reason.
3. An unlisted credential format is not detected at all; that residual is the store screen's own and
   is stated in its docstring.
4. A real token pasted into a test would pass the scan (tests are exempt from the credential shape).
   Review, not the gate, is what catches it.
5. **A personal GitHub handle remains in the repository coordinates** used by the fixtures and in one
   ticket. It is not one of the ticket's five shapes and it is not one of the six names scrubbed
   here; rewriting it would change repository coordinates and therefore the seeded store and its
   case ids, so it needs a decision and a ticket rather than a rename in this branch. It is the
   largest identifier still in the tree.
6. `factory/TICKETS.md` was not edited: the board is the Lead's, and the ticket row for 102 is still
   missing from it.
7. The agent's own `hello/` package and `scripts/t_*.py` scratch collectors remain; they carry no
   identifier, but they are not product either.
