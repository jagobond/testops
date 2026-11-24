# TestOps on Azure

**Live: https://testops.wittymeadow-14b0c4c7.eastus.azurecontainerapps.io/**

Deployed 2026-11-24 for a team walkthrough. Nothing in this deployment touches the FoundryVTT stack
in `rg-foundry-prod`; it has its own resource group and its own registry.

## What exists

| resource | name | notes |
|---|---|---|
| resource group | `rg-testops-demo` | `eastus`. Its own group, so the demo can be deleted in one command |
| container registry | `testopsdemo30562` | Basic tier, admin credentials enabled for the pull secret |
| container apps environment | `testops-env` | default domain `wittymeadow-14b0c4c7.eastus.azurecontainerapps.io` |
| container app | `testops` | 0.25 vCPU / 0.5 Gi, external ingress on port 8080, replicas 1..1 |

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
  `az containerapp update -n testops -g rg-testops-demo --min-replicas 0` when the demo is over.
- **No authentication.** Everything in the store is public repositories (restful-booker-platform,
  cotw-continuity, reqoverflow). A login gate is a product change and belongs through a factory
  ticket, not a deploy-time hack.

## What the demo cannot do

- **Writes do not survive a replica restart.** The container's copy of the database is replaced when
  the image or the replica changes. Analysis runs need network access to GitHub and a PAT, neither
  of which is in the image, so the site is read-only in practice.
- **One replica.** Under a room full of people clicking at once, the single 0.25 vCPU replica will
  queue. Pages are static-rendered from SQLite and answered in ~0.35 s one at a time.

## Redeploying

```bash
RG=rg-testops-demo ACR=testopsdemo30562 ./scripts/deploy_azure.sh
```

The script registers the resource providers, creates the registry if absent, builds
`testops:<timestamp>` in the cloud, and creates or updates the app.

## Tearing it down

```bash
az group delete -n rg-testops-demo --yes --no-wait
```
