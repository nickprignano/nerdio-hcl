#!/usr/bin/env bash
# One-time setup for the deploy pipeline, from Azure Cloud Shell (Bash). Decision 0016.
#
#   ./scripts/pipeline/bootstrap.sh                 plan, then apply after you type yes
#   ./scripts/pipeline/bootstrap.sh --assistant "AVD Admins"  bootstrap the pipeline and deploy the
#                                                   setup chatbot connected to it in one command
#   ./scripts/pipeline/bootstrap.sh --plan          plan only
#   ./scripts/pipeline/bootstrap.sh --answers-only  publish your ./nerdio answers again after a change
#                                                   (the setup chatbot can save them too)
#   ./scripts/pipeline/bootstrap.sh --adopt         move 00-assistant, 01-platform and 02-nerdio-config
#                                                   state you applied from Cloud Shell into the
#                                                   pipeline's storage, and the variable values that
#                                                   run used, so the pipeline takes over from there
#
# Terraform (environments/example/00-pipeline) creates the state storage, the plan and apply
# identities with GitHub OIDC trust, the GitHub environments: <env>-plan, and <env>-apply,
# which needs a reviewer's approval. The repository settings the kit relies on (issue labels,
# workflow token, the ruleset on the branch the apply trusts) are github/: run
# ./github/settings.sh apply afterwards. This script is glue only: it reads IDs from
# `az account show`, the repository from git, and a GitHub token from `gh auth token`, which it
# hands to that one terraform process and never writes down.
#
#   NME_ENV        kit environment (default: the one ./nerdio use picked last, else sandbox).
#                  The first run saves this tenant and subscription for it; later runs check them.
#   NME_LOCATION   region for the state storage (default eastus2)
#   NME_NAME       short name for the pipeline's resources (default nme-<first 3 of env>)
#   NME_REVIEWERS  comma-separated GitHub logins who may approve applies (default: you)
#   NME_ADMIN_GROUP Entra security group display name to also deploy 00-assistant with --pipeline
#
# You need: Owner (or Contributor + Role Based Access Control Administrator) on the
# subscription, Privileged Role Administrator or Global Administrator to grant the identities
# their Microsoft Graph roles, and admin rights on the GitHub repository.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
env_dir="$root/environments/example"
stage="$env_dir/00-pipeline"
mode="apply"
admin_group="${NME_ADMIN_GROUP:-}"
while [ $# -gt 0 ]; do
  case "$1" in
    apply | --plan | --answers-only | --adopt) mode="$1"; shift ;;
    --assistant)
      [ $# -ge 2 ] && [ -n "$2" ] || { echo "usage: $0 [--plan|--answers-only|--adopt] [--assistant <admin-group>]" >&2; exit 64; }
      admin_group="$2"; shift 2 ;;
    *) echo "usage: $0 [--plan|--answers-only|--adopt] [--assistant <admin-group>]" >&2; exit 64 ;;
  esac
done

env_name="${NME_ENV:-$(cat "${XDG_CONFIG_HOME:-$HOME/.config}/nerdio-hcl/current" 2>/dev/null || echo sandbox)}"
location="${NME_LOCATION:-eastus2}"
name="${NME_NAME:-nme-${env_name:0:3}}"

say() { printf '\n== %s\n' "$*"; }

ensure_terraform() {
  local have=""
  command -v terraform >/dev/null 2>&1 && have="$(terraform version -json | jq -r .terraform_version)"
  if [ -n "$have" ] && [ "$(printf '%s\n' 1.11.0 "$have" | sort -V | head -n1)" = 1.11.0 ]; then
    return
  fi
  local want="${NME_TF_VERSION:-1.16.6}" tmp
  echo "Terraform ${have:-not found}; installing $want to ~/bin"
  tmp="$(mktemp -d)"
  curl -fsSL -o "$tmp/tf.zip" "https://releases.hashicorp.com/terraform/$want/terraform_${want}_linux_amd64.zip"
  curl -fsSL -o "$tmp/sums" "https://releases.hashicorp.com/terraform/$want/terraform_${want}_SHA256SUMS"
  (cd "$tmp" && grep "linux_amd64.zip" sums | sed "s/terraform_${want}_linux_amd64.zip/tf.zip/" | sha256sum --check -)
  mkdir -p "$HOME/bin"
  unzip -o -q "$tmp/tf.zip" -d "$HOME/bin"
  rm -rf "$tmp"
  export PATH="$HOME/bin:$PATH"
}

