---
title: "Community projects"
summary: "Other Nerdio + Terraform projects worth knowing about"
topic: nerdio
status: partial
last_reviewed: 2026-10-16
---

# Community projects

Other public Nerdio + Terraform work. Useful for comparison; none is endorsed by Nerdio unless noted.

| Project | Notes |
|---|---|
| [Get-Nerdio/NME-Terraform-Provider](https://github.com/Get-Nerdio/NME-Terraform-Provider) | Nerdio's official provider. See [terraform-provider.md](terraform-provider.md). |
| [roanp/NerdioTerraform](https://github.com/roanp/NerdioTerraform) | Rebuilds Nerdio's Azure resources directly instead of using the Marketplace. The app package comes from Nerdio support. Lists required roles. |
| roanp/NerdioTerraformUnofficial | Found, not yet reviewed. |
| oWretch/Nerdio-Terraform | Found, not yet reviewed. |
| [MB-External/NME-Terraform](https://github.com/MB-External/NME-Terraform) | Automates the install end to end: app settings, Key Vault, SQL bootstrap, then app code from Nerdio's package API via Kudu zip deploy. Consent stays manual. **No license, so reference only: nothing is copied.** The kit's own single-apply install is built in parallel and uses it to cross-check app setting names and the package API steps. Watched by the weekly digest. See [platform.md](platform.md#install-step-manual). |
| [pc-dok/N4K-Github-AVD-Packer](https://github.com/pc-dok/N4K-Github-AVD-Packer) | AVD image builds with Packer and GitHub Actions. No Nerdio integration. |
| [microsoft/terraform-provider-msgraph](https://github.com/microsoft/terraform-provider-msgraph) | Official generic Graph provider (preview, v0.6.0), for Entra/Intune gaps azuread doesn't cover. See [../stack-options.md](../stack-options.md#tool-verdicts). |
| [Get-Nerdio/NMW](https://github.com/Get-Nerdio/NMW) | Nerdio's own repo: `templates/mainTemplate.json`, the update runbook that uses the package API, `intune-policies/` (baselines, ASR, compliance, CA, Defender, firewall), `azure-custom-roles/nme-custom-role.json` (least-privilege role) and Windows scripted actions (screen capture protection, RDP Shortpath, clipboard). See [../security/README.md](../security/README.md). |

When you review one, replace "not yet reviewed" with what it does and how it differs from this kit.
Check each project's license before reusing anything. A repo with no license is reference only: learn
from it and cite it, but don't copy its code.
