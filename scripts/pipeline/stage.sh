#!/usr/bin/env bash
# Plan or apply one kit stage inside the deploy workflow (.github/workflows/deploy.yml).
#
#   scripts/pipeline/stage.sh plan    render tfvars from the answers, plan, save the plan
#   scripts/pipeline/stage.sh apply   fetch the saved plan, check its hash, apply exactly it
#
# Glue only (docs/guardrails.md): Terraform does the work. Azure sign-in is GitHub OIDC
# (ARM_USE_OIDC), so there's no secret. Logs and the job summary never show tenant,
# subscription or object IDs: every GUID is replaced before it's printed, because a public
# repository's Actions logs are public.
#
# Inputs (set by the workflow from the GitHub environment's variables):
#   STAGE                    platform | config
#   NERDIO_ENV               sandbox | dev | prod
#   ARM_TENANT_ID ARM_SUBSCRIPTION_ID ARM_CLIENT_ID
#   TFSTATE_RESOURCE_GROUP TFSTATE_STORAGE_ACCOUNT
#   NERDIO_PLAN_PRINCIPAL_ID NERDIO_APPLY_PRINCIPAL_ID
#   NERDIO_ANSWERS           plan only: the ./nerdio answers JSON
#   PLAN_BLOB PLAN_SHA256    apply only: from the plan job
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
action="${1:-}"
case "$action" in plan | apply) ;; *) echo "usage: $0 plan|apply" >&2; exit 64 ;; esac
case "${STAGE:-}" in platform) dir_name=01-platform ;; config) dir_name=02-nerdio-config ;; *) echo "STAGE must be platform or config" >&2; exit 64 ;; esac
[[ "${NERDIO_ENV:-}" =~ ^[a-z][a-z0-9-]{1,20}$ ]] || { echo "NERDIO_ENV is missing or malformed" >&2; exit 64; }
for v in ARM_TENANT_ID ARM_SUBSCRIPTION_ID ARM_CLIENT_ID TFSTATE_RESOURCE_GROUP TFSTATE_STORAGE_ACCOUNT; do
  [ -n "${!v:-}" ] || { echo "$v isn't set: run scripts/pipeline-bootstrap.sh for the $NERDIO_ENV environment first" >&2; exit 2; }
done

env_dir="$root/environments/example"
platform="$env_dir/01-platform"
stage_dir="$env_dir/$dir_name"
work="${RUNNER_TEMP:-$(mktemp -d)}/nerdio-$STAGE"
mkdir -p "$work"

for v in ARM_TENANT_ID ARM_SUBSCRIPTION_ID ARM_CLIENT_ID NERDIO_PLAN_PRINCIPAL_ID NERDIO_APPLY_PRINCIPAL_ID; do
  if [ -n "${!v:-}" ]; then echo "::add-mask::${!v}"; fi
done

# Everything printed goes through this, so no GUID reaches a log or the summary.
redact() { sed -E 's/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/<id>/g'; }
summary() { if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then redact >> "$GITHUB_STEP_SUMMARY"; else redact; fi; }
fail() { echo "::error::$*" | redact; exit 1; }

init_stage() { # $1 dir, $2 state name
  printf 'terraform {\n  backend "azurerm" {}\n}\n' > "$1/backend.tf"
  terraform -chdir="$1" init -input=false -no-color \
    -backend-config="resource_group_name=$TFSTATE_RESOURCE_GROUP" \
    -backend-config="storage_account_name=$TFSTATE_STORAGE_ACCOUNT" \
    -backend-config="container_name=tfstate" \
    -backend-config="key=nerdio/$NERDIO_ENV/$2.tfstate" \
    -backend-config="use_azuread_auth=true" 2>&1 | redact | tail -n 3
}

blob() { # $1 upload|download, $2 file, then any extra az arguments
  az storage blob "$1" --auth-mode login --only-show-errors --account-name "$TFSTATE_STORAGE_ACCOUNT" \
    --container-name plans --name "$PLAN_BLOB" --file "$2" "${@:3}" >/dev/null
}

if [ "$STAGE" = config ]; then
  echo "== nerdio/nme provider"
  "$root/scripts/install-nme-provider.sh" 2>&1 | redact | tail -n 2
fi

