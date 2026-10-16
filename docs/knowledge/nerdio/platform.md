---
title: "Nerdio Manager platform"
summary: "What the Marketplace deployment creates, the install step, setup wizard, roles and hardening"
topic: nerdio
status: partial
last_reviewed: 2026-10-16
---

# Nerdio Manager platform

How Nerdio Manager for Enterprise (NME) lands in Azure, and which parts can and can't be automated.

## What the Marketplace deployment creates

- App Service plan and web app (B3 by default, roughly $219/month list price at the time of writing)
- Azure SQL server and database (S1 by default, roughly $29/month)
- Key Vault, Automation account, Application Insights
- Per Nerdio's reference architecture, also storage accounts and a Log Analytics workspace
- SQL must be a dedicated, new PaaS instance with collation `Latin1_General_CP1_CI_AS`.

## Marketplace deployment

- Deploy into an **empty resource group**.
- Use the **Nerdio Manager for Enterprise** offer (`nerdio.nerdio_wvd_manager`), not the
  "Billing Subscription" SaaS listing (`nerdio.nmw-billing`).
- Nerdio's own template is public at `Get-Nerdio/NMW` `templates/mainTemplate.json` (updated
  2026-10-02). It's a solution template, so there are no Marketplace terms to accept (*inferred*:
  it has no plan, and licensing is a separate offer). Pin it to a commit. Nerdio hasn't declared it
  a supported, versioned deploy path.
- The alternative is to export the template from the portal (**Review + create > Download a
  template for automation**) and pin it in the repo. Offer/plan IDs and a parameter list aren't published.
- In Terraform, deploy the export with `azurerm_resource_group_template_deployment`
  (`deployment_mode = "Incremental"`) and `ignore_changes = [template_content]`, because Nerdio
  updates the running app itself after install. Find the generated resource names afterwards
  with `data "azurerm_resources"`.
- Marketplace parameter names change between Nerdio releases. Always take them from your export.

## Terraform install (the kit's default)

`modules/nerdio-core` does the template's and install script's work in Terraform; see
[decision 0011](../decisions/0011-terraform-native-install.md). Facts it relies on (*unverified*
until the first live run unless noted):

- Nerdio's updater finds the web app from the Key Vault name, so keep the template's names:
  `nmw-app-<suffix>`, `nmw-app-kv-<suffix>`, `-sql-`, `-automation-`, `-scripted-actions-`,
  `-law-`, `-insights-`, `-plan-`.
- App setting `Deployment:UpdaterRunbookRunAs` names the Automation runbook the in-app updater
  starts (`nmwUpdateRunAs`), passing `sourceUri`, `azureEnv` and `authType`.
- Package service: `GET https://nwp-web-app.azurewebsites.net/api/package` lists versions
  (status 2 is GA); `POST /api/package/{version}/link?standalone=false` returns `packageUri`. The
  zip holds `app.zip`, `nwm-scripts.psm1` (`NWM-Before-Publish`, `NWM-After-Publish`) and
  `version.txt`. Undocumented.
- Kudu zip deploy accepts an Entra bearer token, so basic publishing auth can stay off.
- SQL can be Entra-only with an Entra group as admin (web app identity plus the Nerdio app). The
  SQL server's identity needs Graph `User.Read.All`, `GroupMember.Read.All` and
  `Application.Read.All` to resolve group members.

## Install step (manual, marketplace path)

- After the Marketplace deployment, the app's home page shows a one-line script for Cloud Shell
  (needs a storage-backed Cloud Shell). It creates the Entra app and service principal, prepares
  Key Vault, configures the App Service and applies the latest code.
- The advanced **Use existing AD app** path takes an app ID, a secret value and the service
  principal object ID, and uses a downloaded `deploy-az.ps1` script. That script does not run in
  Cloud Shell; run it in local PowerShell. See [entra-app.md](entra-app.md).

- **Automating the install:** [MB-External/NME-Terraform](https://github.com/MB-External/NME-Terraform)
  does the install script's work in Terraform. It writes the app settings, Key Vault secrets and
  SQL bootstrap, then deploys the app code from Nerdio's package API (`/api/package`, then
  `/{ver}/link`) with a Kudu zip deploy. Admin consent is left manual. *Untested:* whether this
  survives Nerdio's self-update.

## Setup wizard (manual)

1. Grant admin consent (**Consent on behalf of my organization**).
2. Pick the directory profile: Entra-joined, AD DS or Entra DS.
3. Pick the AVD network and the resource group for host pools.
4. A **second consent link** appears at the end. It is required; clicking OK alone does not grant it.

What has an API: the network and resource group (`nme_linked_network`, `nme_linked_resource_group`),
and consent can be granted in Terraform (*inferred* to match the wizard's second consent; confirm on
a live run). What doesn't: the directory profile (only `GET /api/v1/ad/config`) and the
registration/first-run state. Those two keep the wizard from being fully automated.

## Roles needed

- Subscription **Owner** on the target subscription.
- **Global Administrator**, or **Privileged Role Administrator + Cloud Application Administrator**.

## Hardening (private endpoints)

- Nerdio ships an **Enable Private Endpoints** runbook with parameters `StorageAccountResource`,
  `MakeAppServicePrivate` and `PeerVnetId`.
- Making the scripted-actions storage account private breaks Azure runbook scripted actions;
  use a Hybrid Runbook Worker instead.
- Nerdio only lists outbound HTTPS 443 to its licensing servers as an egress requirement.
- The kit does the same thing in Terraform as a second apply (App Service VNet integration plus
  private endpoints for SQL, Key Vault and the web app), because the Marketplace resource names
  are only known after the first apply. Use either the runbook or Terraform, not both.
- With a private App Service, admins need a route into the VNet (VPN, Bastion or a jump host).

## Networking note

- *Unverified, check Microsoft's current position before relying on it:* new Azure subnets no
  longer get default outbound internet access, so session host subnets need a NAT gateway or a
  route through a firewall.
- RDP Shortpath and screen capture protection can be turned on with Nerdio's Windows scripted
  actions in Get-Nerdio/NMW (`scripted-actions/windows-scripts`); see [../security/README.md](../security/README.md).

## Sources

- Nerdio help center: Entra app article 26124326326669, private endpoints article 26124315691149
  (https://nmehelp.getnerdio.com).
