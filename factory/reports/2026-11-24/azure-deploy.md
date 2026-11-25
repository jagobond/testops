# TestOps on Azure

**Live: https://<container-app-domain>.azurecontainerapps.io/**

Deployed 2026-11-24 for a team walkthrough. Nothing in this deployment touches the FoundryVTT stack
in `<foundry-resource-group>`; it has its own resource group and its own registry.

## What exists

| resource | name | notes |
|---|---|---|
| resource group | `<app-resource-group>` | `eastus`. Its own group, so the demo can be deleted in one command |
| container registry | `<registry>` | Basic tier, admin credentials enabled for the pull secret |
| container apps environment | `<container-apps-environment>` | default domain `<container-app-domain>.azurecontainerapps.io` |
| container app | `testops` | 0.25 vCPU / 0.5 Gi, external ingress on port 8080, replicas 1..1 |
| storage account | `<storage-account>` | Standard_LRS, share `<file-share>` mounted at `/app/data` |
| Log Analytics | `<log-analytics-workspace>` | container stdout |

## Why these choices

- **Built by ACR Tasks, not on the laptop.** `az acr build` compiles the image in Azure, so a stopped
  Docker daemon does not block a deploy. The first attempt died on exactly that.
- **eastus, not uksouth.** uksouth had no capacity for this subscription's Container Apps plan.
- **The store is baked into the image.** `data/testops.db` and `data/blobs/` are copied in at build
  time, so the first page a visitor opens is a finished analysis of a real repository pair rather
  than an empty database waiting for a GitHub PAT and a network fetch.
- **`min-replicas 1` for the demo.** Scale-to-zero would add several seconds of cold start to the
  first page a colleague opens. While the minimum is 1 the app costs on the order of pennies a day;
  drop it back to 0 with
  `az containerapp update -n testops -g <app-resource-group> --min-replicas 0` when the demo is over.
- **The store is on Azure Files, so the ledger survives a restart.** The image still ships a seeded store, but
  `/app/data` is mounted from `<storage-account>`, so views, calls, cached explanations and votes outlive a revision
  restart. Verified: a vote was cast, the revision restarted, and the report still showed `Helped 1`, 4 views, 4,028
  tokens. Without the mount, the whole A/B would reset every deploy.
- **Managed identity is assigned but IMDS is unreachable from this container** (`Errno 111 Connection refused` to
  169.254.169.254 on both `2018-02-01` and `2019-08-01`). So the token is a **Container App secret**
  (`testops-agent-token`, exposed as `TESTOPS_AGENT_TOKEN=secretref:...`), not a key in the image or the repo. That is a
  deliberate trade recorded here: the identity path is the better design and does not work in this environment.
- **No authentication.** Everything in the store is public repositories (demo-booking-platform,
  demo-product, demo-service). A login gate is a product change and belongs through a factory
  ticket, not a deploy-time hack.

## What the demo cannot do

- **Writes do not survive a replica restart.** The container's copy of the database is replaced when
  the image or the replica changes. Analysis runs need network access to GitHub and a PAT, neither
  of which is in the image, so the site is read-only in practice.
- **One replica.** Under a room full of people clicking at once, the single 0.25 vCPU replica will
  queue. Pages are static-rendered from SQLite and answered in ~0.35 s one at a time.

## Redeploying

```bash
RG=<app-resource-group> ACR=<registry> ./scripts/deploy_azure.sh
```

The script registers the resource providers, creates the registry if absent, builds
`testops:<timestamp>` in the cloud, and creates or updates the app.

## Tearing it down

```bash
az group delete -n <app-resource-group> --yes --no-wait
```


## 24 November, evening - the Foundry agent route goes live

`?agent=foundry` now renders an explanation produced by the hosted Foundry agent `testops-narrator`, and the page names
the route that served it (`served by: foundry-hosted-agent`). `?agent=on` (this build's own model call) and `?agent=off`
are unchanged. Verified live at 19:5x:

    off      no explanation, 0.4 s
    on       explanation from the model route, 3.0 s
    foundry  explanation from the hosted agent, route named, 7.0 s
    /agent-report  routes side by side: model-route 2 calls 4021 tokens; foundry 1 call 2068 tokens

### Configuration that the deployment needs (and why)

| variable | value | why |
|---|---|---|
| `TESTOPS_FOUNDRY_ENDPOINT` | `.../openai/v1/chat/completions` | the **model** route; once renamed to the project base it 404s |
| `TESTOPS_AGENT_TOKEN` | secret `testops-agent-token` | api-key for the hosted agent's responses endpoint |
| `TESTOPS_AGENT_PROJECT` | `testops` | the **project** name, which is not the account name - the code's default derived `projects/<foundry-account>` and every call 404'd |
| `TESTOPS_AGENT_ROUTE_ENDPOINT` | full agent responses URL | the explicit override; the derived form was wrong for this account/project pair |
| `TESTOPS_AGENT_TIMEOUT` | `60` | the agent's first call in a fresh session can take far longer than the 20 s default |

### Two failures worth remembering

- **SQLite on an Azure Files share does not survive a migration.** v5 would not start: two revisions were warm, each
  opened the mounted `testops.db`, and `ALTER TABLE agent_call ADD COLUMN route ...` died with `database is locked`.
  Deactivating the old revision did not clear it; the mount was removed for the demo and the site now runs on the baked
  store again. **Consequence: votes and cached explanations do not survive a revision restart.** Measured pages still
  work; a post-demo ticket replaces the storage rather than re-mounting SQLite over SMB.
- **A stale environment variable can break the other route.** `TESTOPS_AGENT_ENDPOINT` looked like the agent's override
  but is the *first* name in the model route's endpoint list, so setting it to the project base made `?agent=on` 404
  while `?agent=foundry` worked. The agent route's real override is `TESTOPS_AGENT_ROUTE_ENDPOINT`.
