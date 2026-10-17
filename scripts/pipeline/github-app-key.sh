#!/usr/bin/env bash
# Import the setup chatbot's GitHub App private key into Key Vault, then delete the file.
#
#   ./scripts/pipeline/github-app-key.sh ~/clouddrive/nerdio-chat.2026-10-17.private-key.pem
#
# Upload the .pem GitHub gave you with Cloud Shell's Manage files > Upload, then run this. The
# key goes in as non-exportable and limited to signing: the chatbot asks Key Vault to sign a
# short-lived token and never sees the key, and nobody can read it back out. The file is
# shredded afterwards, so the only copy is in Key Vault. To rotate, generate a new key in the
# GitHub App's settings, run this again with it, then delete the old key in GitHub.
#
# Glue only (docs/guardrails.md): Key Vault keys can't be imported with Terraform, which is why
# this is a script. The vault itself is Terraform (modules/assistant, with --pipeline).
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
pem="${1:-}"
if [ -z "$pem" ] || [ ! -f "$pem" ]; then echo "usage: $0 <github-app-private-key.pem>" >&2; exit 64; fi
grep -q 'PRIVATE KEY' "$pem" || { echo "$pem doesn't look like a private key file" >&2; exit 64; }

vault="$(terraform -chdir="$root/environments/example/00-assistant" output -raw github_key_vault_name 2>/dev/null || true)"
case "$vault" in "" | null)
  echo "The chatbot isn't connected to the pipeline yet: ./nerdio assistant --pipeline --github-app <client ID>" >&2
  exit 2 ;;
esac

# Your Crypto Officer role on the vault can take a minute or two to apply after the first deploy.
for i in 1 2 3 4 5 6; do
  if az keyvault key import --vault-name "$vault" --name github-app --pem-file "$pem" \
    --ops sign --protection software --only-show-errors --query key.kid -o none; then
    shred -u "$pem" 2>/dev/null || rm -f "$pem"
    echo "Imported the GitHub App key into $vault (sign only) and deleted $pem."
    exit 0
  fi
  echo "Key Vault access isn't active yet; retrying in 30s ($i/6)"
  sleep 30
done
echo "Couldn't import the key; $pem is unchanged. Try again in a few minutes." >&2
exit 1
