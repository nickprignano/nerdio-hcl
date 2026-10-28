---
title: "Nerdio Manager platform"
summary: "What the Marketplace deployment creates, the install step, setup wizard, roles and hardening"
topic: nerdio
status: verified
last_reviewed: 2026-10-28
---

# Nerdio Manager platform

How Nerdio Manager for Enterprise (NME) lands in Azure, and which parts can and can't be automated.

## What the Marketplace deployment creates

- App Service plan and web app (B3 by default, roughly $219/month list price at the time of writing)
- Azure SQL server and database (S1 by default, roughly $29/month)
- Key Vault, Automation account, Application Insights
- Per Nerdio's reference architecture, also storage accounts and a Log Analytics workspace,
  including the DPS storage account (Nerdio 5.5 and later)
- Each Insights app adds an App Service plan: one more B3 each for Intune Insights and Real-Time
  Insights (a P2v3 for Intune Insights above 20,000 devices) and a P0v3 for Cost Attribution, per
  Nerdio's [preparation steps](https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps).
  `sub.app_service` counts them when `--features insights` is on.
- Resource providers Nerdio lists include **Microsoft.RecoveryServices** (backups), as well as the
  usual compute, network, storage, web, SQL, Key Vault, Automation and monitoring namespaces.
- SQL must be a dedicated, new PaaS instance with collation `Latin1_General_CP1_CI_AS`.

## Marketplace deployment

- Deploy into an **empty resource group** (`sub.empty_rg` checks it).
- The installer looks up its own client IP with ipinfo.io (per Nerdio's readiness script), so an
  egress filter that blocks it breaks a local install. Cloud Shell isn't affected.
- On a public install the SQL server gets the `AllowAllWindowsAzureIps` firewall rule, a known
  point where Azure Policy denies the deployment (per that script's README).
- Use the **Nerdio Manager for Enterprise** offer (`nerdio.nerdio_wvd_manager`), not the
  "Billing Subscription" SaaS listing (`nerdio.nmw-billing`).
- Nerdio's own template is public at `Get-Nerdio/NMW` `templates/mainTemplate.json` (updated
  2026-10-02). It's a solution template, so there are no Marketplace terms to accept (*inferred*:
  it has no plan, and licensing is a separate offer). Pin it to a commit. Nerdio hasn't declared it
  a supported, versioned deploy path.
- The kit's `modules/nerdio-manager` (`nerdio_install = "marketplace"`) supports both:
  - **Normal Azure portal Marketplace deployment (`nerdio_template_file = null`, default):**
    deploy Nerdio Manager in the Azure portal into the empty `nerdio` resource group (or set
    `existing_resource_groups = ["nerdio"]` if you deployed it in the portal first), run Nerdio's
    one-line Cloud Shell install script (`create_entra_app = false`), and then set
    `entra_app.existing_client_id` so Terraform discovers the Marketplace resources (`data "azurerm_resources"`)
    and creates the Stage 2 REST API client app + Key Vault secret hand-off.
  - **Exported template deployment (`nerdio_template_file` set):** export the template from the
    portal (**Review + create > Download a template for automation**), pin it in the repo, and
    deploy with `azurerm_resource_group_template_deployment` (`deployment_mode = "Incremental"`,
    `ignore_changes = [template_content]`). Offer/plan IDs and a parameter list aren't published.
- Marketplace parameter names change between Nerdio releases. Always take them from your export.

## Terraform install (the kit's default)

`modules/nerdio-core` does the template's and install script's work in Terraform; see
[decision 0011](../decisions/0011-terraform-native-install.md). Verified against `Get-Nerdio/NMW`
`templates/mainTemplate.json` and Microsoft App Service / SQL documentation:

- Nerdio's updater finds the web app from the Key Vault name, so keep the template's names:
  `nmw-app-<suffix>`, `nmw-app-kv-<suffix>`, `-sql-`, `-automation-`, `-scripted-actions-`,
  `-law-`, `-insights-`, `-plan-`.
- App setting `Deployment:UpdaterRunbookRunAs` names the Automation runbook the in-app updater
  starts (`nmwUpdateRunAs`), passing `sourceUri`, `azureEnv` and `authType` (confirmed in
  `templates/mainTemplate.json`).
- Package service: `GET https://nwp-web-app.azurewebsites.net/api/package` lists versions
  (status 2 is GA); `POST /api/package/{version}/link?standalone=false` returns `packageUri`. The
  zip holds `app.zip`, `nwm-scripts.psm1` (`NWM-Before-Publish`, `NWM-After-Publish`) and
  `version.txt`. Undocumented.
- Kudu zip deploy (`/api/zipdeploy`) accepts an Entra bearer token, so basic publishing auth can
  stay off.
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
  `/{ver}/link`) with a Kudu zip deploy. Admin consent is left manual. Keeping the template's
  `nmw-app-*` naming convention and `nmwUpdateRunAs` runbook preserves compatibility with Nerdio's
  in-app self-update.

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

- The private DNS zones Nerdio's private endpoints use: blob, file, database, vaultcore,
  azurewebsites and `privatelink.azure-automation.net`.
