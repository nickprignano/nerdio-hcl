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
# Requires: unzip, sha256sum, and either an authenticated gh or curl + jq (used when gh isn't
# signed in, as in Azure Cloud Shell; the release is public).
set -euo pipefail

tag="${NME_PROVIDER_TAG:-v0.0.1-preview.1}"
dir="${NME_PROVIDER_DIR:-$HOME/.terraform.d/dev-overrides/nme}"
rc="${TF_CLI_CONFIG_FILE:-$HOME/.terraformrc}"
repo="Get-Nerdio/NME-Terraform-Provider"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  echo "Assets in $repo $tag:"
  gh release view "$tag" --repo "$repo" --json assets --jq '.assets[].name' | sed 's/^/  /'

  gh release download "$tag" --repo "$repo" --dir "$work" --pattern '*linux*amd64*'
  gh release download "$tag" --repo "$repo" --dir "$work" --pattern '*SHA256SUMS*' 2>/dev/null \
    || gh release download "$tag" --repo "$repo" --dir "$work" --pattern '*checksums*' 2>/dev/null \
    || true
else
  # Unauthenticated GitHub API: fine for a public release, rate-limited to 60 calls an hour.
  assets="$(curl -fsSL "https://api.github.com/repos/$repo/releases/tags/$tag" \
    | jq -r '.assets[] | "\(.name) \(.browser_download_url)"')"
  echo "Assets in $repo $tag:"
  echo "$assets" | cut -d' ' -f1 | sed 's/^/  /'
  echo "$assets" | while read -r name url; do
    case "$name" in
      *linux*amd64* | *[Ss][Hh][Aa]256[Ss][Uu][Mm][Ss]* | *checksums*)
        curl -fsSL -o "$work/$name" "$url" ;;
    esac
  done
fi

sums="$(find "$work" -maxdepth 1 -type f \( -iname '*sha256sums*' -o -iname '*checksums*' \) | head -n1)"
if [ -n "$sums" ]; then
  (cd "$work" && sha256sum --check "$(basename "$sums")" --ignore-missing)
else
  echo "warning: $tag has no checksum file; skipping verification" >&2
fi

mkdir -p "$dir"
asset="$(find "$work" -maxdepth 1 -type f -name '*linux*amd64*' | head -n1)"
[ -n "$asset" ] || { echo "no linux amd64 asset in $tag" >&2; exit 1; }
case "$asset" in
  *.zip)    unzip -o -q "$asset" -d "$dir" ;;
  *.tar.gz) tar -xzf "$asset" -C "$dir" ;;
  *)        cp "$asset" "$dir/" ;;
esac
bin="$(find "$dir" -maxdepth 1 -type f -name 'terraform-provider-nme*' ! -name '*.zip' ! -name '*.tar.gz' | head -n1)"
[ -n "$bin" ] || { echo "no terraform-provider-nme binary in $(basename "$asset")" >&2; exit 1; }
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
