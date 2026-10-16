# Windows 11 multi-session image

Packer builds a Windows 11 Enterprise multi-session + Microsoft 365 image (Gen2, Trusted Launch)
and publishes it to the Compute Gallery from `modules/image-gallery`. Nerdio imports it from there.

```bash
cd packer/avd-win11
cp example.pkrvars.hcl sandbox.pkrvars.hcl     # gitignored; fill in from `az account show`
packer init .
packer build -var-file=sandbox.pkrvars.hcl .
```

Build steps: base settings, Windows Update, WDOT, sysprep.

## Windows Desktop Optimization Tool (WDOT)

[WDOT](https://github.com/The-Virtual-Desktop-Team/Windows-Desktop-Optimization-Tool) is the
Virtual Desktop Team's successor to VDOT. The kit drives it from HCL:

- **Pinned source.** The build host fetches WDOT with `git` at the commit in `wdot_source`
  (git checks the content against the commit hash) and uploads it to the build VM, so the VM
  never downloads code from GitHub. The zip is cached in `packer_cache/`. Point
  `wdot_source.repository` at an internal mirror on restricted networks.
- **Profiles in HCL** (`wdot.pkr.hcl`). WDOT ships every setting as `Skip`; a profile says which
  config files flip to `Apply` and which WDOT categories run.

| `wdot_profile` | What it applies |
|---|---|
| `avd-multisession` (default) | The same selection as Microsoft's sample profile: local policy, default user, Edge, SMB client and autologger settings, plus disk cleanup. No services, scheduled tasks or app removals. |
| `minimal` | SMB client tuning, autologgers and disk cleanup. |
| `none` | Skips WDOT. |

- **Per-setting overrides.** `wdot_overrides` changes single settings on top of the profile,
  keyed by WDOT config file and then by the setting's name (`Name`, `AppxPackage`,
  `ScheduledTask`, `RegItemValueName`, or the last part of `KeyName`). `"*"` means every setting
  in the file. Overriding a file turns on the WDOT category that reads it. A name that matches
  nothing fails the build, so typos don't pass silently.

```hcl
wdot_overrides = {
  Services       = { SysMain = "Apply" }
  ScheduledTasks = { "*" = "Apply" }
  AppxPackages   = { "*" = "Apply", "Microsoft.WindowsCalculator" = "Skip" }
}
```

The setting names are in WDOT's
[`Configurations/Templates`](https://github.com/The-Virtual-Desktop-Team/Windows-Desktop-Optimization-Tool/tree/main/Configurations/Templates)
at the pinned commit. The gallery image version is tagged with `wdot-profile` and `wdot-commit`.

**Updating the pin.** Pick a commit, review what changed in `Configurations/Templates` and
`Functions/`, set `wdot_source.commit`, and test a build. The current pin is `main` just after
the v1.1 tag, because v1.1 passes `-Source` twice to `New-EventLog` and stops on a VM where the
WDOT event log doesn't exist yet (fixed upstream in `0c8d1e6`).

**License.** The repository's `LICENSE` is MIT, while its README and `EULA.txt` describe it as
Microsoft sample code provided as is and "not intended to be used in a production environment".
The kit fetches WDOT at build time and doesn't copy or redistribute it. Test the profile on a
non-production host pool before rolling an image out.
