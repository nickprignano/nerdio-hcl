---
title: "Community projects"
summary: "Other Nerdio + Terraform projects worth knowing about"
topic: nerdio
status: verified
last_reviewed: 2026-10-27
---

# Community projects

Other public Nerdio + Terraform work. Useful for comparison; none is endorsed by Nerdio unless noted.

| Project | Notes |
|---|---|
| [Get-Nerdio/NME-Terraform-Provider](https://github.com/Get-Nerdio/NME-Terraform-Provider) | Nerdio's official provider. See [terraform-provider.md](terraform-provider.md). |
| [roanp/NerdioTerraform](https://github.com/roanp/NerdioTerraform) | Rebuilds Nerdio's Azure resources directly instead of using the Marketplace. The app package comes from Nerdio support. Lists required roles. |
| [roanp/NerdioTerraformUnofficial](https://github.com/roanp/NerdioTerraformUnofficial) | Unlicensed fork/port of the `MB-External/NME-Terraform` layout (`modules/service`, `modules/ccl`, `modules/rti`, `root/`). Deploys NME core, CCL (Cloud PC Connectivity / Log) and RTI (Real-Time Insights) sub-modules, plus offline package zip support. Uses `local-exec` PowerShell (`Az.Accounts`, `Az.Websites`, `SqlServer`) and `null_resource` with `timestamp()` triggers on every apply; reference only (no license). |
| [oWretch/Nerdio-Terraform](https://github.com/oWretch/Nerdio-Terraform) | Unlicensed early predecessor to `roanp/NerdioTerraform`: builds NME's Azure resources (App Service, SQL, Key Vault, Automation, VNet, private DNS, Shared Image Gallery, Entra app) in Terraform, then requires manually requesting the application zip from Nerdio support and granting admin consent in the portal. |
| [MB-External/NME-Terraform](https://github.com/MB-External/NME-Terraform) | Automates the install end to end: app settings, Key Vault, SQL bootstrap, then app code from Nerdio's package API via Kudu zip deploy. Consent stays manual. See [platform.md](platform.md#install-step-manual-marketplace-path). **Tracked prior art for `modules/nerdio-core`**, which is built in parallel: the curator watches its commits, so diff new app settings or package steps against ours. It has no license, so we reuse facts (setting names, API calls) and never its code. Differences: it runs PowerShell on the Terraform machine with a service principal secret and creates SQL users by script; ours deploys from an Automation job inside Azure and uses an Entra group as the SQL admin. |
| [pc-dok/N4K-Github-AVD-Packer](https://github.com/pc-dok/N4K-Github-AVD-Packer) | AVD image builds with Packer and GitHub Actions. No Nerdio integration. |
| [microsoft/terraform-provider-msgraph](https://github.com/microsoft/terraform-provider-msgraph) | Official generic Graph provider (preview, v0.6.0), for Entra/Intune gaps azuread doesn't cover. See [../stack-options.md](../stack-options.md#tool-verdicts). |
| [Get-Nerdio/NMW](https://github.com/Get-Nerdio/NMW) | Nerdio's own repo: `templates/mainTemplate.json`, the update runbook that uses the package API, `intune-policies/` (baselines, ASR, compliance, CA, Defender, firewall), `azure-custom-roles/nme-custom-role.json` (least-privilege role) and Windows scripted actions (screen capture protection, RDP Shortpath, clipboard). See [../security/README.md](../security/README.md). |
| [aaronparker/nerdio](https://github.com/aaronparker/nerdio) | PowerShell Scripted Actions (`/actions`), Shell Apps (`/shell-apps`), Pester image tests (`/tests`) and sample NME deployment templates (`/nme`) by Aaron Parker (stealthpuppy, Nerdio). **GPL-3.0 licensed** (reference only; do not copy code into this Apache-2.0 repo). Focuses on inside-the-guest customization and Nerdio Scripted Actions rather than declarative Terraform control-plane management. |
| [EUCPilots](https://github.com/EUCPilots) ([eucpilots.com](https://eucpilots.com/)) | Aaron Parker's EUC automation hub: [`evergreen-module`](https://github.com/EUCPilots/evergreen-module) (MIT; live vendor version/URL resolution for Windows apps), [`vcredist`](https://github.com/EUCPilots/vcredist) (MIT; Visual C++ Redistributable installer automation), [`evergreen-packages`](https://github.com/EUCPilots/evergreen-packages) (package definitions for Nerdio UAM Shell Apps and Intune Win32 apps) and Evergreen Workbench. Complementary to this kit: we call `Evergreen` and `VcRedist` optionally from `packer/avd-win11` ([../packer/avd-image.md](../packer/avd-image.md#evergreen-and-vcredist-optional)). |
| [WayneBellows/fslogix-healthcheck](https://github.com/WayneBellows/fslogix-healthcheck) | MIT-licensed read-only PowerShell diagnostic script for FSLogix on AVD/RDS session hosts by Wayne Bellows (Nerdio). Audits registry settings against Microsoft best practices, checks Defender AV exclusions, tests SMB/TCP 445 connectivity and Kerberos, detects stale locks and temporary profiles, and writes a self-contained HTML report with optional guided fixes. Good candidate to run as a Nerdio Scripted Action on session hosts. |
| [virtualmanc/nerdioscripts](https://github.com/virtualmanc/nerdioscripts) | Unlicensed collection of Nerdio PowerShell Scripted Actions and API helper scripts by Neil McLoughlin (Nerdio): Windows 11 25H2 in-place upgrade (`25H2Upgrade`), Scripted Actions backup and restore via the Nerdio REST API (`scriptedactionsbackup.ps1`, `scriptedactionrestore`), OS disk expansion (`expand_os_disk.ps1`) and Office deployment (`deployoffice.ps1`). Reference only (no license); our kit declares Scripted Actions directly in Terraform (`nme_scripted_action` in `modules/nerdio-config`). |

When you review one, replace "not yet reviewed" with what it does and how it differs from this kit.