# Moves a stage's local state into the pipeline's storage account. backend.tf is gitignored and
# holds names only, so later Cloud Shell runs of that stage keep using it. Role assignments take a
# minute or two to reach the data plane, so it retries.
migrate() { # $1 dir, $2 state name
  local dir="$1" rg sa i
  [ -f "$dir/backend.tf" ] && { echo "$(basename "$dir") already uses a backend; skipping"; return; }
  rg="$(terraform -chdir="$stage" output -raw resource_group_name)"
  sa="$(terraform -chdir="$stage" output -raw storage_account_name)"
  cat > "$dir/backend.tf" <<TF
# Written by scripts/pipeline/bootstrap.sh. Gitignored.
terraform {
  backend "azurerm" {
    resource_group_name  = "$rg"
    storage_account_name = "$sa"
    container_name       = "tfstate"
    key                  = "nerdio/$env_name/$2.tfstate"
    use_azuread_auth     = true
  }
}
TF
  for i in 1 2 3 4 5 6 7 8; do
    if terraform -chdir="$dir" init -input=false -migrate-state -force-copy >/dev/null; then
      echo "$(basename "$dir"): state is now in the pipeline's storage (nerdio/$env_name/$2.tfstate)"
      return
    fi
    echo "Storage access isn't active yet; retrying in 30s ($i/8)"
    sleep 30
  done
  rm -f "$dir/backend.tf"
  echo "Couldn't move $(basename "$dir") state; it's unchanged. Run $0 --adopt again in a few minutes." >&2
  exit 1
}

# Cloud Shell runs (cloudshell-bootstrap.sh, or hand-edited tfvars) name things differently from
# what the answers would render, so planning from answers alone would replace the deployment.
# Publish the values that run used as answers/<env>.<stage>.adopted.tfvars.json; the pipeline
# lays them over the answers. Terraform evaluates them, so HCL tfvars come out as exact JSON.
# Values of sensitive variables are skipped: they belong in Key Vault, not in a file.
adopt_values() { # $1 dir, $2 stage name (platform|config)
  local dir="$1" sa names=() name expr out tmp f
  sa="$(terraform -chdir="$stage" output -raw storage_account_name)"
  for f in "$dir"/*.tfvars "$dir"/*.tfvars.json; do
    [ -f "$f" ] || continue
    case "$(basename "$f")" in
      setup.auto.tfvars.json | platform.auto.tfvars.json | zz-adopted.auto.tfvars.json) continue ;; # the pipeline writes these itself
    esac
    if [[ "$f" == *.json ]]; then
      mapfile -t -O "${#names[@]}" names < <(jq -r 'keys[]' "$f")
    else
      mapfile -t -O "${#names[@]}" names < <(sed -nE 's/^([A-Za-z_][A-Za-z0-9_-]*)[[:space:]]*=.*/\1/p' "$f")
    fi
  done
  # The pipeline sets these itself from its own sign-in and identities.
  mapfile -t names < <(printf '%s\n' "${names[@]}" | grep -vxE 'tenant_id|subscription_id|deployer_object_id|' | sort -u)
  if [ "${#names[@]}" = 0 ]; then echo "$(basename "$dir"): no Cloud Shell values to carry over"; return; fi
  tmp="$(mktemp)"
  expr="jsonencode({$(for name in "${names[@]}"; do printf '%s = var.%s, ' "$name" "$name"; done)})"
  out="$(terraform -chdir="$dir" console <<<"$expr" 2>/dev/null || true)"
  if [ "$out" = "(sensitive value)" ] || [ -z "$out" ]; then
    # One at a time, so a sensitive variable is skipped instead of hiding the rest.
    echo '{}' > "$tmp"
    for name in "${names[@]}"; do
      out="$(terraform -chdir="$dir" console <<<"jsonencode(var.$name)" 2>/dev/null || true)"
      case "$out" in "" | "(sensitive value)") echo "  skipping $name (sensitive or unreadable)"; continue ;; esac
      jq --arg k "$name" --argjson v "$(jq -r . <<<"$out")" '.[$k] = $v' "$tmp" > "$tmp.n" && mv "$tmp.n" "$tmp"
    done
  else
    jq -r . <<<"$out" | jq . > "$tmp"
  fi
  local i
  for i in 1 2 3 4 5 6 7 8; do
    if az storage blob upload --auth-mode login --only-show-errors --account-name "$sa" --container-name answers \
      --name "$env_name.$2.adopted.tfvars.json" --file "$tmp" --overwrite >/dev/null 2>&1; then
      echo "$(basename "$dir"): carried over $(jq 'length' "$tmp") values for the pipeline: $(jq -r 'keys | join(", ")' "$tmp")"
      rm -f "$tmp"
      return
    fi
    echo "Storage access isn't active yet; retrying in 30s ($i/8)"
    sleep 30
  done
  rm -f "$tmp"
  echo "Couldn't publish $(basename "$dir")'s values. Run $0 --adopt again in a few minutes." >&2
  exit 1
}

