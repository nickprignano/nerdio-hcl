# Full-stack options for the Nerdio kit (IBM + HashiCorp + Microsoft)

Which HashiCorp, IBM and Microsoft tools fit a Terraform-first Nerdio/AVD kit, with prior art and
what each costs. Scoped 2026-10-16. Nothing here is built yet; this is input for choosing what to build.

## Summary

| Tool | Layer | License / cost | Verdict |
|---|---|---|---|
| **Vault** (or OpenBao) | Secrets | Community edition is free under BUSL; OpenBao is the MPL-2.0 fork; HCP Vault and Enterprise are paid | **Build first** |
| **Packer + HCP Packer** | Images | Packer is free under BUSL; HCP Packer is a paid SaaS (check its free-tier limits) | **Build the image-version link** |
| **Ansible** (in the Packer build) | Image config | ansible-core and the Windows/Azure collections are open source (GPL-3.0); Automation Platform is paid | **Optional, inside Packer only** |
| **msgraph provider** | Entra / M365 | MPL-2.0, published by Microsoft | **Use for Graph gaps azuread doesn't cover** |
| **microsoft365 provider** (community) | Intune | Community project, not supported by Microsoft; confirm the license before depending on it | **Optional Intune module, later** |
| **Boundary** | Admin access | Community edition is free under BUSL; credential injection for RDP needs HCP or Enterprise (verify) | **Later, AD-joined pools only** |
| **Terraform Stacks** | Orchestration | HCP Terraform only, billed by RUM | **Not yet** |
| **Turbonomic** | Right-sizing | Paid IBM SaaS | **Document only; it conflicts with Nerdio auto-scale** |
| **Apptio Cloudability** | FinOps | Paid IBM SaaS | **Document only; the kit just needs consistent tags** |
| **Instana** | Observability | Paid IBM SaaS | **Skip; there's no AVD-specific sensor** |
| **Vault Radar** | Secret scanning | Paid HCP product; free trial only | **Skip; gitleaks already covers the repo** |

Licensing note for a public kit: since 2023, HashiCorp's own tools (Terraform, Packer, Vault,
Boundary) are source-available under BUSL 1.1, not open source. Using them is free for this kit.
The providers it uses (azurerm, azuread, msgraph) are MPL-2.0. If "open source" matters to the
community audience, name OpenTofu and OpenBao as drop-in alternatives in the README.

## Build: Vault

**Gap it closes.** Stage 01 creates the REST API client secret (`modules/nerdio-identity/rest_api.tf`),
so the secret sits in stage 01 state. Stage 02 then needs it handed over through a shell export.
Terraform runs also use long-lived Azure credentials.

**What to build.** Both pieces are optional modules; the kit still works without Vault.
1. *Secret hand-off.* Stage 01 writes the client secret to Vault KV v2. Stage 02 reads it with
   an ephemeral resource (Terraform 1.10+) and passes it to the `nme` provider. The secret then
   never lands in stage 02 state, a tfvars file or a shell variable.
2. *Dynamic Azure credentials.* Vault's Azure secrets engine issues short-lived service principals
   for Terraform runs. Since Vault 1.15, the engine can authenticate to Azure with workload identity
   federation, so Vault holds no long-lived secret either. HCP Terraform has a built-in
   "Vault-backed dynamic credentials" flow for azurerm.

**Caveats.** New service principals take time to replicate in Entra, so add a delay or retry.
Vault's own identity needs `Application.ReadWrite.OwnedBy`. CI can test against `vault server -dev`.

**Prior art.** HashiCorp documents the generic pieces. I found no Vault + Nerdio pattern, so this would be new.

## Build: Packer + HCP Packer

Add an `hcp_packer_registry` block to the existing `packer/avd-win11` template. Stage 02 then reads
the version with the `hcp_packer_artifact` data source and passes it to the host pool's `image`.
The image flows from build to host pool through HCL, and a channel such as `production` makes
rollouts and rollbacks a one-line change.

**Skip the Nerdio post-processor for now.**
- Nerdio's REST API has no "import from Compute Gallery" call. Its desktop image endpoints are
  `create-from-library` (Azure Marketplace), `set-as-image` and script schedules, as seen in the
  community NerdioManagerPowerShell module.
- `nme_dynamic_host_pool` takes an `image` reference directly. *Inferred, not tested:* a gallery
  reference works there, which would make a registration step unnecessary.
- A Nerdio Packer post-processor would be a Go plugin with its own release pipeline, which is a lot of
  upkeep for a registration step that may not be needed.
- There's an open Nerdio community request for better Compute Gallery and version handling
  (Oct 2025, still open in Jun 2026). It's a good upstream-contribution candidate.

