# Windows 11 multi-session image with Packer

A golden image that Nerdio imports from an Azure Compute Gallery
(**Desktop Images > Add from Azure Compute Gallery**).

## Versions

Packer 1.16.1, `packer-plugin-azure` 2.6.4 (`version = "~> 2.6"`, `source = "github.com/hashicorp/azure"`).

## Build shape

- Source image: `MicrosoftWindowsDesktop` / `office-365` / `win11-24h2-avd-m365`.
- Trusted Launch: `security_type = "TrustedLaunch"`, `secure_boot_enabled = true`,
  `vtpm_enabled = true`.
- Gallery image definition must match: `hyper_v_generation = "V2"` and
  `trusted_launch_supported = true`.
- Communicator: WinRM over SSL.
- Publish to the gallery with `Standard_ZRS` replicas.

## Gotchas

- Packer's HCL has no `tostring()` ("Call to unknown function"). For booleans in `env`, use
  `var.flag ? "True" : "False"`.
- Windows Update steps need `valid_exit_codes = [0, 3010]` and an elevated user.
- Virtual Desktop Optimization Tool (VDOT): fetched from the Virtual Desktop Team's GitHub repo
  and run with `Windows_VDOT.ps1 -Optimizations All -AdvancedOptimizations Edge -AcceptEULA`.
  Pin a release or commit rather than `main` for repeatable builds.
- Before sysprep, wait for the RdAgent and Azure guest agent services to be running.

_Last reviewed: 2026-10-16_
