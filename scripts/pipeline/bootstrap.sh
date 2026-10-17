#!/usr/bin/env bash
# One-time setup for the deploy pipeline, from Azure Cloud Shell (Bash). Decision 0016.
#
#   ./scripts/pipeline/bootstrap.sh                 plan, then apply after you type yes
#   ./scripts/pipeline/bootstrap.sh --plan          plan only
#   ./scripts/pipeline/bootstrap.sh --answers-only  republish your ./nerdio answers after a change
#   ./scripts/pipeline/bootstrap.sh --adopt         move 01-platform and 02-nerdio-config state you
#                                                   applied from Cloud Shell into the pipeline's
#                                                   storage, so the pipeline takes over from there
#
# Terraform (environments/example/00-pipeline) creates the state storage, the plan and apply
# identities with GitHub OIDC trust, and the GitHub environments: <env>-plan, and <env>-apply,
# which needs a reviewer's approval. This script is glue only: it reads IDs from
# `az account show`, the repository from git, and a GitHub token from `gh auth token`, which it
# hands to that one terraform process and never writes down.
#
#   NME_ENV        kit environment (default sandbox)
#   NME_LOCATION   region for the state storage (default eastus2)
#   NME_NAME       short name for the pipeline's resources (default nme-<first 3 of env>)
#   NME_REVIEWERS  comma-separated GitHub logins who may approve applies (default: you)
#
# You need: Owner (or Contributor + Role Based Access Control Administrator) on the
# subscription, Privileged Role Administrator or Global Administrator to grant the identities
# their Microsoft Graph roles, and admin rights on the GitHub repository.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
env_dir="$root/environments/example"
stage="$env_dir/00-pipeline"
mode="${1:-apply}"
case "$mode" in apply | --plan | --answers-only | --adopt) ;; *) echo "usage: $0 [--plan|--answers-only|--adopt]" >&2; exit 64 ;; esac

env_name="${NME_ENV:-sandbox}"
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

say "Account"
az account show --query '{subscription:name, signedInAs:user.name}' -o table
ensure_terraform

if [ "$mode" = --adopt ]; then
  terraform -chdir="$stage" output -raw storage_account_name >/dev/null 2>&1 \
    || { echo "Run $0 first; the pipeline's storage doesn't exist yet." >&2; exit 2; }
  say "Moving Cloud Shell state into the pipeline's storage"
  echo "Don't run this while a plan or apply is running in either stage."
  [ -f "$env_dir/01-platform/terraform.tfstate" ] && migrate "$env_dir/01-platform" platform
  [ -f "$env_dir/02-nerdio-config/terraform.tfstate" ] && migrate "$env_dir/02-nerdio-config" config
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
answers="null"
if [ -f "$root/.nerdio/answers.json" ]; then
  # "me" means you; the pipeline signs in as a service identity, so publish your object ID.
  me="$(az ad signed-in-user show --query id -o tsv)"
  jq --arg me "$me" 'walk(if type == "array" then map(if . == "me" then $me else . end) elif . == "me" then $me else . end)' \
    "$root/.nerdio/answers.json" > "$stage/answers.json"
  answers='"answers.json"'
  echo "Publishing your ./nerdio answers to the $env_name-plan environment"
else
  echo "No ./nerdio answers yet. Run ./nerdio init, then $0 --answers-only."
fi
jq -n \
  --arg tenant "$(az account show --query tenantId -o tsv)" \
  --arg sub "$(az account show --query id -o tsv)" \
  --arg name "$name" --arg location "$location" --arg env "$env_name" \
  --arg owner "$owner" --arg repo "$repo" --arg reviewers "$reviewers" \
  --argjson answers "$answers" \
  '{tenant_id: $tenant, subscription_id: $sub, name: $name, location: $location, environment: $env,
    github: {owner: $owner, repository: $repo, reviewers: ($reviewers | split(",") | map(gsub("^\\s+|\\s+$"; "")))},
    answers_file: $answers}' > "$stage/pipeline.auto.tfvars.json"
echo "Wrote 00-pipeline/pipeline.auto.tfvars.json (gitignored)"

say "00-pipeline: terraform"
GITHUB_TOKEN="$(gh auth token)"
export GITHUB_TOKEN
terraform -chdir="$stage" init -input=false >/dev/null
case "$mode" in
  --plan) terraform -chdir="$stage" plan -input=false; exit 0 ;;
  --answers-only) terraform -chdir="$stage" apply -input=false -target='module.pipeline.github_actions_environment_secret.this["plan/NERDIO_ANSWERS"]' ;;
  *) terraform -chdir="$stage" apply -input=false ;;
esac
unset GITHUB_TOKEN

[ -f "$stage/backend.tf" ] || { say "Moving this stage's state into the new storage"; migrate "$stage" pipeline; }

cat <<MSG

Done. Next:
  - If you applied 01-platform from Cloud Shell already: $0 --adopt
  - Then in GitHub: Actions > deploy > Run workflow. Pick $env_name and a stage; tick "apply" to
    apply after the plan. The apply waits for an approver's OK in the $env_name-apply environment.
MSG
