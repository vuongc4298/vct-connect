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

report_parameters=()
if [[ "$phase" == 'activation' ]]; then
  # Preserve a previously audited opt-in; initial deployment still defaults off.
  report_env=$(az containerapp list --resource-group VCT_Connect_Service_Bus \
    --query "[?name=='vct-connect-dev-dispatcher'].properties.template.containers[0].env" \
    --only-show-errors --output json)
  report_file=$(mktemp)
  trap 'rm -f "$report_file"' EXIT
  python -c 'import json, sys
rows = json.load(sys.stdin)
env = {e["name"]: e["value"] for e in (rows[0] if rows else []) if "value" in e}
if env.get("TEXT_REPORT_ENABLED") == "true":
    settings = {k: v for k, v in env.items() if k.startswith(("YESCALE_", "TEXT_REPORT_")) and k not in ("TEXT_REPORT_ENABLED", "YESCALE_API_KEY")}
    print(json.dumps({"enableTextReports": {"value": True}, "textReportSettings": {"value": settings}}))' \
    <<< "$report_env" > "$report_file"
  if [[ -s "$report_file" ]]; then
    report_parameters+=("@$report_file")
  fi
fi

az deployment group create \
  --resource-group VCT_Connect_Service_Bus \
  --name "$deployment_prefix-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT" \
  --template-file infra/azure/main.bicep \
  --parameters backendImageDigest="$BACKEND_DIGEST" webImageDigest="$WEB_DIGEST" \
    enableProcessing="$enable_processing" registryName="$REGISTRY_NAME" \
    vaultName="$VAULT_NAME" clerkPublishableKey="$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY" \
    clerkIssuer="$CLERK_ISSUER" "${report_parameters[@]}" \
  --only-show-errors --output none
