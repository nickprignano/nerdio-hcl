# nerdio-hcl

A HashiCorp-stack deployment kit for **Nerdio Manager for Enterprise** on Azure Virtual Desktop.
Terraform builds the landing zone around Nerdio and deploys Nerdio itself; Packer builds the
golden image that Nerdio rolls out to host pools.

| Layer | Tool | What it covers |
|---|---|---|
| Foundation | Terraform | Resource groups, resource provider registration, Log Analytics |
| Network | Terraform | AVD spoke VNet, session host / private endpoint / App Service subnets, NSGs, NAT gateway, privatelink DNS zones, optional hub peering |
| Profiles | Terraform | Premium Azure Files for FSLogix with a private endpoint, Entra Kerberos / Entra DS / AD DS auth and SMB RBAC |
| Nerdio Manager | Terraform | The Marketplace ARM template (App Service, SQL, Key Vault, Automation, App Insights, storage) |
| Identity | Terraform (azuread) | The `nerdio-nmw-app` registration, app roles, Graph permissions, optional admin consent and REST API client |
| Hardening | Terraform | Private endpoints for SQL and Key Vault, App Service VNet integration, optional private console |
| Images | Terraform + Packer | Compute Gallery and a Windows 11 multi-session + M365 image (Trusted Launch, VDOT, updates) |

Host pools, scaling plans, FSLogix profiles and app groups stay in Nerdio, which is built to own
them. The kit gets everything ready for Nerdio's setup wizard and stops there.

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
environments/
  example/           root module wiring everything together; copy per tenant/environment
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
cd environments/sandbox
cp terraform.tfvars.example terraform.tfvars   # fill in tenant, subscription, names, CIDRs
az login --tenant <tenant-id>
terraform init
terraform apply
```

The full order of operations, including the manual Nerdio steps, is in
[docs/deployment-runbook.md](docs/deployment-runbook.md).

## Provider versions

Modules require `azurerm >= 5.0` and `azuread >= 3.0`; the example pins `~> 5.0` and `~> 3.0`.
Validated with Terraform 1.16, azurerm 5.10, azuread 3.10 and Packer 1.16 with the Azure plugin 2.6.
