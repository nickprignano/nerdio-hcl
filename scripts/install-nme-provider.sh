#!/usr/bin/env bash
# Install Nerdio's nerdio/nme Terraform provider from its GitHub release.
#
# The provider isn't on the Terraform Registry yet; Nerdio ships Linux and Windows builds as
# GitHub release assets. This script downloads the pinned release, verifies its checksum and
# installs it into a plugin directory in your home directory (Terraform calls the layout a
# "filesystem mirror"; it's your own download, not a re-hosted copy), so a normal `terraform init`
# finds it next to the Registry providers that stage 2 also needs (azurerm, vault). Nerdio's
# docs use dev_overrides instead, but that breaks `terraform init` for every other provider.
#
# Guardrail: the provider has no license, so the kit downloads it from Nerdio's own release and
# never vendors, mirrors or re-hosts the binary (docs/guardrails.md, decision 0013).
#
#   NME_PROVIDER_TAG   release tag (default below)
#   NME_PROVIDER_MIRROR mirror directory (default ~/.terraform.d/nme-mirror)
#   TF_CLI_CONFIG_FILE CLI config to write (default ~/.terraformrc)
#
# Requires: unzip, sha256sum, and either an authenticated gh or curl + jq (used when gh isn't
# signed in, as in Azure Cloud Shell; the release is public).
set -euo pipefail

tag="${NME_PROVIDER_TAG:-v0.0.1-preview.1}"
mirror="${NME_PROVIDER_MIRROR:-$HOME/.terraform.d/nme-mirror}"
version="${tag#v}"
dir="$mirror/registry.terraform.io/nerdio/nme/$version/linux_amd64"
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
# Unpacked mirror layout: the binary name starts with terraform-provider-nme.
[ "$bin" = "$dir/terraform-provider-nme_$tag" ] || mv -f "$bin" "$dir/terraform-provider-nme_$tag"
chmod +x "$dir/terraform-provider-nme_$tag"

# Replace any provider_installation block (including the old dev_overrides one this script used to
# write) with: nerdio/nme from the local mirror, everything else from the Registry.
block="provider_installation {
  filesystem_mirror {
    path    = \"$mirror\"
    include = [\"registry.terraform.io/nerdio/nme\"]
  }
  direct {
    exclude = [\"registry.terraform.io/nerdio/nme\"]
  }
}"
if [ -f "$rc" ] && grep -q '^provider_installation' "$rc"; then
  if grep -qF "path    = \"$mirror\"" "$rc"; then
    echo "$rc already points nerdio/nme at $mirror"
  elif ! grep -q 'registry.terraform.io/nerdio/nme' "$rc"; then
    echo "$rc already has a provider_installation block of your own. Merge this into it, then run terraform init:" >&2
    printf '%s\n' "$block" >&2
    exit 1
  else
    cp "$rc" "$rc.bak"
    awk '/^provider_installation[[:space:]]*\{/ {skip=1; depth=0}
         skip { n=gsub(/\{/,"{"); m=gsub(/\}/,"}"); depth+=n-m; if (depth<=0 && (n||m)) {skip=0}; next }
         {print}' "$rc.bak" > "$rc"
    printf '%s\n' "$block" >> "$rc"
    echo "Replaced the provider_installation block in $rc (old copy: $rc.bak)"
  fi
else
  printf '%s\n' "$block" >> "$rc"
  echo "Wrote a provider_installation block for nerdio/nme to $rc"
fi

echo "Installed nerdio/nme $tag to $dir"
