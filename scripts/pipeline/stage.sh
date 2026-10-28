#!/usr/bin/env bash
# Plan or apply one kit stage inside the deploy workflow (.github/workflows/deploy.yml).
#
#   scripts/pipeline/stage.sh plan    render tfvars from the answers, plan, save the plan
#                                     and a change summary the setup chatbot can read
#                                     (STAGE=preflight runs the read-only readiness check instead,
#                                     and STAGE=verify the same check after Nerdio's wizard)
#   scripts/pipeline/stage.sh apply   fetch the saved plan, check its hash, apply exactly it
#
# Every run leaves a result in the plans container for the setup chatbot, failures included
# (with the last lines of the log, IDs masked), so the chat can explain what happened without
# anyone opening the log. A platform apply also saves the outputs Nerdio's wizard asks for.
#
# Glue only (docs/guardrails.md): Terraform does the work. Azure sign-in is GitHub OIDC
# (ARM_USE_OIDC), so there's no secret. Logs and the job summary never show tenant,
# subscription or object IDs: every GUID is replaced before it's printed, because a public
# repository's Actions logs are public.
#
# Inputs (set by the workflow from the GitHub environment's variables):
#   STAGE                    assistant | platform | config | preflight | verify | fix-quota | fix-vcpu
#   NERDIO_ENV               sandbox | dev | prod
#   ARM_TENANT_ID ARM_SUBSCRIPTION_ID ARM_CLIENT_ID
#   TFSTATE_RESOURCE_GROUP TFSTATE_STORAGE_ACCOUNT
#   NERDIO_PLAN_PRINCIPAL_ID NERDIO_APPLY_PRINCIPAL_ID
#   PLAN_BLOB PLAN_SHA256    apply only: from the plan job
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
action="${1:-}"
case "$action" in plan | apply | unlock) ;; *) echo "usage: $0 plan|apply|unlock" >&2; exit 64 ;; esac
readiness_stage=""
fix_target=""
case "${STAGE:-}" in
  assistant) dir_name=00-assistant ;;
  platform) dir_name=01-platform ;;
  config) dir_name=02-nerdio-config ;;
  preflight) dir_name="" readiness_stage=pre-install ;;
  verify) dir_name="" readiness_stage=post-wizard ;;
  fix-quota) dir_name="" fix_target=quota ;;
  fix-vcpu) dir_name="" fix_target=vcpu ;;
  *) echo "STAGE must be assistant, platform, config, preflight, verify, fix-quota or fix-vcpu" >&2; exit 64 ;;
esac
[ -z "${readiness_stage:-}" ] || [ "$action" = plan ] || { echo "$STAGE only checks; it never applies or unlocks" >&2; exit 64; }
[ -z "${fix_target:-}" ] || [ "$action" != unlock ] || { echo "$STAGE cannot unlock Terraform state" >&2; exit 64; }
if [ "${DESTROY:-false}" = true ] && { [ -n "${readiness_stage:-}" ] || [ -n "${fix_target:-}" ]; }; then
  echo "$STAGE cannot be run with DESTROY=true" >&2; exit 64
fi
[[ "${NERDIO_ENV:-}" =~ ^[a-z][a-z0-9-]{1,20}$ ]] || { echo "NERDIO_ENV is missing or malformed" >&2; exit 64; }
for v in ARM_TENANT_ID ARM_SUBSCRIPTION_ID ARM_CLIENT_ID TFSTATE_RESOURCE_GROUP TFSTATE_STORAGE_ACCOUNT; do
  [ -n "${!v:-}" ] || { echo "$v isn't set: run scripts/pipeline-bootstrap.sh for the $NERDIO_ENV environment first" >&2; exit 2; }
done

env_dir="$root/environments/example"
platform="$env_dir/01-platform"
stage_dir="$env_dir/$dir_name"
work="${RUNNER_TEMP:-$(mktemp -d)}/nerdio-$STAGE"
mkdir -p "$work"
# Where this run's results go in the plans container, and the chatbot reads them.
run_dir="$NERDIO_ENV/${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
result_blob="$run_dir/$STAGE.json"
[ "$action" = apply ] && result_blob="$run_dir/$STAGE-apply.json"
[ "$action" = unlock ] && result_blob="$run_dir/$STAGE-unlock.json"
log=""  # the log the last step wrote; a failure reports its tail

for v in ARM_TENANT_ID ARM_SUBSCRIPTION_ID ARM_CLIENT_ID NERDIO_PLAN_PRINCIPAL_ID NERDIO_APPLY_PRINCIPAL_ID; do
  if [ -n "${!v:-}" ]; then echo "::add-mask::${!v}"; fi
