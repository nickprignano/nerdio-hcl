---
title: "Windows 11 multi-session image with Packer"
summary: "Building a Windows 11 multi-session image for Nerdio with Packer"
topic: packer
status: verified
last_reviewed: 2026-10-28
---

# Windows 11 multi-session image with Packer

A golden image that Nerdio imports from an Azure Compute Gallery
(**Desktop Images > Add from Azure Compute Gallery**).

## Versions

Packer 1.16.1 ([1.16.2](https://github.com/hashicorp/packer/releases/tag/v1.16.2) released 2026-10-22), `packer-plugin-azure` 2.6.4 (`version = "~> 2.6"`, `source = "github.com/hashicorp/azure"`).

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
- The file provisioner needs `generated = true` for a file that a `shell-local` provisioner
  creates during the build; otherwise Packer looks for it at the start and fails.
- A file provisioner with `content = jsonencode(...)` is a clean way to hand HCL-rendered settings
  to a script on the guest.
- Before sysprep, wait for the RdAgent and Azure guest agent services to be running.

## Windows Desktop Optimization Tool (WDOT)

The kit optimizes the image with [WDOT](https://github.com/The-Virtual-Desktop-Team/Windows-Desktop-Optimization-Tool),
which its README calls "the next evolution of the Virtual Desktop Optimization Tool" (VDOT). Setup
and the kit's profile are in `packer/avd-win11/README.md`. Checked against the WDOT repo on 2026-10-16.

- **Changes from VDOT:** the entry script is `Windows_Optimization.ps1` (VDOT's was
  `Windows_VDOT.ps1`). It needs `-ConfigProfile`, the name of a folder under `Configurations/`,
  and `-Optimizations` no longer defaults to All.
- **Profiles:** every setting in `Configurations/Templates` is `Skip`. The sample profile
  `Configurations/2009` sets every setting to `Apply` in Autologgers, DefaultUserSettings,
  EdgeSettings, LanManWorkstation and PolicyRegSettings, and leaves AppxPackages, ScheduledTasks
  and Services all `Skip`. The kit's default `avd-multisession` profile reproduces those states.
- **Silent failures:** WDOT records runs in the `WDOT` event log and in `HKLM:\SOFTWARE\WDOT`
  (`Version`, `LastRunTime`). When its config is wrong it returns without an exit code, so a
  wrapper has to check the event log, not the exit code.
- **Versions:** tags are `v1.0` (2025-10-30) and `v1.1` (2026-05-01, commit `f20d6b7`).
  Verified in `Windows_Optimization.ps1`: `v1.1` splats `@EVT` (`@{ LogName = 'WDOT'; Source = 'WDOT' }`)
  into `New-EventLog -Source $EventSources @EVT` (passing `-Source` twice) and `Limit-EventLog @EVT`
  (which does not accept `-Source`), breaking the first run on a VM that has no `WDOT` event log yet.
  It is fixed on `main` in commit [`0c8d1e6`](https://github.com/The-Virtual-Desktop-Team/Windows-Desktop-Optimization-Tool/commit/0c8d1e67d88c8cf6abec37e3ed17e08b2984fe14)
  (which replaces `@EVT` with `-LogName 'WDOT'`), which no tag includes yet, so the kit pins `main`
  at commit `ff2574c` (2026-05-20). Move the pin to a tag once one includes the fix; the weekly
  digest watches the repo.
- **License:** mixed. `LICENSE` is MIT, but the README and `EULA.txt` call it Microsoft Sample
  Code "not intended to be used in a production environment". The kit fetches it at build time
  and doesn't vendor it.
- **Pinning:** where GitHub archive downloads are blocked, fetch the commit with git and pin by
  commit hash rather than a zip checksum (see
  [../terraform/restricted-networks.md](../terraform/restricted-networks.md#pinning-github-sources-by-commit)).
- **Optional Ansible image hardening:** set `run_ansible_playbook = true` in `packer/avd-win11` to
  run `ansible/playbooks/avd-image.yml` over WinRM before sysprep (Teams media optimization, RDP
  Shortpath UDP 3390, Defender FSLogix exclusions, enterprise root certificates; see
  [decision 0028](../decisions/0028-targeted-ansible-for-images-and-hybrid.md)).
- **GPU / Graphics preset:** set `gpu_preset = true` in `packer/avd-win11` (and `image_definition = "win11-avd-gpu"`)
  to enable hardware-accelerated GPU frame encoding (`bEnumerateHWBeforeSW`, `AVC444ModePreferred`,
  `AVCHardwareEncodePreferred`), pairing with `gpu_preset = true` on `02-nerdio-config` host pools.

## Evergreen and VcRedist (optional)

Set `install_vcredist = true` or populate `evergreen_apps` in `packer/avd-win11` to resolve and
install the latest Microsoft Visual C++ Redistributables and common Windows applications at build
time via EUC Pilots' [`VcRedist`](https://github.com/EUCPilots/vcredist) and
[`Evergreen`](https://github.com/EUCPilots/evergreen-module) PowerShell modules (both MIT-licensed,
watched in [../sources.toml](../sources.toml)).

- **HCL-driven:** Packer serializes `install_vcredist` and `evergreen_apps` to
  `C:\Windows\Temp\evergreen-settings.json` with `jsonencode(...)` and runs `scripts/04-evergreen.ps1`.
- **Opt-in:** Both default to disabled (`false` / `[]`) so restricted-network builds that block
  the PowerShell Gallery or vendor CDNs continue to work without changes.
- **Upstream notes:** see Nerdio's [Recommended Optimizations for Desktop Images](https://nmehelp.getnerdio.com/hc/en-us/articles/26124315600525-Recommended-Optimizations-for-Desktop-Images),
  Wayne Bellows' Golden Image notes ([2026-10-19 Intune CNAME auto-discovery](https://modern-euc.com/2026/10/19/golden-image-2026-10-19-intune-drops-cname-auto-discovery-for-mdm-only-enrolment/),
  [2026-10-26 Intune device page](https://modern-euc.com/2026/10/26/golden-image-2026-10-26-intunes-new-device-page-will-become-the-default/)),
  and [Windows 11 AVD golden image update verification](https://markovich.io/windows-11-avd-update-issues-golden-image-patch/).
