# nerdio-hcl

A HashiCorp-stack deployment kit for **Nerdio Manager for Enterprise** on Azure Virtual Desktop,
built around Nerdio's official Terraform provider, [`nerdio/nme`](https://github.com/Get-Nerdio/NME-Terraform-Provider).

- **Stage 1, platform** (`azurerm`, `azuread`): the Azure landing zone, Nerdio Manager itself, and the
  Entra apps Nerdio and its REST API need.
- **Stage 2, Nerdio config** (`nerdio/nme`): workspaces, linked resource groups and networks,
  FSLogix and auto-scale profiles and dynamic host pools, all managed through Nerdio's REST API.
- **Images** (Packer): a Windows 11 multi-session golden image published to a Compute Gallery.

| Layer | Tool | What it covers |
|---|---|---|
| Foundation | Terraform | Resource groups, resource provider registration, Log Analytics |
| Network | Terraform | AVD spoke VNet, session host / private endpoint / App Service subnets, NSGs, NAT gateway, privatelink DNS zones, optional hub peering |
| Profiles | Terraform | Premium Azure Files for FSLogix with a private endpoint, Entra Kerberos / Entra DS / AD DS auth and SMB RBAC |
| Nerdio Manager | Terraform (+ azapi) | App Service, Entra-only SQL, Key Vault, Automation, App Insights and storage with Nerdio's settings, plus an Automation job that deploys the app code. The Marketplace template stays as an alternative. |
| Identity | Terraform (azuread) | The `nerdio-nmw-app` registration, app roles, Graph permissions, optional admin consent and REST API client |
| Hardening | Terraform | Private endpoints for SQL and Key Vault, App Service VNet integration, optional private console |
| Images | Terraform + Packer | Compute Gallery and a Windows 11 multi-session + M365 image (Trusted Launch, updates, WDOT optimizations) |
| Nerdio config | Terraform (`nerdio/nme`) | Linked subscription, resource groups and network, workspace, FSLogix profile, auto-scale profile, dynamic host pools |

Nerdio's setup wizard is the only manual step; it sits between the two stages, because Nerdio has
no API for the directory profile or first run yet.
`nerdio/nme` is early (0.x), so check its
[coverage notes](https://github.com/Get-Nerdio/NME-Terraform-Provider/blob/main/AVD-COVERAGE.md)
before you rely on it for something; app groups and session host actions aren't covered yet, for example.

## Layout

```
modules/
  foundation/        resource groups, providers, Log Analytics
  network/           AVD spoke network and private DNS
  fslogix-storage/   profile storage
  nerdio-core/       Nerdio Manager built in Terraform, plus the app code deploy job (default)
  nerdio-manager/    Marketplace template deployment + resource discovery (alternative)
  nerdio-identity/   Nerdio's Entra app, app roles, consent and REST API client
  nerdio-hardening/  private endpoints and VNet integration for Nerdio's core resources
  image-gallery/     Compute Gallery and image definitions for Packer
  nerdio-config/     Nerdio objects through the nerdio/nme provider
environments/
  example/
    01-platform/       stage 1 root: Azure + Entra + Nerdio install
    02-nerdio-config/  stage 2 root: Nerdio configuration via nerdio/nme
packer/
  avd-win11/         Windows 11 multi-session image build
templates/
  nerdio-manager/    exported Marketplace template (marketplace install only)
docs/
  guardrails.md
  deployment-runbook.md
  cloud-shell.md
  architecture.md
  knowledge/         the living knowledge base and decision records
```

## Quick start

Requirements: Terraform >= 1.9, Packer >= 1.11, Azure CLI, subscription **Owner**, and Global
Administrator (or Privileged Role Administrator + Cloud Application Administrator) in Entra ID.

```bash
cp -r environments/example environments/sandbox
cd environments/sandbox/01-platform
cp terraform.tfvars.example terraform.tfvars   # tenant, subscription, names, CIDRs (gitignored)
az login --tenant <tenant-id>
terraform init && terraform apply

# Terraform installs Nerdio Manager too; finish its setup wizard, enable the REST API, then:
../../../scripts/install-nme-provider.sh      # nerdio/nme ships as a GitHub release for now
terraform output -json nerdio_config_inputs > ../02-nerdio-config/platform.auto.tfvars.json
export NME_CLIENT_SECRET="$(terraform output -raw nme_client_secret)"
cd ../02-nerdio-config
cp terraform.tfvars.example terraform.tfvars   # workspace and host pools
terraform get && terraform apply               # get, not init, with dev_overrides
```

From Azure Cloud Shell (any browser, tablets included) `scripts/cloudshell-bootstrap.sh` reads
the tenant and subscription from your sign-in instead; see [docs/cloud-shell.md](docs/cloud-shell.md).

The full order of operations, including the manual Nerdio steps, is in
[docs/deployment-runbook.md](docs/deployment-runbook.md).

## Provider versions

Modules require `azurerm >= 5.0` and `azuread >= 3.0`. `nerdio/nme` is installed from Nerdio's
GitHub release (`v0.0.1-preview.1`, pinned in `scripts/install-nme-provider.sh`) until it is
published to the Registry.
Validated with Terraform 1.16, azurerm 5.10, azuread 3.10 and Packer 1.16 with the Azure plugin 2.6.

## Guardrails

Every change follows [docs/guardrails.md](docs/guardrails.md). In short:

1. **Automate, never at the expense of security.** Identities and certificates over secrets,
   least privilege, and a documented workaround where automation isn't safe.
2. **HCL first.** Terraform or Packer does it if it can; scripts are thin bootstrap glue.
3. **Works from a browser.** Every step runs in Azure Cloud Shell, on an iPad included.
4. **Nothing identifies a real environment.** No real IDs, domains, IPs, emails, secrets or
   employer names in the repo. CI runs gitleaks and blocks tracked tfvars and state files.
5. **Secrets never go through chat** or into the repo.
6. **PRs only, plan first, and nothing applies without the tenant owner's yes.**
7. **Unlicensed code is reference only.** Nerdio's repos and MB-External have no license: we use
   facts from them, never their code, and download `nerdio/nme` from Nerdio's release.

## Keeping it shareable

The repo holds no tenant-specific values. Real IDs, names and CIDRs go in `terraform.tfvars`,
`*.auto.tfvars.json` and `*.pkrvars.hcl`, which are gitignored. Secrets are passed through
environment variables, never files. Examples use `contoso` names and all-zero GUIDs.
