# Changelog

All notable changes to `nerdio-hcl` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0-alpha.1] - 2026-10-26

### Breaking Changes

- **Multi-region peer `regions` map (`schema/parameters.json` `"version": 2`):** Replaced the v1
  single-region `network` and `fslogix` root variables in `01-platform` and `02-nerdio-config` with
  a peer `regions` map keyed by Azure region name (e.g., `eastus2`, `westeurope`) plus
  `control_plane_location` (and optional `control_plane_dr_location`) for Nerdio Manager's own
  control plane ([decision 0029](docs/knowledge/decisions/0029-v2-multi-region-enterprise-landing-zone.md)).
- **Flexible `workspaces` map in Stage 2 (`02-nerdio-config`):** Replaced the singular `workspace`
  variable with `workspaces = map(object({...}))` so host pools can map to either a shared global
  workspace or per-region / per-persona workspaces.

### Added

- **`./nerdio migrate` subcommand:** Upgrades v1 `.nerdio/answers.json` and `tfvars` to v2 `regions`
  and `workspaces` format, and generates `migrations.auto.tf` with Terraform `moved` blocks in
  `01-platform` and `02-nerdio-config` for zero-downtime state migration.
- **Multi-region CIDR carving and non-overlap validation:** `scripts/nerdio/engine.py` automatically
  carves non-overlapping `/20` VNet ranges across all regions in `locations` (or accepts explicit
  `region:cidr` overrides) and derives subnets per region.
- **Enterprise networking (`modules/network`):** Added `connectivity_mode = "standalone" | "hub_peering" | "vwan"`
  (`azurerm_virtual_hub_connection`), forced-tunneling firewall UDRs (`firewall_next_hop_ip` with
  optional `WindowsVirtualDesktop` service-tag internet bypass), centralized Private DNS zone linking
  across all regional spokes, and `privatelink.azure-automation.net` / `privatelink.wvd.microsoft.com`.
- **Azure NetApp Files & FSLogix Cloud Cache (`modules/anf-storage`):** Added optional per-region
  Azure NetApp Files SMB volumes and multi-share FSLogix Cloud Cache active-active profile locations.
- **Release automation (`.github/workflows/release.yml`, `VERSION`, `CHANGELOG.md`):** Automated
  version verification, changelog extraction, reproducible `nerdio-preflight.pyz` build, and SLSA
  provenance attestation on `v*` tags.
- **Control Plane Hardening & Hybrid Runbook Workers (`modules/nerdio-core`, `modules/nerdio-hardening`, `modules/automation-workers`):**
  Added SQL auto-failover group (`dr_location`), Key Vault purge protection, App Service staging slot
  (`enable_staging_slot`), App Service Plan CPU autoscale (`autoscale`), Blob + Automation
  `DSCAndHybridWorker` private endpoints, and a dedicated Hybrid Runbook Worker VM Scale Set module
  (`modules/automation-workers`).
- **Azure Local, Intune & Entra Conditional Access (`modules/azure-local`, `modules/intune-policies`):**
  Added Azure Local CSV gallery images (`Microsoft.AzureStackHCI/galleryImages`), Arc Connected Machine
  RBAC, and Entra Conditional Access policy-as-code for AVD and Windows 365 Cloud Login.
- **App Attach, Desktop Image Pipelines & AVD Insights (`modules/nerdio-rest-gaps`, `modules/image-gallery`, `modules/avd-insights`):**
  Added MSIX / App Attach package registration, desktop image pipeline schedules, Compute Gallery
  hibernation & accelerated networking flags, and `modules/avd-insights` for Azure Monitor AVD
  Insights Data Collection Rules (DCR) and cost budgets.

## [1.0.0] - 2026-10-26

### Added

- Two-stage Terraform deployment kit (`01-platform` and `02-nerdio-config`) built on `azurerm`,
  `azuread`, `azapi`, `nerdio/nme` and `Mastercard/restapi` ([decision 0001](docs/knowledge/decisions/0001-build-on-nerdio-provider.md),
  [decision 0011](docs/knowledge/decisions/0011-terraform-native-install.md)).
- Key Vault ephemeral secret hand-off and optional OpenBao dynamic secret server
  ([decision 0015](docs/knowledge/decisions/0015-secrets-key-vault-default-openbao-optional.md)).
- Self-hosted setup assistant (`00-assistant`), gated GitHub Actions OIDC deployment pipeline
  (`00-pipeline`), read-only readiness engine (`./nerdio preflight`), Packer Windows 11 multi-session
  golden image (`packer/avd-win11`), and targeted Ansible playbooks (`ansible/`).
