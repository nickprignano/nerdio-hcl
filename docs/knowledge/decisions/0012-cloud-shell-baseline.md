---
status: accepted
date: 2026-10-16
decision-makers: [maintainers]
---

# 0012. Everything runs from Cloud Shell in a browser

## Context and Problem Statement

The maintainer often works from an iPad. Steps that need a local machine (local PowerShell, a
desktop-only installer, a downloaded tool) stall the whole deployment. A tablet browser is also a
good stand-in for the most restricted user the community kit will meet. What should the kit
assume the user has?

## Considered Options

- A local workstation with Terraform, PowerShell and the Azure CLI installed
- Azure Cloud Shell (Bash) in a browser, a tablet included

## Decision Outcome

Chosen option: "Azure Cloud Shell in a browser", because it needs nothing installed and works on
any device. Edge on an iPad is the test case, and every step must work there:

- No local installs. `scripts/cloudshell-bootstrap.sh` installs a newer Terraform into `~/bin`
  with checksum verification when Cloud Shell's is too old.
- Nothing typed in: tenant, subscription and the signed-in user come from `az account show` and
  are written once to gitignored tfvars with mode 600. IDs are never printed.
- Plan first; `--apply` runs `terraform apply`, which asks the user for `yes`.
- Uploads go through Cloud Shell's **Manage files**.

### Consequences

- Good, because the kit works from any browser with no setup.
- Bad, because anything desktop-only needs a Cloud Shell alternative or a spec'd workaround before
  it ships.
- Bad, because with `hardening.disable_public_access`, Key Vault and SQL close to Cloud Shell;
  later applies need a route into the VNet (self-hosted runner, VPN or Bastion).

## More Information

*Untested:* Packer builds from Cloud Shell.
