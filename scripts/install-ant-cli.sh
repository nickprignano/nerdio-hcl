#!/usr/bin/env bash
# Install Anthropic's ant CLI (MIT licensed) into ~/.local/bin, which Cloud Shell keeps.
#
# The kit uses it for one thing: an Anthropic organization admin signs in with it once, so
# `./nerdio assistant --connect-claude` can set up workload identity federation for the setup
# chat. The sign-in token stays in ~/.config/anthropic (mode 600); the kit never prints it.
#
#   ANT_VERSION   release (default below)
#   ANT_BIN_DIR   install directory (default ~/.local/bin)
set -euo pipefail

version="${ANT_VERSION:-1.42.0}"
bin="${ANT_BIN_DIR:-$HOME/.local/bin}"
case "$(uname -m)" in
  x86_64) arch=amd64 ;;
  aarch64 | arm64) arch=arm64 ;;
  *) echo "✗ Unsupported CPU: $(uname -m)" >&2; exit 1 ;;
esac
asset="ant_${version}_linux_${arch}.tar.gz"
base="https://github.com/anthropics/anthropic-cli/releases/download/v${version}"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
curl -fsSL -o "$work/$asset" "$base/$asset"
curl -fsSL -o "$work/checksums.txt" "$base/ant_${version}_checksums.txt"
(cd "$work" && grep " ${asset}\$" checksums.txt | sha256sum -c - >/dev/null) \
  || { echo "✗ Checksum didn't match for $asset; not installing." >&2; exit 1; }

mkdir -p "$bin"
tar -xzf "$work/$asset" -C "$work" ant
install -m 755 "$work/ant" "$bin/ant"
echo "✓ Installed $("$bin/ant" --version) to $bin"
case ":$PATH:" in
  *":$bin:"*) ;;
  *) echo "Add it to your PATH (once): echo 'export PATH=\"$bin:\$PATH\"' >> ~/.bashrc && source ~/.bashrc" ;;
esac