# The pipeline renders each run from answers/<env>.json in the state storage (versioned, so every
# change is kept). "me" means you; the pipeline signs in as a service identity, so publish your
# object ID instead.
publish_answers() {
  local sa me tmp
  if [ ! -f "$root/.nerdio/answers.json" ]; then
    echo "No ./nerdio answers yet. Run ./nerdio init (or use the setup chatbot), then $0 --answers-only."
    return
  fi
  sa="$(terraform -chdir="$stage" output -raw storage_account_name)"
  me="$(az ad signed-in-user show --query id -o tsv)"
  tmp="$(mktemp)"
  jq --arg me "$me" 'walk(if type == "array" then map(if . == "me" then $me else . end) elif . == "me" then $me else . end)' \
    "$root/.nerdio/answers.json" > "$tmp"
  local i
  for i in 1 2 3 4 5 6 7 8; do
    if az storage blob upload --auth-mode login --only-show-errors --account-name "$sa" --container-name answers \
      --name "$env_name.json" --file "$tmp" --overwrite >/dev/null 2>&1; then
      rm -f "$tmp"
      echo "Published your answers for $env_name"
      return
    fi
    echo "Storage access isn't active yet; retrying in 30s ($i/8)"
    sleep 30
  done
  rm -f "$tmp"
  echo "Couldn't publish the answers. Run $0 --answers-only in a few minutes." >&2
  exit 1
}

say "Environment $env_name"
# Saves this tenant and subscription for the environment the first time (after a yes), and from
# then on switches to it or stops if you're signed in to a different tenant.
"$root/nerdio" use "$env_name" || exit 2

say "Account"
az account show --query '{subscription:name, signedInAs:user.name}' -o table
ensure_terraform

if [ "$mode" = --answers-only ]; then
  terraform -chdir="$stage" output -raw storage_account_name >/dev/null 2>&1 \
    || { echo "Run $0 first; the pipeline's storage doesn't exist yet." >&2; exit 2; }
  publish_answers
  exit 0
fi

if [ "$mode" = --adopt ]; then
  terraform -chdir="$stage" output -raw storage_account_name >/dev/null 2>&1 \
    || { echo "Run $0 first; the pipeline's storage doesn't exist yet." >&2; exit 2; }
  say "Moving Cloud Shell state into the pipeline's storage"
  echo "Don't run this while a plan or apply is running in any stage."
  [ -f "$env_dir/00-assistant/terraform.tfstate" ] && migrate "$env_dir/00-assistant" assistant
  [ -f "$env_dir/01-platform/terraform.tfstate" ] && migrate "$env_dir/01-platform" platform
  [ -f "$env_dir/02-nerdio-config/terraform.tfstate" ] && migrate "$env_dir/02-nerdio-config" config
  say "Carrying over the values your Cloud Shell runs used"
  [ -f "$env_dir/00-assistant/backend.tf" ] && adopt_values "$env_dir/00-assistant" assistant
  [ -f "$env_dir/01-platform/backend.tf" ] && adopt_values "$env_dir/01-platform" platform
  [ -f "$env_dir/02-nerdio-config/backend.tf" ] && adopt_values "$env_dir/02-nerdio-config" config
  echo "They take precedence over your answers, so the first plan keeps the names you already have."
  echo "From now on, plan and apply with the deploy workflow (docs/pipeline.md)."
  exit 0
