#!/usr/bin/env bash
# Run the kit from Azure Cloud Shell (Bash) without typing tenant or subscription IDs.
#
#   ./scripts/cloudshell-bootstrap.sh platform           plan 01-platform
#   ./scripts/cloudshell-bootstrap.sh platform --apply   apply 01-platform (Terraform asks for yes)
#   ./scripts/cloudshell-bootstrap.sh config             plan 02-nerdio-config
#   ./scripts/cloudshell-bootstrap.sh config --apply     apply 02-nerdio-config (asks for yes)
#
# The first run reads the signed-in account with az and writes 01-platform/sandbox.auto.tfvars;
# later runs reuse it, so names stay stable. Every generated file is gitignored, and IDs are
# never printed. Run `az account set --subscription <name>` first if the default is wrong.
#
# Guardrails (docs/guardrails.md): this is bootstrap glue only (HCL first; Terraform does the
# work). It plans by default, and --apply leaves the yes to you. Nothing here prints or commits
# tenant values.
#
#   NME_INSTALL        terraform (default: Terraform builds Nerdio Manager) or marketplace (deploy an
#                      exported Marketplace template, then run Nerdio's install script)
#   NME_LOCATION       Azure region (default eastus2)
#   NME_GRANT_CONSENT  grant admin consent from Terraform (default true; needs Global Admin or
#                      Privileged Role Administrator)
#   NME_TF_VERSION     Terraform to install when Cloud Shell's is older than 1.11 (default 1.16.6)
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_dir="$root/environments/example"
platform="$env_dir/01-platform"
config="$env_dir/02-nerdio-config"
template_dir="$root/templates/nerdio-manager"

stage="${1:-platform}"
mode="${2:-plan}"
case "$stage" in platform | config) ;; *) echo "usage: $0 platform|config [--apply]" >&2; exit 64 ;; esac
case "$mode" in plan | --apply) ;; *) echo "usage: $0 platform|config [--apply]" >&2; exit 64 ;; esac

say() { printf '\n== %s\n' "$*"; }

ensure_terraform() {
  local have=""
  command -v terraform >/dev/null 2>&1 && have="$(terraform version -json | jq -r .terraform_version)"
  if [ -n "$have" ] && [ "$(printf '%s\n' 1.11.0 "$have" | sort -V | head -n1)" = 1.11.0 ]; then
    echo "Terraform $have (kit needs >= 1.11)"
    return
  fi
  local want="${NME_TF_VERSION:-1.16.6}"
  echo "Terraform ${have:-not found}; installing $want to ~/bin"
  local tmp; tmp="$(mktemp -d)"
  curl -fsSL -o "$tmp/tf.zip" "https://releases.hashicorp.com/terraform/$want/terraform_${want}_linux_amd64.zip"
  curl -fsSL -o "$tmp/sums" "https://releases.hashicorp.com/terraform/$want/terraform_${want}_SHA256SUMS"
  (cd "$tmp" && grep "linux_amd64.zip" sums | sed "s/terraform_${want}_linux_amd64.zip/tf.zip/" | sha256sum --check -)
  mkdir -p "$HOME/bin"
  unzip -o -q "$tmp/tf.zip" -d "$HOME/bin"
  rm -rf "$tmp"
  export PATH="$HOME/bin:$PATH"
  terraform version | head -n1
}

