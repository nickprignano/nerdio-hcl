---
title: "Workbenches: Cloud Shell and Codespaces"
summary: "Where to run the kit from a browser: Azure Cloud Shell (baseline) or GitHub Codespaces (optional), with their limits"
topic: overview
status: partial
last_reviewed: 2026-10-17
sources:
  - https://docs.github.com/en/codespaces/setting-your-user-preferences/setting-your-timeout-period-for-github-codespaces
  - https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-codespaces/about-billing-for-github-codespaces
  - https://containers.dev/features
---

# Workbenches: Cloud Shell and Codespaces

The kit runs from a browser, an iPad included. Two workbenches fit that rule
([decision 0012](decisions/0012-cloud-shell-baseline.md)). How-to: [docs/codespaces.md](../codespaces.md)
and [docs/cloud-shell.md](../cloud-shell.md).

## Azure Cloud Shell (baseline)

- Already signed in to Azure; Graph PowerShell built in (`./nerdio fix roles` uses it).
- Idles out after about 20 minutes without a keypress, and a sleeping iPad tab ends the session.
  Long applies die mid-run; reruns resume from state. This is why applies moved to the
  [deploy pipeline](decisions/0016-gated-deploy-pipeline.md).

## GitHub Codespaces (optional)

Checked against GitHub's docs on 2026-10-17:

- Idle timeout: 30 minutes by default, 5 to 240 minutes, set per user under GitHub
  Settings > Codespaces > Default idle timeout.
- Included usage for personal accounts each month: GitHub Free 120 core hours and 15 GB-month of
  storage, GitHub Pro 180 core hours and 20 GB-month. Compute counts per core, so the smallest
  (2-core) machine uses 2 core hours an hour: about 60 hours a month on Free.
- A stopped codespace is deleted after the retention period (30 days by default). Local Terraform
  state goes with it.
- Azure sign-in is `az login --use-device-code`. A Conditional Access policy that blocks the
  device-code flow stops this; such tenants need Cloud Shell. *Unverified* on a real tenant.
- `.devcontainer/devcontainer.json` uses the official `azure-cli`, `terraform` (pinned, with
  tflint) and `github-cli` features. `post-create.sh` installs `nerdio/nme` from Nerdio's release.
  The codespace's `GITHUB_TOKEN` is scoped to this repository, so the script unsets it and uses
  the installer's unauthenticated path. *Unverified:* first live codespace build.
- Graph PowerShell isn't installed, so `./nerdio fix roles` still runs from Cloud Shell.

## Not workbenches

- vscode.dev is an editor only, with no terminal, so it can't run Terraform.