fi

say "GitHub"
command -v gh >/dev/null 2>&1 || { echo "The GitHub CLI (gh) isn't installed; Cloud Shell has it by default." >&2; exit 2; }
gh auth status >/dev/null 2>&1 || { echo "Sign in to GitHub first: gh auth login (choose the browser code option), then run this again." >&2; exit 2; }
remote="$(git -C "$root" remote get-url origin)"
slug="$(sed -E 's#(\.git)?$##; s#^.*github\.com[:/]##' <<<"$remote")"
owner="${slug%%/*}"
repo="${slug#*/}"
reviewers="${NME_REVIEWERS:-$(gh api user --jq .login)}"
echo "Repository $owner/$repo; applies need approval from: $reviewers"

say "Variables"
umask 077
jq -n \
  --arg tenant "$(az account show --query tenantId -o tsv)" \
  --arg sub "$(az account show --query id -o tsv)" \
  --arg name "$name" --arg location "$location" --arg env "$env_name" \
  --arg owner "$owner" --arg repo "$repo" --arg reviewers "$reviewers" \
  '{tenant_id: $tenant, subscription_id: $sub, name: $name, location: $location, environment: $env,
    github: {owner: $owner, repository: $repo, reviewers: ($reviewers | split(",") | map(gsub("^\\s+|\\s+$"; "")))}}' > "$stage/pipeline.auto.tfvars.json"
echo "Wrote 00-pipeline/pipeline.auto.tfvars.json (gitignored)"

say "00-pipeline: terraform"
GITHUB_TOKEN="$(gh auth token)"
export GITHUB_TOKEN
terraform -chdir="$stage" init -input=false >/dev/null
case "$mode" in
  --plan)
    terraform -chdir="$stage" plan -input=false
    unset GITHUB_TOKEN
    if [ -n "$admin_group" ]; then
      say "00-assistant: terraform plan"
      NME_SKIP_ADOPT=1 "$root/nerdio" assistant --admin-group "$admin_group" --location "$location" --pipeline --plan
    fi
    exit 0 ;;
  *) terraform -chdir="$stage" apply -input=false ;;
esac
unset GITHUB_TOKEN

[ -f "$stage/backend.tf" ] || { say "Moving this stage's state into the new storage"; migrate "$stage" pipeline; }

if [ -n "$admin_group" ]; then
  say "00-assistant: deploying setup chatbot connected to the pipeline"
  NME_SKIP_ADOPT=1 "$root/nerdio" assistant --admin-group "$admin_group" --location "$location" --pipeline
fi

if [ -f "$env_dir/00-assistant/terraform.tfstate" ]; then
  say "Moving 00-assistant state into the pipeline's storage"
  migrate "$env_dir/00-assistant" assistant
  [ -f "$env_dir/00-assistant/backend.tf" ] && adopt_values "$env_dir/00-assistant" assistant
fi

say "Answers"
publish_answers

# The apply environment trusts main, so warn loudly while main has no ruleset (github/ sets it).
if [ "$(gh api "repos/$owner/$repo/rulesets" --jq '[.[] | select(.target == "branch")] | length' 2>/dev/null || echo 0)" = 0 ]; then
  echo "WARNING: $owner/$repo has no branch ruleset, so anyone who can push to main can change what an approved apply runs." >&2
  echo "         Protect it now: ./github/settings.sh apply (github/README.md)." >&2
fi

cat <<MSG

Done. Next:
  - Protect main, which the apply environment trusts: ./github/settings.sh apply
  - If you applied 01-platform from Cloud Shell already: $0 --adopt
  - Then in GitHub: Actions > deploy > Run workflow. Pick $env_name and a stage; tick "apply" to
    apply after the plan. The apply waits for an approver's OK in the $env_name-apply environment.
MSG
