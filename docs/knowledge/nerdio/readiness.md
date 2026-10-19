---
title: "Nerdio readiness checks"
summary: "The read-only readiness engine behind ./nerdio preflight: stages, statuses, rights, and how it sits beside Nerdio's own readiness script"
topic: nerdio
status: partial
last_reviewed: 2026-10-19
sources:
  - https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps
  - https://nmehelp.getnerdio.com/hc/en-us/articles/26124379482381-How-to-Check-the-Health-of-Nerdio-Manager
---

# Nerdio readiness checks

One read-only engine answers "will this Nerdio Manager deployment, and each feature I plan to
turn on, work in this tenant?" before the install, after it and after Nerdio's wizard
([decision 0026](../decisions/0026-read-only-readiness-engine.md)). It lives in
`scripts/nerdio/readiness/` and runs behind `./nerdio preflight`, the deploy pipeline's
`preflight` stage and, through the pipeline, the setup chat. For a manual Marketplace install it
also runs on its own, without the kit ([standalone](#standalone)).

## Running it

```bash
./nerdio preflight                     # pre-install, the kit's answers, console report
./nerdio preflight --format md         # a short report to paste into a ticket or the chat
./nerdio preflight --json              # readiness.json (schema/readiness.schema.json)
./nerdio preflight --save out/         # readiness.json and readiness.md, mode 600
./nerdio preflight --list              # the catalogue below
./nerdio preflight --only sub.region,avd.vcpu
```

`--stage pre-install|post-install|post-wizard` picks when you are. `--features` adds feature
domains (`app-mgmt`, `app-attach`, `insights`, `rbac`, `self-service`, `hardening`,
`scripted-actions`, `automation`, `ai`, or `all`); without it only core checks run. Inputs only
the readiness check has (`resource_group`, `nerdio_url`, `intune_devices`, `app_attach_storage`,
`rti_reuse_existing` and the existing-network ones) go in with `--set name=value`.
`post-wizard` also re-runs the `post-install` checks, because an installed Nerdio Manager has to
stay healthy through its wizard. After the install, point the checks at Nerdio Manager with
`--resource-group` or `--nerdio-url` (the kit knows its own group). The app (`nme.*`), AVD
(`avd.*`), hardening, roles and self-service checks find Nerdio's resources by type in that
group, so they work on a Marketplace install too. In the kit's pipeline, stage **verify** runs
`--stage post-wizard` as the plan identity.

## Standalone

`nerdio-preflight.pyz` is a single-file Python zipapp attached to this repository's releases.
It needs only what Cloud Shell has (Python 3.9 or later, `az`), installs nothing and has no
`curl | bash` step: download a pinned version, check its SHA-256 against the
[README](../../../README.md#readiness-check-without-the-kit), and run it.

```bash
python3 nerdio-preflight.pyz                         # asks a few questions, then checks
python3 nerdio-preflight.pyz --location eastus2 --users 200 --identity-model entra --no-input
python3 nerdio-preflight.pyz --answers answers.json --format md
```

Inputs come from flags (`--location`, `--identity-model entra|entra_ds|ad_ds`, `--users`,
`--vm-size`, `--set name=value`), then `--answers` (the kit's answer keys), then a short
interview using the kit's own questions. `--no-input` never asks; checks whose inputs are missing
report `skipped`. It resolves only the parameters tagged `readiness` in
`schema/parameters.json`, bundles a copy of that file, and records its version in
`readiness.json` as `parameters_version`. It assumes the Marketplace install, and it never
invents a network to check: the address range and hub are checked only when you give them.
Choices the kit can't build yet (AD DS, for example) are still checked, because Nerdio supports
them.

### Releasing the standalone check

1. Bump `__version__` in `scripts/nerdio/readiness/__init__.py` in a PR and merge it.
2. Tag the merge commit `preflight-v<version>` and push the tag. The `preflight-release`
   workflow runs the tests on Python 3.9, builds the zipapp, signs a build provenance
   attestation and publishes the release with its SHA-256.
3. Rebuild locally (`python3 scripts/build-preflight-pyz.py`) from the tag: the build is
   reproducible, so the checksum must match the release's. Then add the version and checksum to
   the README's table in a PR.

## Statuses and the verdict

| Status | Means |
|---|---|
| `pass` | Checked and fine |
| `warn` | Couldn't be checked fully, or likely to cause trouble; look at it |
| `fail` | Will break the deployment; the `fix` line says what to do |
| `manual` | Only a person can confirm it (licenses, on-premises reachability) |
| `no-access` | The signed-in identity can't read it; the result names the right it needs |
| `skipped` | Out of scope, or an input is missing |

The verdict is `NO-GO` when anything fails, `INCOMPLETE` when nothing ran or every identity or
subscription check came back `no-access`, `GO WITH WARNINGS` when anything is `warn`, `manual` or
`no-access`, and `GO` otherwise, so a run that couldn't see everything is never plain green.
Exit codes: 0 for `GO` and `GO WITH WARNINGS`, 1 for `NO-GO`, 2 for bad usage, 3 for
`INCOMPLETE`. `--strict` also exits 1 on a `warn`; the pipeline uses it.

Output is masked by default: IDs, emails, public IPs, tenant domains, the account's names, and
resource, group and network names (`--names` shows those). `--no-redact` writes everything, only
to a mode-600 file.

## Rights

Every default check only reads: a guard in the engine refuses any `az` command that isn't a
`show` or `list`, and any `az rest` call that isn't a GET, and CI runs every check against
recorded answers to prove it. **Reader** on the subscription (and on the hub network and private
DNS zones where they live elsewhere) plus your own directory read rights cover every default
check. The installer roles Nerdio needs (Global Administrator, or Privileged Role Administrator
plus Cloud Application Administrator; subscription Owner) are checked *for*, not needed *to run*
the check. See [docs/access.md](../../access.md).

After the install, **Directory Readers** (or a role that reads applications and service
principals) covers the Entra app and role checks, **Key Vault Reader** on Nerdio's vault covers
certificate expiry (metadata only, never a value), and **Security Reader** covers the Defender
check. The only call that isn't Azure's own API is one unauthenticated HTTPS GET of Nerdio
Manager's health page.

## Operator

The `op.*` checks: tools, the Azure cloud (endpoints come from `az cloud show`, never
hard-coded), the sign-in and Cloud Shell's persistent storage.

## Identity

The `id.*` checks: subscription Owner, the Entra roles for admin consent, app registration and,
for AD DS or Entra Domain Services, domain reachability (always `manual`).

- An Owner or role-assigning assignment that carries a **condition** (the portal's default "all
  roles except privileged ones") is a `warn`, not a pass: it can block the role assignments
  Nerdio's install and the kit make.
- Roles that are **eligible in PIM but not active** are a `warn` with `./nerdio fix roles`. The
  az CLI's Graph token usually can't read Entra PIM eligibility, so that half often comes back
  `no-access`; `./nerdio fix roles` reads it with its own sign-in.
- A **guest** (B2B) account, or one signed in outside its home tenant, is a `warn`.
- A `nerdio-nmw-app` registration left by an earlier install is a `warn`: reuse or delete it.

## Subscription

The `sub.*` checks: resource providers (Nerdio's list, including Microsoft.RecoveryServices, plus
what selected features need, in the target subscription and every `--host-pool-subscriptions`
one), the region, App Service plans and quota (one B3 for Nerdio, plus the Insights plans with
`--features insights`), Azure SQL, enforced policy assignments, the offer type (free and
credit-based offers usually can't deploy third-party Marketplace offers; *unverified list*),
resource locks, an empty target group for the Marketplace path (`--resource-group`) and, for the
kit's Terraform install, whether the Key Vault, storage, SQL server and web app names it plans are
free. Names are global, so that check asks Azure's name-availability APIs, the only POSTs a
default check may make: they evaluate and reserve nothing.

## Network

The `net.*` checks: the AVD range against existing networks, the hub network and peering rights,
and existing `privatelink` zones (including `privatelink.azure-automation.net`) you may want to
link instead of creating new ones.

Installing into an existing network (standalone `--vnet-id` with `--hosts-subnet`,
`--pe-subnet` and `--app-subnet`), `net.subnets` checks each subnet exists and is /28 or bigger,
and that the App Service integration subnet is delegated to `Microsoft.Web/serverFarms`; the fix
command is printed, never run. `net.outbound` checks the session host subnet has a way out: a
NAT gateway or a 0.0.0.0/0 route to a firewall. Without either, a subnet with default outbound
access turned off is a `fail`, and one still relying on it is a `warn` (VNets created after
31 March 2026 don't get it).

## AI

With `--features ai` and `--ai-model <name>` (the model Nerdio's Copilot docs name), the `ai.*`
checks look for the Cognitive Services provider, the model offered as Global or Data Zone
Standard in the region, and free quota for it. Quota requests have no API, so a shortfall links
Microsoft's form.

## AVD

Before the install, the `avd.*` checks look at the session host size, its vCPU quota at full
scale, the Marketplace image in the region (and Generation 2 for Windows 11), premium file shares
for FSLogix, and user licenses. After the wizard they read the AVD estate Nerdio manages through
`Microsoft.DesktopVirtualization` (az has no built-in commands for it, so these are ARM GETs):

- Entra-joined hosts: someone holds **Virtual Machine User Login**, and host pool RDP properties
  allow Entra sign-in (`enablerdsaadauth:i:1` or `targetisaadjoined:i:1`).
- Every application group has users and is in a workspace.
- Start VM on connect has the Azure Virtual Desktop service principal (matched by Microsoft's
  published app ID, since its display name varies) holding a power-on role; Microsoft scaling
  plans need **Power On Off Contributor** at subscription scope (`--features self-service` or
  `automation`).
- Session hosts aren't `Unavailable`, `NeedsAssistance` or `UpgradeFailed`, with the failing
  health check named. `Upgrading` is normal, and auto-scale shuts hosts down.
- Host pools and workspaces send diagnostics to Log Analytics.
- The FSLogix share signs in the way the hosts join (Entra Kerberos, AD DS or Entra Domain
  Services), users and admins hold the SMB share roles, and it isn't open to the internet.

## Nerdio Manager

The `nme.*` checks, after the install:

- **Resources**: the web app, App Service plan, Key Vault, SQL, Automation account and
  Application Insights are all in Nerdio's group.
- **Web app**: running, HTTPS-only, TLS 1.2, FTP off, managed identity on.
- **Health page**: `<nerdio_url>/public/health/status` answers. It allows one request per five
  minutes, so a rate-limited answer is `skipped`, never unhealthy. Its body format is unverified.
- **Version**: `manual`; Nerdio has no read of its version yet (an upstream ask).
- **Entra app**: one `nerdio-nmw-app` registration with a service principal, admin consent for
  its application permissions, tenant-wide consent for its delegated ones (the wizard's second
  consent), and no certificate expiring within 30 days.
- **Azure roles**: Reader and Backup Reader on the subscription and Contributor on its groups;
  Owner or Contributor on the whole subscription is a `warn`.
- **SQL**: collation `SQL_Latin1_General_CP1_CI_AS` (it can't change later), S1 or larger,
  Entra-only sign-in.
- **Certificates and Automation**: nothing in the vault or the Automation account expires within
  30 days, and the updater runbook is there.
- **Smart Detection**: warns when Azure created the "Application Insights Smart Detection" action
  group, which blocks a teardown.
- **REST API** (post-wizard): an application holds Nerdio's `RestClient` role; the kit's stage 2
  needs it.

## Hardening

With `--features hardening`, after the wizard: SQL, Key Vault, the web app, Automation and
storage have private endpoints and refuse public traffic; the web app is VNet-integrated with
route-all on; SQL has no "Allow Azure services" rule; basic publishing credentials are off on the
core app (Nerdio's docs say the Intune and Real-Time Insights apps need them on theirs); private
storage has a hybrid worker for runbook scripted actions; Key Vault, SQL and the web app send
diagnostics; Nerdio's group has a delete lock; and purge protection's state is reported (Nerdio's
template leaves it off). MFA through Conditional Access is usually `manual`: `az rest` tokens
carry only the Azure CLI's own Graph scopes, which don't include `Policy.Read.All`.

## Roles and self-service

With `--features rbac`: at least two holders of Nerdio's Admin role (`WvdAdmin`), at least one
assigned directly, because Entra gives the enterprise app's owner role only to directly assigned
users; the other roles held by groups with members; and, before the install, whether you hold the
Azure roles Nerdio's admins need to link groups and networks. With `--features self-service`:
someone holds `EndUser`, the app is enabled and has tenant-wide consent (Conditional Access stays
`manual`).

## Kit

In kit mode, `kit.terraform_checks` reads each initialised stage's state (`terraform state
pull`, which only reads) and reports the kit's own `check` blocks, such as `nerdio_health`, as of
the last plan or apply. Outside the pipeline it is `skipped` unless the stage is initialised.
The state holds sensitive values, so this is the one default check that loads them; it keeps
only `check_results`.

## Applications

With `--features app-mgmt`: the tenant has Intune licenses and Nerdio's app holds
`DeviceManagementApps.ReadWrite.All` with consent (the Intune repository); before the install,
private WinGet's providers and Cosmos DB access in the region; after the wizard, no security group
denies outbound 443 to the internet. The Shell Apps storage account and a ConfigMgr repository are
`manual`: the first has no documented name, the second lives on-premises. With
`--features app-attach` and `--set app_attach_storage=<name>` (standalone: `--app-attach-storage`):
the account is in the hosts' subscription, Entra-joined hosts have **Reader and Data Access** for
both Azure Virtual Desktop service principals, AD DS hosts have a joined account and a share role
(NTFS stays `manual`), host pools don't run Windows Server, and premium shares are offered.
After the wizard, `app.repository` also checks that Nerdio's group has a storage account for
Unified Application Management packages, and `attach.packages` that every App Attach package on
a host pool has an image path.

## Insights

With `--features insights` (and `--set intune_devices=<n>` for sizing): SQL S1, S2 or S4 for the
device count is offered in the region (App Service plans and Cost Attribution's P0v3 are in
`sub.app_service`); you can grant the Insights identities their roles (Owner, RBAC Administrator
or User Access Administrator, plus Global or Privileged Role Administrator once); Real-Time
Insights gets its own Key Vault and SQL (`--set rti_reuse_existing=no` records it). After the
wizard: the Insights identities hold exactly Storage Blob and Table Data Contributor, Monitoring
Reader and Log Analytics Reader, the Intune Insights identity holds `Directory.Read.All`, and
Microsoft's AVD Insights rule (`microsoft-avdi-*`) exists. Insights apps are found by name in
Nerdio's group, which is inferred; endpoint reach and execution policy are `manual`. `ins.workspace` checks that Nerdio's Log Analytics workspace keeps at least 30 days of data.

## Scripted actions and automation

With `--features scripted-actions`: Azure runbook scripted actions look on, no Automation module
failed to import, storage-mode scripts can reach private storage (or a hybrid worker runs them),
hybrid workers checked in within the hour and you can list Nerdio's vault certificates. Which
mode is set, and Windows scripted actions' Custom Script Extension, are `manual`. With
`--features automation`: Microsoft.RecoveryServices is registered and a vault is in the region,
image builds have a gallery and a VM's worth of quota, and Start VM on connect and scaling plans
have their power roles. After the wizard, `sa.automation_identity` checks that Nerdio's Automation
account has a system-assigned identity and runbooks, and `auto.scaling` that pooled host pools set
a session limit, so session-based auto-scale can trigger.

## Policy evaluation

`sub.policy_eval` is `manual`. Read-only evaluation through Policy Insights'
`checkPolicyRestrictions` is unproven: it may miss child resources such as a SQL firewall rule,
the case that broke a real deploy. The spike needs a live run in the personal sandbox with a
deny policy on a child resource; until then it's a no-go and the result points at Nerdio's
script. Its POST would also need adding to the guard's evaluate-only list, which today holds only
name availability.

## Nerdio data tier

`--nerdio-data` adds read-only GETs of Nerdio Manager's own REST API: `nme.wizard` reads the
directory profile (`GET /api/v1/ad/config`, the only wizard step the API exposes; the network
and resource group links stay `manual`), and `nme.rest_api` makes one read. It signs in with the
REST client's credentials:

- **Kit:** base URL, tenant, client and scope from `02-nerdio-config/platform.auto.tfvars.json`
  (none are secrets), and the secret from the kit's Key Vault, which needs **Key Vault Secrets
  User** on that vault only.
- **Standalone:** `NME_CLIENT_ID`, `NME_SCOPE` and `NME_CLIENT_SECRET` in your own shell (the nme
  provider's names; `NME_BASE_URL` and `NME_TENANT_ID` default to `--nerdio-url` and your
  tenant). Nerdio shows the secret once and stores it nowhere, so a Marketplace install has it only
  where you saved it. Never paste it into a chat.

The secret stays in the process: it isn't printed, logged or sent anywhere but the sign-in
endpoint. Default-tier checks can't read secrets at all: the guard refuses any `az` command
naming secrets, keys, credentials or app settings, and Key Vault data-plane or `list*Keys` URLs.

## Probes

`--probe url-check --vm <session host ID>` runs Microsoft's Required URL Check tool
(`WVDAgentUrlTool.exe`, installed with the AVD agent) on one host through Run Command, which
runs the script as SYSTEM on that VM. It needs **Virtual Machine Contributor** on the VM, says
what it does and waits for a typed `yes`, and refuses to run without a terminal or in GitHub
Actions; the setup chat never offers it. It creates no Azure resource, and the VM's activity log
keeps a record. The tool's output format is unverified, so anything that isn't plainly fine is a
`warn` with the lines shown. `net.url_check` reads the agent's own URL health result first and is
`manual`, never `pass`, when hosts don't report it.

## Nerdio's own readiness script

Nerdio's Solutions Engineering team publishes `Test-NmeDeploymentReadiness.ps1` in the
[Get-Nerdio/NME-SE](https://github.com/Get-Nerdio/NME-SE) repository, linked from Nerdio's
installation preparation article. Facts, from its README:

- It checks the installer's Entra roles, subscription Owner and resource providers, then tests
  **deployability**: it creates throwaway copies of the resources the installer makes, reports a
  blocking Azure Policy by name, tests private endpoints, private DNS, App Service VNet
  integration and outbound reach, and deletes everything.
- It needs **Owner** and **creates resources**, so in a strict tenant running it is itself a change.
- It runs in PowerShell 7 with the Az modules (Cloud Shell's PowerShell mode works), interactively.
- It has no license, so this kit uses it for facts only and never copies, wraps or re-hosts it.

Use ours first (read-only, any time, in the pipeline) and Nerdio's when you need to know whether
Azure Policy will deny the install; our `sub.policy_list` result links it. Read-only policy
evaluation (`sub.policy_eval`) stays Nerdio's job until a spike proves ours.

Nerdio's health page, `<nerdio_url>/public/health/status`, answers unauthenticated and allows
one request per five minutes; `nme.health` reads it.

## Catalogue

Generated from the registry. Stage letters: P pre-install, I post-install, W post-wizard.

<!-- BEGIN GENERATED: readiness-catalogue (./nerdio preflight --list --write) -->
| ID | Stage | Check | Feature | Right needed | Reads with |
|---|---|---|---|---|---|
| `ai.models` | P | [Copilot model](https://learn.microsoft.com/azure/ai-services/openai/concepts/models) | ai | Reader on the subscription | az cognitiveservices model list |
| `ai.provider` | P | [Cognitive Services provider](https://learn.microsoft.com/azure/ai-services/openai/how-to/create-resource) | ai | Reader on the subscription | az provider show |
| `ai.quota` | P | [Copilot quota](https://learn.microsoft.com/azure/ai-services/openai/quotas-limits) | ai | Reader on the subscription | az cognitiveservices usage list |
| `app.intune_repo` | W | [Intune app repository](https://learn.microsoft.com/graph/permissions-reference) | app-mgmt | Directory Readers | Graph /subscribedSkus, Graph /servicePrincipals/{id}/appRoleAssignments |
| `app.private_winget` | P | [Private WinGet](https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps) | app-mgmt | Reader on the subscription | az provider show, ARM Microsoft.DocumentDB/locations |
| `app.repository` | W | [UAM package storage](https://nmehelp.getnerdio.com/hc/en-us/articles/26124345260941-Nerdio-Manager-Default-Deployment-Resources-and-Costs) | app-mgmt | Reader on Nerdio's resource group | az resource list |
| `app.sccm` | P | [ConfigMgr repository](https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps) | app-mgmt | none | - |
| `app.shell_apps` | W | [Shell Apps storage](https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps) | app-mgmt | Reader on Nerdio's resource group | - |
| `app.winget_reach` | W | [WinGet reach](https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps) | app-mgmt | Reader on the subscription | az network nsg list |
| `attach.adds_hosts` | W | [App Attach for AD DS hosts](https://nmehelp.getnerdio.com/hc/en-us/articles/26124362318989-Configure-Azure-Files-Permissions-for-App-Attach) | app-attach | Reader on the subscription | az storage account list, az role assignment list |
| `attach.entra_hosts` | W | [App Attach for Entra-joined hosts](https://nmehelp.getnerdio.com/hc/en-us/articles/26124362318989-Configure-Azure-Files-Permissions-for-App-Attach) | app-attach | Reader on the subscription | az role assignment list, az ad sp list |
| `attach.host_pools` | W | [App Attach host pools](https://learn.microsoft.com/azure/virtual-desktop/app-attach-overview) | app-attach | Reader on the subscription | ARM hostPools/sessionHosts |
| `attach.packages` | W | [App Attach packages](https://learn.microsoft.com/azure/virtual-desktop/app-attach-overview) | app-attach | Reader on the subscription | ARM hostPools, ARM hostPools/msixPackages |
| `attach.premium` | P | [App Attach premium shares](https://nmehelp.getnerdio.com/hc/en-us/articles/26124362318989-Configure-Azure-Files-Permissions-for-App-Attach) | app-attach | Reader on the subscription | az storage sku list |
| `attach.storage_sub` | P, W | [App Attach storage](https://nmehelp.getnerdio.com/hc/en-us/articles/26124362318989-Configure-Azure-Files-Permissions-for-App-Attach) | app-attach | Reader on the subscription | az storage account list |
| `auto.backup` | P, W | [Backup](https://learn.microsoft.com/azure/backup/backup-azure-vms-introduction) | automation | Reader on the subscription | az provider show, az backup vault list |
| `auto.image_mgmt` | P | [Image management](https://learn.microsoft.com/azure/virtual-machines/shared-image-galleries) | automation | Reader on the subscription | az sig list, az vm list-usage |
| `auto.scaling` | W | [Host pool session limits](https://learn.microsoft.com/azure/virtual-desktop/autoscale-scenarios) | automation | Reader on the subscription | ARM hostPools |
| `avd.assignments` | W | [User assignments](https://learn.microsoft.com/azure/virtual-desktop/app-groups) | core | Reader on the subscription | ARM applicationGroups, ARM workspaces, az role assignment list |
| `avd.diagnostics` | W | [AVD diagnostics](https://learn.microsoft.com/azure/virtual-desktop/insights) | core | Reader on the subscription | ARM diagnosticSettings |
| `avd.entra_join_login` | W | [Entra sign-in to hosts](https://learn.microsoft.com/azure/virtual-desktop/azure-ad-joined-session-hosts) | core | Reader on the subscription | az role assignment list, ARM hostPools |
| `avd.fslogix_storage` | P, W | [FSLogix storage](https://learn.microsoft.com/azure/virtual-desktop/fslogix-profile-container-configure-azure-files-active-directory) | core | Reader on the subscription | az storage sku list, az storage account list, az role assignment list |
| `avd.host_health` | W | [Session hosts](https://learn.microsoft.com/azure/virtual-desktop/troubleshoot-statuses-checks) | core | Reader on the subscription | ARM hostPools/sessionHosts |
| `avd.image` | P | [Session host image](https://learn.microsoft.com/azure/virtual-machines/generation-2) | core | Reader on the subscription | az vm image list-skus, az vm list-skus |
| `avd.licenses` | P | [AVD user licenses](https://learn.microsoft.com/azure/virtual-desktop/prerequisites) | core | none | - |
| `avd.start_vm_on_connect` | W | [Start VM on connect](https://learn.microsoft.com/azure/virtual-desktop/start-virtual-machine-connect) | self-service, automation | Reader on the subscription | ARM hostPools, ARM scalingPlans, az role assignment list, az ad sp list |
| `avd.vcpu` | P | [vCPU quota](https://learn.microsoft.com/azure/quotas/per-vm-quota-requests) | core, automation | Reader on the subscription | az vm list-skus, az vm list-usage |
| `avd.vm_size` | P | [VM size](https://learn.microsoft.com/azure/azure-resource-manager/troubleshooting/error-sku-not-available) | core | Reader on the subscription | az vm list-skus |
| `hard.diagnostics` | W | [Nerdio diagnostics](https://learn.microsoft.com/azure/azure-monitor/essentials/diagnostic-settings) | hardening | Reader on Nerdio's resource group | ARM diagnosticSettings |
| `hard.kv_purge` | W | [Key Vault purge protection](https://learn.microsoft.com/azure/key-vault/general/soft-delete-overview) | hardening | Reader on Nerdio's resource group | az keyvault show |
| `hard.locks` | W | [Delete lock](https://learn.microsoft.com/azure/azure-resource-manager/management/lock-resources) | hardening | Reader on Nerdio's resource group | az lock list |
| `hard.mfa` | W | [MFA for Nerdio Manager](https://learn.microsoft.com/entra/identity/conditional-access/policy-all-users-mfa-strength) | hardening | Policy.Read.All (Security Reader or Global Reader) | Graph /identity/conditionalAccess/policies |
| `hard.private_endpoints` | W | [Private endpoints](https://learn.microsoft.com/azure/private-link/private-endpoint-overview) | hardening | Reader on Nerdio's resource group | az resource show |
| `hard.runbooks_vs_private_storage` | W | [Runbooks and private storage](https://nmehelp.getnerdio.com/hc/en-us/articles/26124302308109) | hardening | Reader on Nerdio's resource group | az resource show, ARM automationAccounts/hybridRunbookWorkerGroups |
| `hard.scm` | W | [Publishing credentials](https://learn.microsoft.com/azure/app-service/configure-basic-auth-disable) | hardening | Reader on Nerdio's resource group | ARM sites/basicPublishingCredentialsPolicies, az webapp config show |
| `hard.sql_firewall` | W | [SQL firewall](https://learn.microsoft.com/azure/azure-sql/database/firewall-configure) | hardening | Reader on Nerdio's resource group | ARM sql servers/firewallRules |
| `hard.vnet_integration` | W | [App Service VNet integration](https://learn.microsoft.com/azure/app-service/overview-vnet-integration) | hardening | Reader on Nerdio's resource group | az webapp show |
| `id.app_registration` | P | [App registration](https://learn.microsoft.com/graph/api/resources/authorizationpolicy) | core | your own default directory read rights | Graph /me/transitiveMemberOf, Graph /policies/authorizationPolicy |
| `id.domain_join_account` | P | [Domain reachability](https://learn.microsoft.com/azure/virtual-desktop/prerequisites) | core | nothing in Azure; a person confirms it | - |
| `id.entra_roles` | P | [Entra admin role](https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps) | core | your own default directory read rights | Graph /me/transitiveMemberOf |
| `id.leftover_app` | P | [Earlier Nerdio app](https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps) | core | your own default directory read rights | Graph /applications |
| `id.pim_eligible` | P | [PIM roles](https://learn.microsoft.com/rest/api/authorization/role-eligibility-schedule-instances/list-for-scope) | core | your own PIM eligibility (read) | ARM roleEligibilityScheduleInstances asTarget(), Graph roleEligibilityScheduleInstances |
| `id.sub_owner` | P | [Subscription Owner](https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps) | core | Reader on the subscription | az ad signed-in-user show, az role assignment list |
| `id.tenant_match` | P, I, W | [Home tenant](https://learn.microsoft.com/entra/external-id/user-properties) | core | your own default directory read rights | az account show, Graph /me |
| `ins.avd_insights` | W | [AVD Insights](https://learn.microsoft.com/azure/virtual-desktop/insights) | insights | Reader on the subscription | ARM dataCollectionRules |
| `ins.capacity` | P | [Insights SQL tier](https://nmehelp.getnerdio.com/hc/en-us/articles/35702701977485) | insights | Reader on the subscription | ARM Microsoft.Sql/locations/capabilities |
| `ins.enabler_rights` | P | [Rights to turn on Insights](https://nmehelp.getnerdio.com/hc/en-us/articles/35702701977485) | insights | Reader on the subscription | az role assignment list, Graph /me/transitiveMemberOf |
| `ins.identity_roles` | W | [Insights identities](https://nmehelp.getnerdio.com/hc/en-us/articles/35702701977485) | insights | Reader on the subscription | az webapp identity show, az role assignment list |
| `ins.intune_graph` | W | [Intune Insights Graph access](https://nmehelp.getnerdio.com/hc/en-us/articles/35702701977485) | insights | Directory Readers | az webapp identity show, Graph appRoleAssignments |
| `ins.rti_endpoints` | W | [Real-Time Insights endpoints](https://nmehelp.getnerdio.com/hc/en-us/articles/41694103483533-Insights-Real-Time) | insights | none | - |
| `ins.rti_new_kv_sql` | P | [Real-Time Insights stores](https://nmehelp.getnerdio.com/hc/en-us/articles/41694103483533-Insights-Real-Time) | insights | none | - |
| `ins.workspace` | W | [Log Analytics workspace](https://learn.microsoft.com/azure/virtual-desktop/insights) | insights | Reader on Nerdio's resource group | ARM operationalInsights/workspaces |
| `kit.terraform_checks` | I, W | [Terraform checks](https://developer.hashicorp.com/terraform/language/checks) (kit only) | core | read access to the Terraform state (it holds sensitive values) | terraform state pull |
| `net.hub` | P | [Hub network](https://learn.microsoft.com/azure/virtual-network/virtual-network-peering-overview) | core | Reader on the hub VNet | az network vnet show, az role assignment list |
| `net.outbound` | P, W | [Outbound access](https://learn.microsoft.com/azure/virtual-network/ip-services/default-outbound-access) | core | Reader on the VNet | az network vnet subnet show, az network route-table show |
| `net.overlap` | P | [Address range](https://learn.microsoft.com/azure/virtual-network/virtual-network-peering-overview) | core | Reader on the subscription | az network vnet list, az group list |
| `net.private_dns` | P | [Private DNS](https://learn.microsoft.com/azure/private-link/private-endpoint-dns) | core | Reader on the private DNS zones' subscription | az network private-dns zone list |
| `net.subnets` | P | [Existing subnets](https://learn.microsoft.com/azure/app-service/overview-vnet-integration#subnet-requirements) (standalone only) | core | Reader on the VNet | az network vnet subnet show |
| `net.url_check` | W | [Required URLs](https://learn.microsoft.com/azure/virtual-desktop/required-url-check-tool) | core | Reader on the subscription | ARM hostPools/sessionHosts |
| `nme.app` | I | [Web app](https://learn.microsoft.com/azure/app-service/overview-security) | core | Reader on Nerdio's resource group | az webapp show, az webapp config show |
| `nme.automation` | I | [Nerdio's Automation](https://nmehelp.getnerdio.com/hc/en-us/articles/26124345260941-Nerdio-Manager-Default-Deployment-Resources-and-Costs) | core | Reader on Nerdio's resource group | ARM automationAccounts/runbooks, ARM automationAccounts/certificates |
| `nme.discover` | I, W | [Nerdio resources](https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps) | core | Reader on Nerdio's resource group | az resource list, az webapp list |
| `nme.entra_app` | I | [Nerdio's Entra app](https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps) | core | Directory Readers | Graph /applications, Graph /servicePrincipals, appRoleAssignments, oauth2PermissionGrants |
| `nme.health` | I | [Health page](https://nmehelp.getnerdio.com/hc/en-us/articles/26124379482381-How-to-Check-the-Health-of-Nerdio-Manager) | core | none (unauthenticated) | GET <nerdio_url>/public/health/status |
| `nme.keyvault` | I | [Nerdio's certificates](https://learn.microsoft.com/azure/key-vault/general/rbac-guide) | core | Key Vault Reader on Nerdio's vault | az keyvault certificate list |
| `nme.rest_api` | W | [Nerdio REST API](https://nmehelp.getnerdio.com/hc/en-us/articles/27422824784269) | core | Directory Readers | Graph /servicePrincipals/{id}/appRoleAssignedTo |
| `nme.smart_detection` | I | [Smart Detection action group](https://learn.microsoft.com/azure/azure-monitor/alerts/proactive-arm-config) | core | Reader on Nerdio's resource group | az monitor action-group list |
| `nme.sp_roles` | I, W | [Nerdio's Azure roles](https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps) | core | Reader on the subscription | az role assignment list |
| `nme.sql` | I | [Nerdio's SQL](https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps) | core | Reader on Nerdio's resource group | az sql server show, az sql db show |
| `nme.version` | I, W | [Nerdio version](https://nmehelp.getnerdio.com/hc/en-us/articles/26124379482381-How-to-Check-the-Health-of-Nerdio-Manager) | core | none | - |
| `nme.wizard` | W | [Nerdio's wizard](https://nmehelp.getnerdio.com/hc/en-us/articles/27422824784269) | core | Nerdio's REST client (the data tier, --nerdio-data) | Nerdio GET /api/v1/ad/config |
| `op.cloud` | P, I, W | [Azure cloud](https://learn.microsoft.com/cli/azure/manage-clouds-azure-cli) | core | none | az cloud show |
| `op.cloudshell_storage` | P | [Cloud Shell storage](https://learn.microsoft.com/azure/cloud-shell/persisting-shell-storage) (kit only) | core | none | environment, ~/clouddrive |
| `op.signin` | P, I, W | [Azure sign-in](https://learn.microsoft.com/cli/azure/authenticate-azure-cli) | core | none | az account show |
| `op.tools` | P | [Tools](https://learn.microsoft.com/azure/cloud-shell/features) | core | none | PATH |
| `rbac.admins` | W | [Nerdio admins](https://nmehelp.getnerdio.com/hc/en-us/articles/26124313324173) | rbac | Directory Readers | Graph /servicePrincipals/{id}/appRoleAssignedTo |
| `rbac.azure_side` | P | [Azure rights for Nerdio admins](https://nmehelp.getnerdio.com/hc/en-us/articles/26124313324173) | rbac | Reader on the subscription | az role assignment list |
| `rbac.groups` | W | [Nerdio role groups](https://nmehelp.getnerdio.com/hc/en-us/articles/26124313324173) | rbac | Directory Readers | Graph /servicePrincipals/{id}/appRoleAssignedTo, Graph /groups/{id}/members |
| `sa.automation_identity` | W | [Scripted Actions identity](https://nmehelp.getnerdio.com/hc/en-us/articles/26124302308109) | scripted-actions | Reader on Nerdio's resource group | az resource show, ARM automationAccounts/runbooks |
| `sa.hybrid_worker` | W | [Hybrid workers](https://learn.microsoft.com/azure/automation/automation-hybrid-runbook-worker) | scripted-actions | Reader on Nerdio's resource group, Key Vault Reader | ARM hybridRunbookWorkerGroups/hybridRunbookWorkers, az keyvault certificate list |
| `sa.mode_vs_network` | W | [Scripted actions and storage](https://nmehelp.getnerdio.com/hc/en-us/articles/26124302308109) | scripted-actions | Reader on Nerdio's resource group | az resource show, ARM automationAccounts/hybridRunbookWorkerGroups |
| `sa.modules` | W | [Automation modules](https://nmehelp.getnerdio.com/hc/en-us/articles/26124302308109) | scripted-actions | Reader on Nerdio's resource group | ARM automationAccounts/modules |
| `sa.runbooks_enabled` | W | [Azure runbook scripted actions](https://nmehelp.getnerdio.com/hc/en-us/articles/26124302308109) | scripted-actions | Reader on Nerdio's resource group | ARM automationAccounts/runbooks |
| `sa.windows` | P | [Windows scripted actions](https://learn.microsoft.com/azure/virtual-machines/extensions/custom-script-windows) | scripted-actions | none | - |
| `self.consent` | W | [Self-service sign-in](https://learn.microsoft.com/entra/identity/enterprise-apps/what-is-access-management) | self-service | Directory Readers | Graph /servicePrincipals, Graph /oauth2PermissionGrants |
| `self.end_user_role` | W | [Self-service users](https://nmehelp.getnerdio.com/hc/en-us/articles/26124313324173) | self-service | Directory Readers | Graph /servicePrincipals/{id}/appRoleAssignedTo |
| `sub.app_service` | P | [App Service quota](https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps) | core, insights | Reader on the subscription | az appservice list-locations, ARM Microsoft.Web/locations/usages |
| `sub.empty_rg` | P | [Target resource group](https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps) | core | Reader on the resource group | az group exists, az resource list |
| `sub.locks` | P | [Resource locks](https://learn.microsoft.com/azure/azure-resource-manager/management/lock-resources) | core | Reader on the subscription | az lock list |
| `sub.names` | P | [Resource names](https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules) (kit only) | core | Reader on the subscription | az keyvault list-deleted, az keyvault check-name, az storage account check-name, ARM checkNameAvailability (Microsoft.Sql, Microsoft.Web) |
| `sub.nerdio_license` | P | [Nerdio license](https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps) | core | none | - |
| `sub.policy_eval` | P | [Policy evaluation](https://learn.microsoft.com/rest/api/policyinsights/policy-restrictions/check-at-subscription-scope) | core | none | - |
| `sub.policy_list` | P | [Azure Policy](https://learn.microsoft.com/azure/governance/policy/overview) | core | Reader on the subscription | az policy assignment list |
| `sub.providers` | P, W | [Resource providers](https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps) | core | Reader on the subscription and each host pool subscription | az provider list |
| `sub.region` | P | [Region](https://learn.microsoft.com/cli/azure/account#az-account-list-locations) | core | Reader on the subscription | az account list-locations |
| `sub.sql` | P | [Azure SQL region](https://learn.microsoft.com/rest/api/sql/capabilities/list-by-location) | core | Reader on the subscription | ARM Microsoft.Sql/locations/capabilities |
| `sub.type` | P | [Subscription offer](https://learn.microsoft.com/marketplace/purchase-saas-offer-in-azure-portal) | core | Reader on the subscription | ARM GET /subscriptions/{id} |
<!-- END GENERATED: readiness-catalogue -->