done

# Everything printed goes through this, so no GUID reaches a log or the summary.
redact() { sed -E 's/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/<id>/g'; }
summary() { if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then redact >> "$GITHUB_STEP_SUMMARY"; else redact; fi; }

blob() { # $1 upload|download, $2 container, $3 blob name, $4 file, then any extra az arguments
  az storage blob "$1" --auth-mode login --only-show-errors --account-name "$TFSTATE_STORAGE_ACCOUNT" \
    --container-name "$2" --name "$3" --file "$4" "${@:5}" >/dev/null
}

# A failure also leaves a result for the chatbot: the message and the log's tail, IDs masked.
fail() {
  echo "::error::$*" | redact
  local tail=""
  [ -n "$log" ] && [ -f "$log" ] && tail="$(grep -v '^\s*$' "$log" | tail -n 30 | redact)"
  jq -n --arg stage "$STAGE" --arg action "$action" --arg error "$(echo "$*" | redact)" --arg log "$tail" \
    '{stage: $stage, action: $action, status: "failed", error: $error, log_tail: $log}' > "$work/failed.json"
  blob upload plans "$result_blob" "$work/failed.json" --overwrite 2>/dev/null || true
  exit 1
}

init_stage() { # $1 dir, $2 state name
  printf 'terraform {\n  backend "azurerm" {}\n}\n' > "$1/backend.tf"
  terraform -chdir="$1" init -input=false -no-color \
    -backend-config="resource_group_name=$TFSTATE_RESOURCE_GROUP" \
    -backend-config="storage_account_name=$TFSTATE_STORAGE_ACCOUNT" \
    -backend-config="container_name=tfstate" \
    -backend-config="key=nerdio/$NERDIO_ENV/$2.tfstate" \
    -backend-config="use_azuread_auth=true" 2>&1 | redact | tail -n 3
}

if [ "$STAGE" = config ]; then
  echo "== nerdio/nme provider"
  "$root/scripts/install-nme-provider.sh" 2>&1 | redact | tail -n 2
fi

if [ "$action" = unlock ]; then
  [[ "${LOCK_ID:-}" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]] \
    || fail "LOCK_ID must be a valid UUID to force-unlock state"
  echo "::add-mask::$LOCK_ID"
  echo "== $dir_name: terraform force-unlock"
  init_stage "$stage_dir" "$STAGE"
  log="$work/unlock.log"
  terraform -chdir="$stage_dir" force-unlock -force "$LOCK_ID" > "$log" 2>&1 || { redact < "$log"; fail "terraform force-unlock failed"; }
  redact < "$log"
  { echo "## $NERDIO_ENV / $dir_name"; echo; echo "Force-unlocked Terraform state."; } | summary
  jq -n --arg stage "$STAGE" '{stage: $stage, action: "unlock", status: "unlocked"}' > "$work/unlocked.json"
  blob upload plans "$result_blob" "$work/unlocked.json" --overwrite
  exit 0
fi