- The App Service integration subnet must be **delegated to `Microsoft.Web/serverFarms`**
  (`net.subnets` checks an existing VNet's).
- Nerdio ships an **Enable Private Endpoints** runbook with parameters `StorageAccountResource`,
  `MakeAppServicePrivate` and `PeerVnetId`.
- Making the scripted-actions storage account private breaks Azure runbook scripted actions;
  use a Hybrid Runbook Worker instead.
- `modules/nerdio-hardening` adds optional private endpoints for Storage Blob (`blob`) and Azure
  Automation (`DSCAndHybridWorker` subresource on `privatelink.azure-automation.net`), and
  `modules/automation-workers` deploys a Windows Server VM Scale Set with `HybridWorkerExtension`
  (`Microsoft.Azure.Automation.HybridWorker`) registered to an `azurerm_automation_hybrid_runbook_worker_group`.
- For control-plane HA/DR (`modules/nerdio-core`), setting `dr_location` provisions a partner
  Entra-only SQL Server and `azurerm_mssql_failover_group` (`Automatic` read-write failover with a
  60-minute grace period), alongside optional Key Vault purge protection (`purge_protection_enabled`),
  an App Service `staging` slot (`enable_staging_slot`), and CPU-based `azurerm_monitor_autoscale_setting`.
- Nerdio only lists outbound HTTPS 443 to its licensing servers as an egress requirement.
- The kit does the same thing in Terraform as a second apply (App Service VNet integration plus
  private endpoints for SQL, Key Vault and the web app), because the Marketplace resource names
  are only known after the first apply. Use either the runbook or Terraform, not both.
- With a private App Service, admins need a route into the VNet (VPN, Bastion or a jump host).
- When `disable_public_access = true` closes public access on Key Vault, SQL Server, and storage
  accounts, GitHub-hosted `ubuntu-latest` runners cannot reach them. Enabling `enable_vnet_runner = true`
  in `01-platform` and `runner_labels = ["self-hosted", "nerdio-vnet"]` in `00-pipeline` provisions
  `modules/vnet-runner` inside `snet-vnet-runner` (`/27`, delegated to `Microsoft.App/environments`)
  so `.github/workflows/deploy.yml` executes inside the AVD spoke VNet ([decision 0030](../decisions/0030-enterprise-guardrails-locks-and-gitops.md)).

## Networking note

- VNets created after 31 March 2026 get no default outbound internet access, so session host
  subnets need a NAT gateway, a route through a firewall or a load balancer
  ([Microsoft](https://learn.microsoft.com/azure/virtual-network/ip-services/default-outbound-access));
  `net.outbound` checks it.
- RDP Shortpath and screen capture protection can be turned on with Nerdio's Windows scripted
  actions in Get-Nerdio/NMW (`scripted-actions/windows-scripts`); see [../security/README.md](../security/README.md).

## Sources

- Nerdio help center: Entra app article 26124326326669, private endpoints article 26124315691149,
  [VNet integration firewall requirements](https://nmehelp.getnerdio.com/hc/en-us/articles/26124375247757-VNet-integration-firewall-requirements),
  [Required outbound internet access from AVD session host VMs](https://nmehelp.getnerdio.com/hc/en-us/articles/26124299857549-Required-outbound-internet-access-from-AVD-session-host-VMs),
  [HA/DR web app](https://nmehelp.getnerdio.com/hc/en-us/articles/31499449359757-Configure-the-Nerdio-Manager-web-app-for-high-availability-HA-or-disaster-recovery-DR-scenarios),
  [Zone-resilient App Service](https://nmehelp.getnerdio.com/hc/en-us/articles/30352409581709-Configure-the-application-for-zone-resilient-mode) and [SQL](https://nmehelp.getnerdio.com/hc/en-us/articles/37405988082829-Configure-the-SQL-Database-for-zone-resilient-mode),
  [Managed Identity subscription linking](https://nmehelp.getnerdio.com/hc/en-us/articles/32612209667853-Link-Azure-Subscription-Using-Managed-Identities),
  [Migrate Update Automation from Run As to Managed Identity](https://nmehelp.getnerdio.com/hc/en-us/articles/26124376757901-Migrate-the-Nerdio-Update-Automation-Account-from-Run-As-to-Managed-Identity),
  [Azure Local integration](https://nmehelp.getnerdio.com/hc/en-us/articles/34054417281165-How-can-I-integrate-AVD-resources-provisioned-to-Azure-Local-Stack-HCI-with-Nerdio-Manager),
  [Azure Government](https://nmehelp.getnerdio.com/hc/en-us/articles/40495096260493-Nerdio-Manager-in-Azure-Government-What-to-know),
  [Log Analytics performance counter cost tuning](https://nmehelp.getnerdio.com/hc/en-us/articles/49499405163149-Reduce-Log-Analytics-costs-for-AVD-monitoring-by-tuning-performance-counters),
  [OneDrive cloud.microsoft transition](https://nmehelp.getnerdio.com/hc/en-us/articles/49855586627853-OneDrive-transition-to-the-cloud-microsoft-domain-what-do-I-need-to-know-and-do)
  (https://nmehelp.getnerdio.com).
- [Azure Files cross-region copy with Azure Storage Mover (preview)](https://azure.microsoft.com/updates?id=576542) (2026-10-15) and [NME Q3 2026 scaling updates](https://markovich.io/nerdio-manager-enterprise-scaling-updates-q3-2026/) (2026-10-21).