**Prior art.** Plenty of AVD + Packer examples exist (pc-dok/N4K-Github-AVD-Packer, msandbu's blog).
None of them integrate with Nerdio.

## Optional: Ansible

The obvious Terraform-to-Ansible handoff doesn't fit Nerdio. Nerdio auto-scale creates and destroys
session hosts, so Terraform never sees them and can't hand them to Ansible. Nerdio's native config
path is scripted actions, which the kit can already manage with `nme_scripted_action`.

Ansible does fit in one place: as a Packer provisioner (`packer-plugin-ansible`), running
`ansible.windows` roles during the image build in place of the PowerShell scripts. That's worth doing
only if the community wants reusable roles. The PowerShell scripts work today.

Terraform actions (1.14+) and the Terraform Ansible collection 2.0 (Jun 2026) mostly target Ansible
Automation Platform, which is paid.

**Prior art.** `azure.azcollection` creates Azure resources but has no AVD session-host role. I found no
Nerdio-specific Ansible content.

## Entra and M365 providers

- **azuread** (already in the kit) covers apps, groups and Conditional Access policies, including CA
  for the Azure Virtual Desktop app. No second provider is needed for CA.
- **microsoft/msgraph** (MPL-2.0, official) is a thin generic layer: `msgraph_resource` takes a Graph
  `url` and a `body`. Use it for gaps such as Intune settings on Entra-joined session hosts. It's
  verbose, but Microsoft supports it.
- **deploymenttheory/terraform-provider-microsoft365** (community) has purpose-built Intune, Teams,
  Exchange and Defender resources and leaves Entra to azuread. It's friendlier but not supported by
  Microsoft. Make it opt-in and pin it.

A later optional module could hold a baseline Intune and Conditional Access setup for session hosts.

## Later: Boundary

RDP targets inject credentials (static or from Vault), so admins never see the host password. Limits:
it needs Active Directory auth (Kerberos or NTLM), so Entra-only joined hosts don't qualify; it needs a
worker in the host pool VNet; and Azure Bastion already covers brokered access natively. It's worth a
later optional module paired with Vault, not core.

## Not yet: Terraform Stacks

Stacks would merge the two stages into one deployment, but it's blocked for now:
- It runs only in HCP Terraform, and since GA, Stacks resources count toward billing.
- Remote runs install providers from a registry. `nerdio/nme` is a GitHub preview installed through
  `dev_overrides`, which a remote Stack can't use.
- Nerdio's install script and wizard still sit between the stages as manual steps.

Revisit once `nerdio/nme` is on the Terraform Registry, which belongs on the upstream contribution list.

## IBM SaaS: document, don't build

- **Turbonomic** resizes and scales VMs. Nerdio auto-scale already owns session-host count and sizing,
  so the two would fight. Turbonomic doesn't optimize GPUs on Windows (an IBM idea for it has been
  "planned" since 2024), which rules out GPU VDI. It could watch non-pool infrastructure such as
  the Nerdio app service and file shares.
- **Cloudability** allocates cost by tags. The kit already merges a `tags` map; a documented tag
  convention (cost center, environment, host pool) is all it needs, and Azure Cost Management reads the same tags.
- **Instana** monitors Azure VMs through its agent, but it has no AVD or session sensor; a Citrix
  VDI sensor is only "planned" (Jun 2026). AVD Insights in Azure Monitor and Nerdio's own monitoring cover this.
- **Vault Radar** is a paid HCP product with a free trial only. The repo's gitleaks CI already
  enforces the no-leak rule for free.

## Suggested order

1. Vault secret hand-off (smallest change, removes the manual secret step)
2. HCP Packer image-version link
3. Vault dynamic Azure credentials
4. Optional Intune/CA module (msgraph first)
5. Boundary for AD-joined pools; Stacks once `nme` is on the Registry

## Sources

- Vault Azure secrets engine: https://developer.hashicorp.com/vault/docs/secrets/azure
- Vault 1.15 workload identity federation: https://www.hashicorp.com/blog/hashicorp-vault-1-15-adopts-microsoft-workload-identity-federation
- Vault-backed dynamic credentials for azurerm: https://developer.hashicorp.com/terraform/cloud-docs/workspaces/dynamic-provider-credentials/vault-backed/azure-configuration
- Terraform Stacks GA notes: https://developer.hashicorp.com/terraform/language/stacks/update-GA
- Boundary RDP targets: https://developer.hashicorp.com/boundary/docs/targets/create/rdp
- What's new with Terraform and Ansible (Jun 2026): https://www.hashicorp.com/en/blog/whats-new-with-terraform-ansible
- Vault Radar tiers: https://developer.hashicorp.com/vault-radar/cloud/get-started/product-tiers
- msgraph provider: https://github.com/microsoft/terraform-provider-msgraph
- microsoft365 community provider: https://www.mintlify.com/deploymenttheory/terraform-provider-microsoft365
- Turbonomic Windows GPU idea: https://automation-management.ideas.ibm.com/ideas/TURBO-I-899
- Instana Citrix VDI idea: https://automation-management.ideas.ibm.com/ideas/INSTANA-I-4896
- Instana Azure VM monitoring: https://www.ibm.com/docs/en/SSE1JP5/src/pages/ecosystem/azure-vm/index.html
- Nerdio desktop image endpoints (community PowerShell module): https://powershellgallery.com/packages/NerdioManagerPowerShell/0.8.6/Content/Public/DesktopImage.ps1
- Nerdio gallery image version request: https://nmmhelp.getnerdio.com/hc/en-us/community/posts/40030830038541
- AVD + Packer example: https://github.com/pc-dok/N4K-Github-AVD-Packer

GitHub prior art for this page came from web search and may miss small repos; re-check with
[`scripts/kb/prior_art.py`](curation.md#prior-art-check-kb-prior-art) before building any of it.

_Last reviewed: 2026-10-16_