if [ "$action" = plan ]; then
  mkdir -p "$root/.nerdio"
  if [ "$STAGE" != assistant ]; then
    echo "== Answers to tfvars"
    # One versioned blob per environment, written by the bootstrap script or the setup chatbot.
    blob download answers "$NERDIO_ENV.json" "$root/.nerdio/answers.json" 2>/dev/null \
      || fail "No answers for $NERDIO_ENV yet. Save them from the setup chatbot, or run scripts/pipeline/bootstrap.sh --answers-only."
    if [ -z "${fix_target:-}" ]; then
      # Tenant and subscription come from ARM_*; group names are looked up with the plan identity.
      log="$work/init.log"
      "$root/nerdio" init --non-interactive > "$log" 2>&1 || { redact < "$log"; fail "./nerdio init rejected the answers"; }
      grep -E '^(✓|✗|Wrote)' "$log" | redact || true
    fi
  else
    blob download answers "$NERDIO_ENV.json" "$root/.nerdio/answers.json" 2>/dev/null || true
  fi

  if [ -n "${fix_target:-}" ]; then
    echo "== Plan quota request: $fix_target (read-only preview)"
    fix_args=("$fix_target")
    if [ "$fix_target" = vcpu ] && [ -n "${FIX_FAMILY:-}" ]; then fix_args+=(--family "$FIX_FAMILY"); fi
    if [ -n "${FIX_LIMIT:-}" ]; then fix_args+=(--limit "$FIX_LIMIT"); fi
    if [ "$fix_target" = quota ] && [ -n "${FIX_CONTACT:-}" ]; then
      email_part="${FIX_CONTACT%%,*}"
      country_part=""
      if [[ "$FIX_CONTACT" == *,* ]]; then country_part="${FIX_CONTACT#*,}"; fi
      if [ -n "$email_part" ]; then fix_args+=(--email "$email_part"); fi
      if [ -n "$country_part" ]; then fix_args+=(--country "$country_part"); fi
    fi
    log="$work/fix.log"
    "$root/nerdio" fix "${fix_args[@]}" --plan > "$log" 2>&1 || { redact < "$log"; fail "./nerdio fix $fix_target --plan failed"; }
    redact < "$log"
    fix_summary="$(redact < "$log" | tr '\n' ' ' | sed -E 's/[[:space:]]+/ /g; s/^ //; s/ $//')"
    {
      echo "## $NERDIO_ENV / $STAGE"
      echo
      echo '```'
      cat "$log"
      echo '```'
    } | summary
    jq -n --arg stage "$STAGE" --arg summary "$fix_summary" --arg addr "quota.$fix_target" \
      '{stage: $stage, status: "planned", summary: $summary, adopted: [], changes: [{action: "request", address: $addr}]}' \
      > "$work/summary.json"
    blob upload plans "$result_blob" "$work/summary.json" --overwrite
    printf '%s\n' "${fix_args[@]}" | jq -R . | jq -s . > "$work/fix-args.json"
    cp "$root/.nerdio/answers.json" "$work/answers.json"
    tar -C "$work" -cf "$work/plan.tar" fix-args.json answers.json
    PLAN_BLOB="$run_dir/$STAGE.tar"
    blob upload plans "$PLAN_BLOB" "$work/plan.tar" --overwrite
    sha="$(sha256sum "$work/plan.tar" | cut -d' ' -f1)"
    { echo "plan_blob=$PLAN_BLOB"; echo "plan_sha256=$sha"; echo "changes=true"; } >> "${GITHUB_OUTPUT:-/dev/null}"
    echo "Saved quota request plan $sha"
    exit 0
  fi

  if [ -n "${readiness_stage:-}" ]; then
    echo "== Readiness check, $readiness_stage (read-only)"
    # Signed in as the plan identity, so the checks of a person's roles come back as "manual":
    # the apply identity holds those roles by design. Everything else is checked for real.
    # After the install, the platform state also carries the kit's own Terraform checks.
    if [ "$STAGE" = verify ]; then init_stage "$platform" platform; fi
    log="$work/preflight.log"
    set +e
    "$root/nerdio" preflight --stage "$readiness_stage" --json --strict > "$work/preflight.json" 2> "$log"
    code=$?
    set -e
    jq -e '.schema == "nerdio-readiness/1"' "$work/preflight.json" >/dev/null 2>&1 || fail "The readiness check didn't finish"
    # The engine masks its own output; the second pass is belt and braces for anything new.
    redact < "$work/preflight.json" | jq --arg stage "$STAGE" \
      '{stage: $stage, status: (.verdict | ascii_downcase | gsub(" "; "-")), verdict, counts, results}' > "$work/result.json"
    blob upload plans "$result_blob" "$work/result.json" --overwrite
    {
      echo "## $NERDIO_ENV / readiness check ($readiness_stage): $(jq -r '.verdict' "$work/result.json")"
      echo
      echo "| Result | Check | Detail |"
      echo "|---|---|---|"
      jq -r '.results[] | select(.status != "skipped") | "| \(.status) | `\(.id)` \(.title) | \(.detail | gsub("\\|"; "/")) |"' "$work/result.json"
    } | summary
    echo "Readiness check: $(jq -r .status "$work/result.json") (exit $code)"
    echo "changes=false" >> "${GITHUB_OUTPUT:-/dev/null}"
    exit 0
  fi

  # Values carried over from an earlier Cloud Shell deployment (bootstrap.sh --adopt). They win
  # over the answers, so the pipeline plans the names that already exist instead of replacements.
  adopted=()
  if blob download answers "$NERDIO_ENV.$STAGE.adopted.tfvars.json" "$work/adopted.json" 2>/dev/null; then
    # The pipeline sets the identity and target itself (ARM_* and TF_VAR_deployer_object_id); an
    # adopted file must never override them, whoever wrote it.
    jq 'del(.deployer_object_id, .tenant_id, .subscription_id)' "$work/adopted.json" \
      > "$stage_dir/zz-adopted.auto.tfvars.json"
    mapfile -t adopted < <(jq -r 'keys[]' "$stage_dir/zz-adopted.auto.tfvars.json")
    echo "Using ${#adopted[@]} values adopted from Cloud Shell: ${adopted[*]}"
  fi

  if [ "$STAGE" = assistant ]; then
    export TF_VAR_tenant_id="$ARM_TENANT_ID"
    export TF_VAR_subscription_id="$ARM_SUBSCRIPTION_ID"
    if [ ! -f "$stage_dir/zz-adopted.auto.tfvars.json" ] || [ -z "$(jq -r '.admin_group // empty' "$stage_dir/zz-adopted.auto.tfvars.json" 2>/dev/null)" ]; then
      if [ -f "$root/.nerdio/answers.json" ]; then
        fallback_group="$(jq -r '((.nerdio_admins // []) + (.admin_groups // [])) | map(select(test("^[0-9a-fA-F-]{36}$") | not)) | .[0] // empty' "$root/.nerdio/answers.json")"
        fallback_loc="$(jq -r '.location // "eastus2"' "$root/.nerdio/answers.json")"
        if [ -n "$fallback_group" ]; then
          jq -n --arg g "$fallback_group" --arg l "$fallback_loc" '{admin_group: $g, location: $l}' > "$stage_dir/zz-adopted.auto.tfvars.json"
        fi
      fi
    fi
    if [ ! -f "$stage_dir/zz-adopted.auto.tfvars.json" ] || [ -z "$(jq -r '.admin_group // empty' "$stage_dir/zz-adopted.auto.tfvars.json" 2>/dev/null)" ]; then
      fail "No 00-assistant configuration in the pipeline's storage yet. Run ./nerdio assistant --admin-group \"<group>\" --pipeline or ./scripts/pipeline/bootstrap.sh --adopt first."
    fi
  else
    out="$platform/setup.auto.tfvars.json"
    install="$(jq -r '.nerdio_install // "terraform"' "$out")"
    case "$install" in
      terraform | marketplace) ;;
      *) fail "nerdio_install must be terraform or marketplace (found $install)." ;;
    esac

    # Both deploy identities read the Nerdio REST secret (decision 0015): plan to refresh stage 2,
    # apply to configure the nme provider during the apply.
    jq --arg p "${NERDIO_PLAN_PRINCIPAL_ID:-}" --arg a "${NERDIO_APPLY_PRINCIPAL_ID:-}" \
      '.nme_secret = ((.nme_secret // {}) | .reader_object_ids = (((.reader_object_ids // []) + ([$p, $a] | map(select(. != "")))) | unique))' \
      "$out" > "$work/p.json" && cat "$work/p.json" > "$out"
  fi

  if [ "$STAGE" = config ]; then
    echo "== Inputs from 01-platform"
    init_stage "$platform" platform
    terraform -chdir="$platform" output -json nerdio_config_inputs > "$stage_dir/platform.auto.tfvars.json" 2>/dev/null \
      || fail "01-platform has no outputs yet. Plan and apply the platform stage first."
    base_url="$(jq -r '.nme_base_url // empty' "$stage_dir/platform.auto.tfvars.json")"
    [ -n "$base_url" ] || fail "01-platform has no nme_base_url yet. For a Marketplace install, deploy Nerdio Manager into the nerdio resource group and re-run the platform stage to discover it."
    client_id="$(jq -r '.nme_client_id // empty' "$stage_dir/platform.auto.tfvars.json")"
    [ -n "$client_id" ] || fail "01-platform has no nme_client_id yet. Set create_entra_app = true or existing_entra_app_client_id and re-run the platform stage."
    kind="$(jq -r '.nme_secret_source // "output"' "$stage_dir/platform.auto.tfvars.json")"
    [ "$kind" = key_vault ] || fail "The pipeline needs nme_secret_store = key_vault (found $kind)."
  fi

  echo "== $dir_name: terraform plan"
  # The plan identity plans, but the apply identity applies: name it as the deployer so the
  # Key Vault roles and app ownership in the plan are the apply identity's.
  export TF_VAR_deployer_object_id="${NERDIO_APPLY_PRINCIPAL_ID:?}"
  init_stage "$stage_dir" "$STAGE"
  plan_flags=(-input=false -no-color -lock-timeout=5m -detailed-exitcode -out="$work/tfplan")
  [ "${DESTROY:-false}" = true ] && plan_flags+=(-destroy)
  set +e
  log="$work/plan.log"
  terraform -chdir="$stage_dir" plan "${plan_flags[@]}" > "$log" 2>&1
  code=$?
  set -e
  if [ "$code" = 1 ]; then
    grep -v '^\s*$' "$log" | tail -n 40 | redact
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

  # The change list for the setup chatbot: private storage, so values aren't redacted here.
  adopted_json="$(printf '%s\n' "${adopted[@]}" | jq -R . | jq -s 'map(select(. != ""))')"
  if [ "$code" = 2 ]; then
    terraform -chdir="$stage_dir" show -json "$work/tfplan" \
      | jq --arg stage "$STAGE" --arg summary "$(grep -E '^Plan:' "$work/plan.log" || true)" --argjson adopted "$adopted_json" \
        '{stage: $stage, status: "planned", summary: $summary, adopted: $adopted, changes: [.resource_changes[] | select(.change.actions != ["no-op"] and .change.actions != ["read"]) | {action: (.change.actions | join(" then ")), address}]}' \
      > "$work/summary.json"
  else
    jq -n --arg stage "$STAGE" --argjson adopted "$adopted_json" '{stage: $stage, status: "planned", summary: "No changes.", adopted: $adopted, changes: []}' > "$work/summary.json"
  fi
  blob upload plans "$result_blob" "$work/summary.json" --overwrite

  changes=false
  if [ "$code" = 2 ]; then
    changes=true
    tar -C "$work" -cf "$work/plan.tar" tfplan
    tar -C "$stage_dir" -rf "$work/plan.tar" .terraform.lock.hcl
    PLAN_BLOB="$run_dir/$STAGE.tar"
    blob upload plans "$PLAN_BLOB" "$work/plan.tar" --overwrite
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
blob download plans "$PLAN_BLOB" "$work/plan.tar"
echo "$PLAN_SHA256  $work/plan.tar" | sha256sum --check --quiet - || fail "The saved plan changed since it was reviewed; not applying"
if [ -n "${fix_target:-}" ]; then
  tar -C "$work" -xf "$work/plan.tar" fix-args.json answers.json
  mkdir -p "$root/.nerdio"
  cp "$work/answers.json" "$root/.nerdio/answers.json"
  mapfile -t fix_args < <(jq -r '.[]' "$work/fix-args.json")
  echo "== Requesting quota: ./nerdio fix ${fix_args[*]} --yes"
  log="$work/apply.log"
  "$root/nerdio" fix "${fix_args[@]}" --yes > "$log" 2>&1 || { redact < "$log"; fail "./nerdio fix $fix_target failed"; }
  redact < "$log"
  detail="$(redact < "$log" | tail -n 5 | tr '\n' ' ' | sed -E 's/[[:space:]]+/ /g; s/^ //; s/ $//')"
  { echo "## $NERDIO_ENV / $STAGE"; echo; echo "Sent the reviewed quota request."; } | summary
  jq -n --arg stage "$STAGE" --arg detail "$detail" \
    '{stage: $stage, action: "apply", status: "applied", outputs: {detail: $detail}}' > "$work/applied.json"
  blob upload plans "$result_blob" "$work/applied.json" --overwrite
  exit 0
