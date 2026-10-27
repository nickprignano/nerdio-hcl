---
status: accepted
date: 2026-10-26
decision-makers: [maintainers]
---

# 0029. v2 multi-region peer `regions` map, `./nerdio migrate` and enterprise landing zone architecture

## Context and Problem Statement

Version 1 of `nerdio-hcl` modeled a single `location`, a single spoke VNet (`module.network`), a
single FSLogix storage account (`module.fslogix`), and a single AVD `workspace`. Enterprise landing
zones often span multiple peer Azure regions (with no single "primary" workload region), connect
spokes via Azure Virtual WAN or forced-tunneling hub firewalls, use Azure NetApp Files or FSLogix
Cloud Cache across regions, require Hybrid Runbook Workers when locking down Nerdio's storage and Key
Vault, and manage Intune, Windows 365, Conditional Access, and Azure Local/Arc alongside AVD. How
should the kit structure multi-region and enterprise landing zone capabilities without turning
sandbox setup into an unmanageable form?

## Considered Options

- Keep top-level single-region variables (`location`, `network`, `fslogix`) as a "primary" region
  and add an optional `additional_regions` map alongside them
- Break v1 compatibility in v2 (`schema/parameters.json` `"version": 2`): move all workload spoke
  networks, resource groups and profile storage into a peer `regions = map(object({...}))` keyed by
  Azure region name alongside `control_plane_location` for Nerdio Manager itself, and provide a
  `./nerdio migrate` command that upgrades v1 configs and emits Terraform `moved` blocks
- Split regional spokes into separate per-region Terraform state roots

## Decision Outcome

Chosen option: "Break v1 compatibility in v2 with a peer `regions` map, `control_plane_location`,
`workspaces` map, and `./nerdio migrate`", because large multi-region estates treat workload regions
as peers while keeping Nerdio Manager's control plane in a designated `control_plane_location`, and
automated `moved` block generation gives existing v1 deployments a zero-downtime upgrade path.

- **Peer `regions` map in `01-platform` and `02-nerdio-config`:** Every workload region in
  `var.regions` defines its own spoke resource groups (`network`, `hostpools`, `storage`), VNet and
  connectivity mode (`standalone`, `hub_peering`, or `vwan` + optional firewall UDRs), optional
  per-region `subscription_id`, and profile storage (`azure_files`, `azure_netapp_files`, or `none`).
- **Control plane location (`control_plane_location`):** Nerdio Manager's own resources (`nerdio` and
  `monitoring` resource groups, App Service, Entra-only SQL, Key Vault, Automation, Private DNS
  zones) live in `var.control_plane_location` (with optional `control_plane_dr_location`).
- **Centralized Private DNS zones:** Created once at the platform level (or passed via
  `existing_private_dns_zone_ids` from a central hub subscription) and linked to every regional VNet
  in `var.regions`.
- **Flexible `workspaces` map in `02-nerdio-config`:** Host pools reference `region_key` and
  `workspace_key`, supporting either a single global workspace or per-region/per-persona workspaces,
  plus FSLogix Cloud Cache multi-share active-active locations across regions.
- **Zero-downtime v1 → v2 migration (`./nerdio migrate`):** Upgrades `.nerdio/answers.json` and
  `setup.auto.tfvars.json` from schema v1 to v2 and generates `migrations.auto.tf` in `01-platform`
  and `02-nerdio-config` with Terraform `moved` blocks (`module.network` → `module.network["<loc>"]`,
  `nme_linked_network.session_hosts` → `nme_linked_network.session_hosts["<loc>"]`, etc.).
- **Single platform state for opt-in enterprise modules:** `intune-policies`, `windows-365`,
  `conditional-access`, `azure-local`, `avd-hybrid-arc`, `hybrid-worker`, `cmk-encryption`,
  `nerdio-rbac`, and `avd-observability` wire into `01-platform` as opt-in (`default = null`) modules.

### Consequences

- Good, because single-region sandbox users still answer the same questions in `./nerdio init`
  (which automatically populates `regions = { "<location>": { ... } }`), while multi-region
  enterprises get a clean, symmetric `regions` map with automatic non-overlapping `/20` CIDR carving.
- Good, because `./nerdio migrate` prevents destructive recreation of live VNets and Nerdio linked
  networks/workspaces when upgrading from v1.
- Neutral, because `schema/parameters.json` advances to `"version": 2` and tracked releases follow
  Semantic Versioning in `VERSION` and `CHANGELOG.md`.