ensure_template() {
  if [ -f "$template_dir/template.json" ]; then
    echo "Using exported template templates/nerdio-manager/template.json"
    [ -f "$platform/nerdio.auto.tfvars.json" ] || jq -n '{nerdio_template_file: "../../../templates/nerdio-manager/template.json"}' > "$platform/nerdio.auto.tfvars.json"
    return
  fi
  # If the user uploaded an exported "Download a template for automation" zip to Cloud Shell, unpack it.
  local zip="" z
  while IFS= read -r z; do
    if unzip -Z1 "$z" 2>/dev/null | grep -qx 'template.json'; then zip="$z"; break; fi
  done < <(find "$HOME" "$HOME/clouddrive" -maxdepth 1 -type f -iname '*.zip' 2>/dev/null)
  if [ -z "$zip" ]; then
    echo "Portal Marketplace mode (no exported template zip): Terraform builds the landing zone and discovers Nerdio Manager in rg-<prefix>-nerdio once you deploy it from the Azure portal Marketplace."
    return
  fi
  echo "Unpacking $(basename "$zip")"
  local tmp; tmp="$(mktemp -d)"
  unzip -o -q "$zip" -d "$tmp"
  cp "$tmp/template.json" "$template_dir/template.json"
  if [ -f "$tmp/parameters.json" ]; then
    jq --arg loc "$location" \
      '{nerdio_template_file: "../../../templates/nerdio-manager/template.json",
        nerdio_template_parameters: (.parameters | map_values(.value)
          | if has("location") then .location = $loc else . end)}' \
      "$tmp/parameters.json" > "$platform/nerdio.auto.tfvars.json"
    echo "Wrote 01-platform/nerdio.auto.tfvars.json from parameters.json"
  else
    jq -n '{nerdio_template_file: "../../../templates/nerdio-manager/template.json"}' > "$platform/nerdio.auto.tfvars.json"
  fi
  rm -rf "$tmp"
}

write_platform_tfvars() {
  local out="$platform/sandbox.auto.tfvars"
  if [ -f "$out" ]; then
    echo "Reusing 01-platform/sandbox.auto.tfvars"
    return
  fi
  local tenant sub me suffix prefix compact consent
  tenant="$(az account show --query tenantId -o tsv)"
  sub="$(az account show --query id -o tsv)"
  me="$(az ad signed-in-user show --query id -o tsv)"
  suffix="$(head -c 64 /dev/urandom | tr -dc 'a-z0-9' | head -c 4)"
  prefix="nme-sbx-$suffix"
  compact="nmesbx$suffix"
  consent="${NME_GRANT_CONSENT:-true}"

  local create_app="true"
  [ "$install" = marketplace ] && create_app="${NME_CREATE_ENTRA_APP:-false}"

  umask 077
  cat > "$out" <<TFVARS
# Generated by scripts/cloudshell-bootstrap.sh from az account show. Gitignored; don't commit.
tenant_id       = "$tenant"
subscription_id = "$sub"
prefix          = "$prefix"
location        = "$location"

tags = {
  workload    = "avd"
  managed-by  = "terraform"
  environment = "sandbox"
}

resource_groups = {
  nerdio     = "rg-$prefix-nerdio"
  network    = "rg-$prefix-network"
  hostpools  = "rg-$prefix-hostpools"
  storage    = "rg-$prefix-storage"
  monitoring = "rg-$prefix-monitoring"
}

network = {
  address_space = ["10.50.0.0/20"]
  subnets = {
    session_hosts     = "10.50.0.0/22"
    private_endpoints = "10.50.4.0/27"
    app_integration   = "10.50.4.32/27"
  }
}

fslogix = {
  storage_account_name = "st${compact}fslogix"
  identity_source      = "AADKERB"
}

image_gallery = {
  name                      = "gal_${compact}"
  build_resource_group_name = "rg-$prefix-images-build"
}

create_entra_app = $create_app

entra_app = {
  wvd_admin_object_ids = ["$me"]
  grant_admin_consent  = $consent
}

nerdio_install   = "$install"
enable_hardening = false
TFVARS
  echo "Wrote 01-platform/sandbox.auto.tfvars (prefix $prefix, region $location, $install install, admin consent $consent)"
}

