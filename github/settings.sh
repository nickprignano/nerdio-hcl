#!/usr/bin/env bash
# Plan or apply this repository's GitHub settings (github/), from Azure Cloud Shell (Bash).
#
#   ./github/settings.sh            plan only: what would change on GitHub
#   ./github/settings.sh apply      plan, then apply after you type yes
#
# Glue only: it reads the owner and repository from git, asks for a token without echoing it,
# hands it to terraform for this run only, and starts every run from an empty state (no backend;
# imports.tf adopts what exists). See github/README.md for the token to create.
set -euo pipefail

dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mode="${1:-plan}"
case "$mode" in plan | apply) ;; *) echo "usage: $0 [plan|apply]" >&2; exit 64 ;; esac

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

ensure_terraform

remote="$(git -C "$dir" remote get-url origin)"
slug="$(sed -E 's#(\.git)?$##; s#^.*github\.com[:/]##' <<<"$remote")"
export TF_VAR_owner="${slug%%/*}" TF_VAR_repository="${slug#*/}"
echo "Repository: $TF_VAR_owner/$TF_VAR_repository"

if [ -z "${GITHUB_TOKEN:-}" ]; then
  read -rsp "Paste your one-day fine-grained token (nothing will show): " GITHUB_TOKEN
  echo
fi
export GITHUB_TOKEN

# A state file left by an earlier run would hide drift, so every run starts empty.
clean() { rm -f "$dir/terraform.tfstate" "$dir/terraform.tfstate.backup" "$dir/settings.tfplan"; }
trap 'clean; unset GITHUB_TOKEN' EXIT
clean

terraform -chdir="$dir" init -input=false >/dev/null
terraform -chdir="$dir" plan -input=false -out=settings.tfplan
[ "$mode" = apply ] || exit 0

read -rp "Apply this plan to GitHub? Type yes: " answer
[ "$answer" = yes ] || { echo "Nothing applied."; exit 0; }
terraform -chdir="$dir" apply -input=false settings.tfplan
echo "Done. Revoke the token now: GitHub > Settings > Developer settings > Fine-grained tokens."
