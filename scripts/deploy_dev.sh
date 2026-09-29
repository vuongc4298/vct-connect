#!/usr/bin/env bash
set -euo pipefail

phase="${1:-}"
if [[ $# -ne 1 ]]; then
  echo 'Usage: scripts/deploy_dev.sh baseline|activation' >&2
  exit 2
fi

case "$phase" in
  baseline)
    deployment_prefix='vct-base'
    enable_processing='false'
    ;;
  activation)
    deployment_prefix='vct-active'
    enable_processing='true'
    ;;
  *)
    echo 'Invalid deployment phase; expected baseline or activation.' >&2
    exit 2
    ;;
esac

required_variables=(
  GITHUB_RUN_ID GITHUB_RUN_ATTEMPT BACKEND_DIGEST WEB_DIGEST
  REGISTRY_NAME VAULT_NAME NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY CLERK_ISSUER
)
for variable in "${required_variables[@]}"; do
  if [[ -z "${!variable:-}" ]]; then
    echo "Missing required deployment variable: $variable" >&2
    exit 2
  fi
done

if [[ ! "$GITHUB_RUN_ID" =~ ^[0-9]+$ || ! "$GITHUB_RUN_ATTEMPT" =~ ^[0-9]+$ ]]; then
  echo 'Invalid deployment run identifier; expected numeric run ID and attempt.' >&2
  exit 2
fi

if [[ ! "$BACKEND_DIGEST" =~ ^sha256:[0-9a-f]{64}$ || ! "$WEB_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo 'Invalid image digest; expected sha256 followed by 64 lowercase hex digits.' >&2
  exit 2
fi

az deployment group create \
  --resource-group VCT_Connect_Service_Bus \
  --name "$deployment_prefix-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT" \
  --template-file infra/azure/main.bicep \
  --parameters backendImageDigest="$BACKEND_DIGEST" webImageDigest="$WEB_DIGEST" \
    enableProcessing="$enable_processing" registryName="$REGISTRY_NAME" \
    vaultName="$VAULT_NAME" clerkPublishableKey="$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY" \
    clerkIssuer="$CLERK_ISSUER" \
  --only-show-errors --output none
