---
title: "Security baselines and hardening"
summary: "Security baselines Nerdio publishes, kit hardening, and how to record accepted risks"
topic: security
status: verified
last_reviewed: 2026-10-28
---

# Security baselines and hardening

Security building blocks for a Nerdio + AVD deployment, and the patterns for recording accepted
risks. The chat assistant's `security-review`, `encryption` and `endpoint-mgmt` skills draw on this
page (see [../chat-assistant.md](../chat-assistant.md#6-security-review-and-hardening)).

## What Nerdio already publishes

All in [Get-Nerdio/NMW](https://github.com/Get-Nerdio/NMW):

- **`intune-policies/`:** ready-made Intune policy sets: security baselines, attack surface
  reduction (ASR), compliance, Conditional Access, Defender and firewall. Verified against the repo
  files: they are exported Microsoft Graph `/beta` REST JSON payloads (`deviceManagement/configurationPolicies`
  Settings Catalog with `settingInstance`, `deviceManagement/deviceCompliancePolicies` with `@odata.type`,
  and `identity/conditionalAccess/policies` with `includeUsers: ["None"]` placeholder targets). They
  can be posted through `msgraph_resource` in `microsoft/terraform-provider-msgraph` after dropping
  read-only export attributes (`settingCount`) and filling in target group/role IDs, whereas typed
  resources in `microsoft365` take HCL attributes. See also Nerdio's [CIS hardened images and Intune policies](https://nmehelp.getnerdio.com/hc/en-us/articles/30352365514381-Enable-CIS-hardened-images-and-CIS-Intune-policies),
  [ASR AVD exclusions](https://nmehelp.getnerdio.com/hc/en-us/articles/30697557675277-Attack-Surface-Reduction-AVD-Exclusions) and
  [ASR UAM exclusions](https://nmehelp.getnerdio.com/hc/en-us/articles/34054417298957-Attack-Surface-Reduction-UAM-Exclusions).
- **`azure-custom-roles/nme-custom-role.json`:** a least-privilege Azure custom role for Nerdio,
  an alternative to subscription Owner. Verified against `nme-custom-role.json`: its `Actions`
  include `Microsoft.Resources/deployments/*`, `Microsoft.Resources/subscriptions/resourceGroups/*`,
  `Microsoft.Authorization/roleAssignments/*`, `Microsoft.Web/serverfarms/*`, `Microsoft.Sql/servers/*`,
  `Microsoft.KeyVault/vaults/*`, `Microsoft.Storage/storageAccounts/*`, and `Microsoft.Automation/automationAccounts/*`
  (blocking only `roleDefinitions/write` and `delete` in `NotActions`), so it covers both the
  initial NME resource group deployment and day-to-day operation. Our kit's `modules/nerdio-rbac`
  role is stricter for day-2 managed resource groups and omits `Microsoft.Authorization/*/Write` and `Delete`.
- **`scripted-actions/windows-scripts`:** Windows scripted actions for screen capture protection,
  RDP Shortpath and clipboard redirection, among others. See also Nerdio's [Key Vault hardening](https://nmehelp.getnerdio.com/hc/en-us/articles/39637060252685-Harden-key-vault)
  and [Storage Account hardening](https://nmehelp.getnerdio.com/hc/en-us/articles/26124299985165-Harden-Azure-Storage-Account)
  articles, plus community guidance on [AVD strong authentication](https://stealthpuppy.com/avd-w365-secure-authentication/),
  [phishing-resistant FIDO2 MFA](https://markovich.io/avd-phishing-resistant-authentication-bitb-fido2/), and
  [AVD security configurations](https://www.gettothe.cloud/azure-virtual-desktop-security-give-aways/).

## Kit hardening

- Private App Service, SQL, Key Vault, Storage and Automation (`DSCAndHybridWorker`) through
  `modules/nerdio-hardening` and `modules/automation-workers`; see
  [../nerdio/platform.md](../nerdio/platform.md#hardening-private-endpoints).
- Ephemeral VNet Container Apps Job runner (`modules/vnet-runner`, `enable_vnet_runner = true` in
  `01-platform` and `runner_labels = ["self-hosted", "nerdio-vnet"]` in `00-pipeline`): deploys into
  a `/27` Consumption Workload Profile subnet (`snet-vnet-runner`) delegated to
  `Microsoft.App/environments`, authenticates via KEDA `github-runner` (GitHub App or PAT stored in
  Key Vault), and allows `.github/workflows/deploy.yml` to reach private Key Vault, SQL, and state
  storage endpoints when public network access is disabled ([decision 0030](../decisions/0030-enterprise-guardrails-locks-and-gitops.md)).
- `CanNotDelete` management locks (`enable_resource_locks = true` by default in `prod`) on the
  `nerdio` resource group (inheriting down to SQL Server, Key Vault, and App Service), the Stage 2
  REST secret Key Vault, the CMK Key Vault, FSLogix storage accounts/ANF volumes, and the `00-pipeline`
  Terraform state storage account, paired with automated destructive-change guardrails in
  `scripts/pipeline/stage.sh` that block accidental deletion or replacement of stateful Stage 1 and
  Stage 2 resources unless `allow_replace = true` is explicitly passed.
- Static IaC security scanning (`trivy config --severity HIGH,CRITICAL` in `.github/workflows/validate.yml`)
  with documented architectural exceptions in `.trivyignore`.
- Customer-Managed Key (CMK) encryption with an RSA Key Vault key (automatic rotation) and
  per-region Disk Encryption Sets (DES) via `modules/cmk-encryption` (`cmk_encryption` in
  `01-platform`), passed automatically to `02-nerdio-config` host pools.
- Custom least-privilege Azure RBAC role (`modules/nerdio-rbac`, `nerdio_rbac` in `01-platform`)
  that replaces built-in `Contributor` on managed resource groups and explicitly blocks
  `Microsoft.Authorization/*/Write` and `Delete`.
- Intune Windows Update rings, Defender FSLogix/App Attach exclusions, and Entra Conditional Access
  MFA policies via `modules/intune-policies`.
- The golden image is Gen2 with Trusted Launch; see [../packer/avd-image.md](../packer/avd-image.md).

## Accepted risks

When a review finding is accepted instead of fixed, record it as a decision in the environment's
own (private) decision log: the finding, why it's accepted, and when to revisit it. Only general
patterns belong here, never a specific environment's findings.
