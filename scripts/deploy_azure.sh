#!/usr/bin/env bash
# Deploy TestOps to Azure Container Apps.
#
# Nothing here builds on this laptop: the image is built by ACR Tasks (`az acr build`), so the
# deploy works whether or not a Docker daemon is running locally. That is deliberate - the first
# attempt failed for exactly that reason.
#
# Everything lands in its own resource group. The FoundryVTT stack in rg-foundry-prod is not
# touched, named, or queried by this script.
set -euo pipefail

RG="${RG:-rg-testops-demo}"
LOCATION="${LOCATION:-eastus}"          # eastus, not uksouth: uksouth had no capacity for this
ACR="${ACR:-testopsdemo30562}"
ENVNAME="${ENVNAME:-testops-env}"
APP="${APP:-testops}"
TAG="${TAG:-$(date +%Y%m%d-%H%M%S)}"
IMAGE="$ACR.azurecr.io/testops:$TAG"

echo "== providers"
for ns in Microsoft.App Microsoft.ContainerRegistry Microsoft.OperationalInsights; do
  state=$(az provider show -n "$ns" --query registrationState -o tsv)
  if [ "$state" != "Registered" ]; then
    echo "registering $ns (was $state)"
    az provider register -n "$ns" --wait >/dev/null
  fi
done

echo "== resource group $RG in $LOCATION"
az group create -n "$RG" -l "$LOCATION" -o none

echo "== registry $ACR (Basic: the cheapest tier that can hold an image)"
if ! az acr show -n "$ACR" -o none 2>/dev/null; then
  az acr create -n "$ACR" -g "$RG" --sku Basic --location "$LOCATION" -o none
fi
az acr update -n "$ACR" --admin-enabled true -o none

echo "== build $IMAGE in the cloud"
az acr build -r "$ACR" -t "testops:$TAG" -f Dockerfile . -o none

ACR_USER=$(az acr credential show -n "$ACR" --query username -o tsv)
ACR_PASS=$(az acr credential show -n "$ACR" --query 'passwords[0].value' -o tsv)

echo "== container apps environment $ENVNAME"
if ! az containerapp env show -n "$ENVNAME" -g "$RG" -o none 2>/dev/null; then
  az containerapp env create -n "$ENVNAME" -g "$RG" --location "$LOCATION" -o none
fi

echo "== app $APP"
# min-replicas 0: it costs nothing while nobody is looking at it, and the first request after a
# quiet spell pays a few seconds of cold start. max-replicas 1: this is a demo, not a service.
if az containerapp show -n "$APP" -g "$RG" -o none 2>/dev/null; then
  az containerapp registry set -n "$APP" -g "$RG" --server "$ACR.azurecr.io" --username "$ACR_USER" --password "$ACR_PASS" -o none
  az containerapp update -n "$APP" -g "$RG" --image "$IMAGE" -o none
else
  az containerapp create -n "$APP" -g "$RG" --environment "$ENVNAME" \
    --image "$IMAGE" --target-port 8080 --ingress external \
    --registry-server "$ACR.azurecr.io" --registry-username "$ACR_USER" --registry-password "$ACR_PASS" \
    --cpu 0.25 --memory 0.5Gi --min-replicas 0 --max-replicas 1 -o none
fi

FQDN=$(az containerapp show -n "$APP" -g "$RG" --query 'properties.configuration.ingress.fqdn' -o tsv)
echo
echo "TestOps: https://$FQDN"
echo "image:   $IMAGE"
