# Community projects

Other public Nerdio + Terraform work. Useful for comparison; none is endorsed by Nerdio unless noted.

| Project | Notes |
|---|---|
| [Get-Nerdio/NME-Terraform-Provider](https://github.com/Get-Nerdio/NME-Terraform-Provider) | Nerdio's official provider. See [terraform-provider.md](terraform-provider.md). |
| [roanp/NerdioTerraform](https://github.com/roanp/NerdioTerraform) | Rebuilds Nerdio's Azure resources directly instead of using the Marketplace. The app package comes from Nerdio support. Lists required roles. |
| roanp/NerdioTerraformUnofficial | Found, not yet reviewed. |
| oWretch/Nerdio-Terraform | Found, not yet reviewed. |
| [MB-External/NME-Terraform](https://github.com/MB-External/NME-Terraform) | Automates the install end to end: app settings, Key Vault, SQL bootstrap, then app code from Nerdio's package API via Kudu zip deploy. Consent stays manual. See [platform.md](platform.md#install-step-manual). **Tracked prior art for `modules/nerdio-core`**, which is built in parallel: the curator watches its commits, so diff new app settings or package steps against ours. It has no license, so we reuse facts (setting names, API calls) and never its code. Differences: it runs PowerShell on the Terraform machine with a service principal secret and creates SQL users by script; ours deploys from an Automation job inside Azure and uses an Entra group as the SQL admin. |
| [pc-dok/N4K-Github-AVD-Packer](https://github.com/pc-dok/N4K-Github-AVD-Packer) | AVD image builds with Packer and GitHub Actions. No Nerdio integration. |
| [microsoft/terraform-provider-msgraph](https://github.com/microsoft/terraform-provider-msgraph) | Official generic Graph provider (preview, v0.6.0), for Entra/Intune gaps azuread doesn't cover. See [../stack-options.md](../stack-options.md#tool-verdicts). |
| [Get-Nerdio/NMW](https://github.com/Get-Nerdio/NMW) | Nerdio's own repo: `templates/mainTemplate.json`, the update runbook that uses the package API, `intune-policies/` (baselines, ASR, compliance, CA, Defender, firewall), `azure-custom-roles/nme-custom-role.json` (least-privilege role) and Windows scripted actions (screen capture protection, RDP Shortpath, clipboard). See [../security/README.md](../security/README.md). |

When you review one, replace "not yet reviewed" with what it does and how it differs from this kit.

_Last reviewed: 2026-10-16_
