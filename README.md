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
| Nerdio Manager | Terraform | The Marketplace ARM template (App Service, SQL, Key Vault, Automation, App Insights, storage) |
| Identity | Terraform (azuread) | The `nerdio-nmw-app` registration, app roles, Graph permissions, optional admin consent and REST API client |
| Hardening | Terraform | Private endpoints for SQL and Key Vault, App Service VNet integration, optional private console |
| Images | Terraform + Packer | Compute Gallery and a Windows 11 multi-session + M365 image (Trusted Launch, VDOT, updates) |
| Nerdio config | Terraform (`nerdio/nme`) | Linked subscription, resource groups and network, workspace, FSLogix profile, auto-scale profile, dynamic host pools |

Nerdio's install script and setup wizard are the only manual steps; they sit between the two stages.
`nerdio/nme` is early (0.x), so check its
[coverage notes](https://github.com/Get-Nerdio/NME-Terraform-Provider/blob/main/AVD-COVERAGE.md)
before you rely on it for something; app groups and session host actions aren't covered yet, for example.

## Guided setup

One set of questions, three ways to answer them. All three read
[`schema/parameters.json`](schema/README.md), so they ask the same things and write the same tfvars:

- **Chat:** a setup chatbot you host in your own Azure tenant. Deploy it from Azure Cloud Shell with
  `./nerdio assistant --admin-group "<your admin group>"`, open the URL it prints, and it walks you
  through discover, a readiness check and configure, explaining each choice with a source
  ([docs/assistant.md](docs/assistant.md)).
- **Command line:** `./nerdio init` asks the questions in the terminal (Azure Cloud Shell works),
  then `./nerdio preflight` checks your roles, providers, region and quota.
- **Button:** the **configure** workflow in the Actions tab takes the main answers as a form and
  dry-runs them.

Details: [docs/setup.md](docs/setup.md).

## Layout

```
modules/
  foundation/        resource groups, providers, Log Analytics
  network/           AVD spoke network and private DNS
  fslogix-storage/   profile storage
  nerdio-manager/    Marketplace template deployment + resource discovery
  nerdio-identity/   Entra app for Nerdio's "Use existing AD app" install path
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
  nerdio-manager/    drop the exported Marketplace template here
docs/
  deployment-runbook.md
  architecture.md
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

# install Nerdio and finish its wizard, enable the REST API, then:
../../../scripts/install-nme-provider.sh      # nerdio/nme ships as a GitHub release for now
terraform output -json nerdio_config_inputs > ../02-nerdio-config/platform.auto.tfvars.json
export NME_CLIENT_SECRET="$(terraform output -raw nme_client_secret)"
cd ../02-nerdio-config
cp terraform.tfvars.example terraform.tfvars   # workspace and host pools
terraform get && terraform apply               # get, not init, with dev_overrides
```

The full order of operations, including the manual Nerdio steps, is in
[docs/deployment-runbook.md](docs/deployment-runbook.md).

## Provider versions

Modules require `azurerm >= 5.0` and `azuread >= 3.0`. `nerdio/nme` is installed from Nerdio's
GitHub release (`v0.0.1-preview.1`, pinned in `scripts/install-nme-provider.sh`) until it is
published to the Registry.
Validated with Terraform 1.16, azurerm 5.10, azuread 3.10 and Packer 1.16 with the Azure plugin 2.6.

## Keeping it shareable

The repo holds no tenant-specific values. Real IDs, names and CIDRs go in `terraform.tfvars`,
`*.auto.tfvars.json` and `*.pkrvars.hcl`, which are gitignored. Secrets are passed through
environment variables, never files. Examples use `contoso` names and all-zero GUIDs.
