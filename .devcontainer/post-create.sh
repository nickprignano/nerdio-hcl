#!/usr/bin/env bash
# Runs once when a codespace is created (docs/codespaces.md). Bootstrap glue only: adds the
# packages the kit's scripts call and installs nerdio/nme from Nerdio's own GitHub release, so
# the first ./scripts/cloudshell-bootstrap.sh run doesn't have to.
set -euo pipefail

missing=()
for cmd in jq unzip python3; do
  command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
done
if [ "${#missing[@]}" -gt 0 ]; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq "${missing[@]}"
fi

# The codespace's GITHUB_TOKEN is scoped to this repository; drop it so the installer takes its
# unauthenticated path for Nerdio's public release.
env -u GITHUB_TOKEN -u GH_TOKEN ./scripts/install-nme-provider.sh \
  || echo "nerdio/nme install failed; ./scripts/cloudshell-bootstrap.sh config retries it" >&2

terraform version | head -n1
az version --query '"azure-cli"' -o tsv | sed 's/^/Azure CLI /'