# Terraform's output is also kept (owner-only, gitignored) so it can be shared with IDs masked:
# ./nerdio redact --tail 40. Plans and errors name subscription, tenant and object IDs.
run_tf() {
  local logs="$root/.nerdio/logs" log
  mkdir -p "$logs" && chmod 700 "$logs"
  log="$logs/$(basename "$PWD")-${mode#--}-$(date +%Y%m%d-%H%M%S).log"
  (umask 077; : > "$log")
  ln -sf "$(basename "$log")" "$logs/last.log"
  if [ "$mode" = --apply ]; then
    terraform apply 2>&1 | tee "$log"
  else
    terraform plan -input=false 2>&1 | tee "$log"
  fi
  echo
  echo "To share this output, run ./nerdio redact --tail 40 and paste that (IDs, IPs and names masked)."
}

say "Account"
az account show --query '{subscription:name, signedInAs:user.name}' -o table
location="${NME_LOCATION:-eastus2}"
install="${NME_INSTALL:-terraform}"
case "$install" in terraform | marketplace) ;; *) echo "NME_INSTALL must be terraform or marketplace" >&2; exit 64 ;; esac
[ -d "$HOME/clouddrive" ] || echo "warning: no ~/clouddrive; this looks like an ephemeral Cloud Shell, so state is lost when it closes." >&2

say "Terraform"
ensure_terraform

if [ "$stage" = platform ]; then
  if [ "$install" = marketplace ]; then
    say "Nerdio Manager template"
    ensure_template
  fi
  say "Variables"
  write_platform_tfvars
  say "01-platform: terraform ${mode#--}"
  cd "$platform"
  terraform init -input=false -upgrade >/dev/null
  run_tf
  if [ "$mode" = plan ]; then
    echo
    echo "Review the plan, then: ./scripts/cloudshell-bootstrap.sh platform --apply"
  fi
  exit 0
fi

say "nerdio/nme provider"
if [ -x "$HOME/.terraform.d/nme-mirror/registry.terraform.io/nerdio/nme/0.0.1-preview.1/linux_amd64/terraform-provider-nme_v0.0.1-preview.1" ] \
  && grep -q 'nme-mirror' "$HOME/.terraformrc" 2>/dev/null; then
  echo "Already installed"
else
  "$root/scripts/install-nme-provider.sh"
fi

say "Inputs from 01-platform"
terraform -chdir="$platform" output -json nerdio_config_inputs > "$config/platform.auto.tfvars.json"
echo "Wrote 02-nerdio-config/platform.auto.tfvars.json"
[ -f "$config/terraform.tfvars" ] || { cp "$config/terraform.tfvars.example" "$config/terraform.tfvars"; echo "Wrote 02-nerdio-config/terraform.tfvars from the example"; }

# The Nerdio REST client secret (decision 0015). With key_vault (the default) Terraform reads it
# from Key Vault with your az sign-in, so nothing is exported here.
source_kind="$(jq -r '.nme_secret_source // "output"' "$config/platform.auto.tfvars.json")"
say "REST API secret: $source_kind"
case "$source_kind" in
  key_vault)
    echo "Terraform reads it from Key Vault during plan and apply; it never reaches this shell." ;;
  openbao)
    terraform -chdir="$platform" output -raw openbao_ca_cert > "$config/openbao-ca.pem"
    # A short-lived Entra token for OpenBao's login app, not the Nerdio secret.
    scope="$(jq -r '.openbao.scope' "$config/platform.auto.tfvars.json")"
    TF_VAR_openbao_jwt="$(az account get-access-token --scope "$scope" --query accessToken -o tsv)"
    export TF_VAR_openbao_jwt
    echo "OpenBao mints a short-lived secret for this run." ;;
  *)
    NME_CLIENT_SECRET="$(terraform -chdir="$platform" output -raw nme_client_secret)"
    export NME_CLIENT_SECRET
    echo "Using NME_CLIENT_SECRET (the old hand-off); set nme_secret_store = \"key_vault\" to stop exporting it." ;;
esac

say "02-nerdio-config: terraform ${mode#--}"
cd "$config"
terraform init -input=false -upgrade >/dev/null
run_tf
if [ "$mode" = plan ]; then
  echo
  echo "Review the plan, then: ./scripts/cloudshell-bootstrap.sh config --apply"
fi
