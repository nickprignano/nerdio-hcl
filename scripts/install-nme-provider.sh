#!/usr/bin/env bash
# Install Nerdio's nerdio/nme Terraform provider from its GitHub release.
#
# The provider isn't on the Terraform Registry yet; Nerdio ships Linux and Windows builds as
# GitHub release assets and documents a dev_overrides install. This script downloads the pinned
# release, verifies its checksum and writes the override into the Terraform CLI config.
#
#   NME_PROVIDER_TAG   release tag (default below)
#   NME_PROVIDER_DIR   install directory (default ~/.terraform.d/dev-overrides/nme)
#   TF_CLI_CONFIG_FILE CLI config to write (default ~/.terraformrc)
#
# Requires: gh (authenticated), unzip, sha256sum.
set -euo pipefail

tag="${NME_PROVIDER_TAG:-v0.0.1-preview.1}"
dir="${NME_PROVIDER_DIR:-$HOME/.terraform.d/dev-overrides/nme}"
rc="${TF_CLI_CONFIG_FILE:-$HOME/.terraformrc}"
repo="Get-Nerdio/NME-Terraform-Provider"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

gh release download "$tag" --repo "$repo" --dir "$work" --pattern '*linux_amd64.zip' --pattern 'SHA256SUMS'
(cd "$work" && sha256sum --check SHA256SUMS --ignore-missing)

mkdir -p "$dir"
unzip -o -q "$work"/*linux_amd64.zip -d "$dir"
bin="$(find "$dir" -maxdepth 1 -type f -name 'terraform-provider-nme*' ! -name '*.zip' | head -n1)"
[ "$bin" = "$dir/terraform-provider-nme" ] || mv -f "$bin" "$dir/terraform-provider-nme"
chmod +x "$dir/terraform-provider-nme"

if [ -f "$rc" ] && grep -q 'registry.terraform.io/nerdio/nme' "$rc"; then
  echo "$rc already overrides nerdio/nme; leaving it as is."
else
  cat >> "$rc" <<RC
provider_installation {
  dev_overrides {
    "registry.terraform.io/nerdio/nme" = "$dir"
  }
  direct {}
}
RC
  echo "Wrote dev_overrides for nerdio/nme to $rc"
fi

echo "Installed nerdio/nme $tag to $dir"