if [ "$action" = plan ]; then
  [ -n "${NERDIO_ANSWERS:-}" ] || fail "No answers for $NERDIO_ENV. Publish them with scripts/pipeline-bootstrap.sh."
  echo "== Answers to tfvars"
  mkdir -p "$root/.nerdio"
  printf '%s\n' "$NERDIO_ANSWERS" > "$root/.nerdio/answers.json"
  # Tenant and subscription come from ARM_*; group names are looked up with the plan identity.
  "$root/nerdio" init --non-interactive > "$work/init.log" 2>&1 || { redact < "$work/init.log"; fail "./nerdio init rejected the answers"; }
  grep -E '^(✓|✗|Wrote)' "$work/init.log" | redact || true

  out="$platform/setup.auto.tfvars.json"
  install="$(jq -r '.nerdio_install // "terraform"' "$out")"
  [ "$install" = terraform ] || fail "The pipeline supports nerdio_install = terraform only; the Marketplace path needs a portal download."

  # Both deploy identities read the Nerdio REST secret (decision 0015): plan to refresh stage 2,
  # apply to configure the nme provider during the apply.
  jq --arg p "${NERDIO_PLAN_PRINCIPAL_ID:-}" --arg a "${NERDIO_APPLY_PRINCIPAL_ID:-}" \
    '.nme_secret = ((.nme_secret // {}) | .reader_object_ids = (((.reader_object_ids // []) + ([$p, $a] | map(select(. != "")))) | unique))' \
    "$out" > "$work/p.json" && cat "$work/p.json" > "$out"

  if [ "$STAGE" = config ]; then
    echo "== Inputs from 01-platform"
    init_stage "$platform" platform
    terraform -chdir="$platform" output -json nerdio_config_inputs > "$stage_dir/platform.auto.tfvars.json" 2>/dev/null \
      || fail "01-platform has no outputs yet. Plan and apply the platform stage first."
    kind="$(jq -r '.nme_secret_source // "output"' "$stage_dir/platform.auto.tfvars.json")"
    [ "$kind" = key_vault ] || fail "The pipeline needs nme_secret_store = key_vault (found $kind)."
  fi

  echo "== $dir_name: terraform plan"
  # The plan identity plans, but the apply identity applies: name it as the deployer so the
  # Key Vault roles and app ownership in the plan are the apply identity's.
  export TF_VAR_deployer_object_id="${NERDIO_APPLY_PRINCIPAL_ID:?}"
  init_stage "$stage_dir" "$STAGE"
  set +e
  terraform -chdir="$stage_dir" plan -input=false -no-color -lock-timeout=5m -detailed-exitcode -out="$work/tfplan" > "$work/plan.log" 2>&1
  code=$?
  set -e
  if [ "$code" = 1 ]; then
    grep -v '^\s*$' "$work/plan.log" | tail -n 40 | redact
    fail "terraform plan failed"
  fi
  grep -E '^(Plan:|No changes)' "$work/plan.log" | redact || true

  {
    echo "## $NERDIO_ENV / $dir_name"
    echo
    if [ "$code" = 0 ]; then
      echo "No changes. Nothing to apply."
    else
      echo '```'
      grep -E '^Plan:' "$work/plan.log" || true
      echo '```'
      echo
      echo "| Action | Resource |"
      echo "|---|---|"
      terraform -chdir="$stage_dir" show -json "$work/tfplan" \
        | jq -r '.resource_changes[] | select(.change.actions != ["no-op"] and .change.actions != ["read"]) | "| \(.change.actions | join(" then ")) | `\(.address)` |"'
    fi
  } | summary

  changes=false
  if [ "$code" = 2 ]; then
    changes=true
    tar -C "$work" -cf "$work/plan.tar" tfplan
    tar -C "$stage_dir" -rf "$work/plan.tar" .terraform.lock.hcl
    PLAN_BLOB="$NERDIO_ENV/$GITHUB_RUN_ID-${GITHUB_RUN_ATTEMPT:-1}/$STAGE.tar"
    blob upload "$work/plan.tar" --overwrite
    sha="$(sha256sum "$work/plan.tar" | cut -d' ' -f1)"
    { echo "plan_blob=$PLAN_BLOB"; echo "plan_sha256=$sha"; } >> "${GITHUB_OUTPUT:-/dev/null}"
    echo "Saved plan $sha"
  fi
  echo "changes=$changes" >> "${GITHUB_OUTPUT:-/dev/null}"
  exit 0
fi

# apply: exactly the plan the reviewer approved, or nothing.
if [ -z "${PLAN_BLOB:-}" ] || ! [[ "${PLAN_SHA256:-}" =~ ^[0-9a-f]{64}$ ]]; then fail "No saved plan to apply"; fi
echo "== Saved plan"
blob download "$work/plan.tar"
echo "$PLAN_SHA256  $work/plan.tar" | sha256sum --check --quiet - || fail "The saved plan changed since it was reviewed; not applying"
tar -C "$work" -xf "$work/plan.tar" tfplan
tar -C "$stage_dir" -xf "$work/plan.tar" .terraform.lock.hcl

echo "== $dir_name: terraform apply"
init_stage "$stage_dir" "$STAGE"
# A plan goes stale if the state moved since it was made; Terraform then refuses to apply it.
terraform -chdir="$stage_dir" apply -input=false -no-color -lock-timeout=5m "$work/tfplan" 2>&1 | redact
{ echo "## $NERDIO_ENV / $dir_name"; echo; echo "Applied the reviewed plan."; } | summary
