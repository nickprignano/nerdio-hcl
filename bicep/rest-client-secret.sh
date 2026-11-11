#!/usr/bin/env bash
# Creates the Nerdio REST API client secret and writes it straight to the stage 1 Key Vault, for
# the Bicep variant (decision 0015, bicep/README.md). Thin glue: the Microsoft Graph Bicep
# extension can't create client secrets, so this one step is a script.
#
# The value goes from Entra to Key Vault through a pipe. It is never printed, never in a variable,
# a file, an argument or a deployment, so no state or log holds it. Stage 2 reads it from Key Vault.
#
# Run it as the tenant owner in Cloud Shell (Bash), after identity.bicep and the platform stack:
#   bicep/rest-client-secret.sh
# Run it again to rotate. It replaces every password on the REST API client app, so only the new
# one works afterwards.
#
# Settings (environment variables, all optional):
#   ANSWERS      answers file (default environments/example/01-platform/setup.auto.tfvars.json)
#   STACK        platform stack name (default nerdio-<prefix>-platform)
#   IDENTITY     identity deployment name (default nerdio-identity)
#   SECRET_DAYS  secret lifetime in days (default 365, as in the Terraform module)
set -euo pipefail

ANSWERS="${ANSWERS:-environments/example/01-platform/setup.auto.tfvars.json}"
[ -f "$ANSWERS" ] || { echo "No answers file at $ANSWERS. Run ./nerdio init first." >&2; exit 1; }
prefix="$(jq -r .prefix "$ANSWERS")"
STACK="${STACK:-nerdio-$prefix-platform}"
IDENTITY="${IDENTITY:-nerdio-identity}"
SECRET_DAYS="${SECRET_DAYS:-365}"

app="$(az deployment sub show --only-show-errors --name "$IDENTITY" \
  --query properties.outputs.rest_api_client_object_id.value -o tsv)"
[ -n "$app" ] || { echo "Deployment $IDENTITY has no REST API client app (create_rest_api_client off?)." >&2; exit 1; }

kv="$(az stack sub show --only-show-errors --name "$STACK" \
  --query outputs.nerdio_config_inputs.value.nme_key_vault -o json)"
[ "$kv" != "null" ] && [ -n "$kv" ] || { echo "Stack $STACK has no Key Vault (nme_secret_store isn't key_vault)." >&2; exit 1; }
vault="$(jq -r '.id | split("/") | last' <<<"$kv")"
name="$(jq -r .secret_name <<<"$kv")"

# The Secrets Officer role from the stack can take a few minutes to apply. Check before creating
# the secret, so a refusal doesn't leave a new password that nothing holds.
for i in $(seq 1 12); do
  az keyvault secret list --only-show-errors --vault-name "$vault" --maxresults 1 -o none 2>/dev/null && break
  [ "$i" = 12 ] && { echo "Can't write to Key Vault $vault yet. Check you hold Key Vault Secrets Officer on it (deployer_object_id), then rerun." >&2; exit 1; }
  echo "Waiting for Key Vault access to apply ($i/12)..."
  sleep 15
done

end="$(date -u -d "+$SECRET_DAYS days" +%Y-%m-%dT%H:%M:%SZ)"
az ad app credential reset --only-show-errors --id "$app" --display-name nme-stage2 \
  --end-date "$end" --query password -o tsv \
  | tr -d '\n' \
  | az keyvault secret set --only-show-errors --vault-name "$vault" --name "$name" \
      --file /dev/stdin --encoding utf-8 --expires "$end" \
      --content-type "Nerdio REST API client secret" -o none

echo "Wrote $name to Key Vault $vault (expires $end). Stage 2 reads it from there."
