---
title: "Workbenches: Cloud Shell and Codespaces"
summary: "Where to run the kit from a browser: Azure Cloud Shell (baseline) or GitHub Codespaces (optional), with their limits"
topic: overview
status: verified
last_reviewed: 2026-11-10
sources:
  - https://docs.github.com/en/codespaces/setting-your-user-preferences/setting-your-timeout-period-for-github-codespaces
  - https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-codespaces/about-billing-for-github-codespaces
  - https://containers.dev/features
  - https://learn.microsoft.com/entra/identity/conditional-access/concept-authentication-flows#device-code-flow
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
  Settings > Codespaces > Default idle timeout (no API), or per codespace with
  `gh codespace create --idle-timeout 240m`, which the kit's docs use instead.
- Included usage for personal accounts each month: GitHub Free 120 core hours and 15 GB-month of
  storage, GitHub Pro 180 core hours and 20 GB-month. Compute counts per core, so the smallest
  (2-core) machine uses 2 core hours an hour: about 60 hours a month on Free.
- A stopped codespace is deleted after the retention period (30 days by default). Local Terraform
  state goes with it.
- Azure sign-in is `az login --use-device-code`. A Conditional Access policy that blocks the
  device-code authentication flow stops this; such tenants need Cloud Shell
  ([Conditional Access authentication flows](https://learn.microsoft.com/entra/identity/conditional-access/concept-authentication-flows#device-code-flow)).
- `.devcontainer/devcontainer.json` uses the official `azure-cli`, `terraform` (pinned, with
  tflint) and `github-cli` features (`ghcr.io/devcontainers/features/*`). `post-create.sh` installs
  `nerdio/nme` from Nerdio's release. The codespace's `GITHUB_TOKEN` is scoped to this repository,
  so the script unsets it and uses the installer's unauthenticated release-API fallback.
- Graph PowerShell isn't installed, so `./nerdio fix roles` still runs from Cloud Shell.

Billing, checked against GitHub's billing docs on 2026-11-10:

- Compute is billed only while a codespace is active; storage is billed for as long as the
  codespace exists, stopped or not. Delete codespaces you're done with (after moving any state).
- With no payment method on file, usage is blocked once the included quota is used up. With one,
  spending past the allowance is billed, capped only by the budgets you set.

## Lessons learned

- **Codespaces is not free, so it stays optional** (owner's call, 2026-11-10). The free monthly
  allowance runs out after roughly 60 hours on the smallest machine, and storage keeps counting
  while a codespace sits stopped. Cloud Shell is the free baseline every step must work from;
  no step may need Codespaces.
- **Every mention carries a cost note.** Any doc, prompt or chat answer that offers Codespaces
  says it's optional and billed past the free allowance, so nobody picks it thinking it's free.
- **Don't write steps from memory.** The first Codespaces steps in this project were given from
  memory and had to be replaced: the HashiCorp apt install they included isn't needed, because
  `scripts/cloudshell-bootstrap.sh` installs Terraform and `nerdio/nme` (in a codespace, the dev
  container's features and `post-create.sh` do). Check steps against the repo and the vendor docs before giving them.
- **The 240-minute idle timeout needs no settings page.** `gh codespace create --idle-timeout 240m`
  from Cloud Shell sets it per codespace, which keeps to the no-portal-click-paths rule.

## Not workbenches

- vscode.dev is an editor only, with no terminal, so it can't run Terraform.