fi
tar -C "$work" -xf "$work/plan.tar" tfplan
tar -C "$stage_dir" -xf "$work/plan.tar" .terraform.lock.hcl

echo "== $dir_name: terraform apply"
init_stage "$stage_dir" "$STAGE"
# A plan goes stale if the state moved since it was made; Terraform then refuses to apply it.
log="$work/apply.log"
set +e
terraform -chdir="$stage_dir" apply -input=false -no-color -lock-timeout=5m "$work/tfplan" > "$log" 2>&1
code=$?
set -e
redact < "$log"
[ "$code" = 0 ] || fail "terraform apply failed"
{ echo "## $NERDIO_ENV / $dir_name"; echo; echo "Applied the reviewed plan."; } | summary

# The result for the chatbot. After the platform stage, include the names Nerdio's first-run
# wizard asks for, so the chat can walk the user through it with the exact values. Names only:
# no secrets, and nothing printed to the public log.
outputs='{}'
if [ "$STAGE" = platform ]; then
  outputs="$(terraform -chdir="$stage_dir" output -json 2>/dev/null \
    | jq '{nerdio_url, avd_vnet_name, resource_group_names, fslogix_share_unc} | with_entries(select(.value != null) | .value = .value.value)' \
    || echo '{}')"
elif [ "$STAGE" = assistant ]; then
  outputs="$(terraform -chdir="$stage_dir" output -json 2>/dev/null \
    | jq '{url, github_setup_url} | with_entries(select(.value != null) | .value = .value.value)' \
    || echo '{}')"
fi
jq -n --arg stage "$STAGE" --argjson outputs "$outputs" \
  '{stage: $stage, action: "apply", status: "applied", outputs: $outputs}' > "$work/applied.json"
blob upload plans "$result_blob" "$work/applied.json" --overwrite
