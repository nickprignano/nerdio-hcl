# 0012. Everything runs from Cloud Shell in a browser

- **Status:** Accepted
- **Date:** 2026-10-16

## Context

The maintainer often works from an iPad. Steps that need a local machine (local PowerShell, a
desktop-only installer, a downloaded tool) stall the whole deployment. A tablet browser is also a
good stand-in for the most restricted user the community kit will meet.

## Decision

The baseline is Azure Cloud Shell (Bash) in a browser on a tablet (Edge on an iPad is the test
case). Every step must work there:

- No local installs. `scripts/cloudshell-bootstrap.sh` installs a newer Terraform into `~/bin`
  with checksum verification when Cloud Shell's is too old.
- Nothing typed in: tenant, subscription and the signed-in user come from `az account show` and
  are written once to gitignored tfvars with mode 600. IDs are never printed.
- Plan first; `--apply` runs `terraform apply`, which asks the user for `yes`.
- Uploads go through Cloud Shell's **Manage files**.

## Consequences

- Anything desktop-only needs a Cloud Shell alternative or a spec'd workaround before it ships.
- With `hardening.disable_public_access`, Key Vault and SQL close to Cloud Shell; later applies
  need a route into the VNet (self-hosted runner, VPN or Bastion).
- *Untested:* Packer builds from Cloud Shell.
