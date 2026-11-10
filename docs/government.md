# Azure Government and GCC High

**Short answer: not supported end to end yet.** The kit can now be pointed at Azure Government
with one setting, `cloud = "usgovernment"` (the default stays `public`), and the Azure side of
the deployment (stages `00-pipeline` and `01-platform`, Packer and the readiness engine) follows
it. Two pieces still don't work there: stage `02-nerdio-config`, because the `nerdio/nme`
provider can only sign in to the commercial cloud, and the setup chat, because Claude isn't
offered inside Azure Government. Nothing has been tested in a Government subscription yet.
[Decision 0034](knowledge/decisions/0034-azure-government-cloud-parameter.md) records the choice.

Which cloud is which:

| Microsoft 365 / Entra cloud | Azure cloud the kit targets | `cloud` value |
|---|---|---|
| Commercial and **GCC** | Azure commercial (`AzureCloud`) | `public` |
| **GCC High** | Azure Government (`AzureUSGovernment`) | `usgovernment` |
| DoD (IL5) | Azure Government, DoD regions and DoD Graph | not supported |

GCC tenants use commercial endpoints, so they need nothing from this page
([Microsoft Graph national clouds](https://learn.microsoft.com/graph/deployments)).
Nerdio says the same: GCC is treated as commercial and GCC High as Azure US Government
([Nerdio Manager in Azure Government](https://nmehelp.getnerdio.com/hc/en-us/articles/40495096260493-Nerdio-Manager-in-Azure-Government-What-to-know)).

## How to point the kit at Azure Government

Nothing here deploys anything; it only changes what a plan targets.

1. Sign in to the Government cloud in Cloud Shell. Open Cloud Shell from the Azure Government
   portal (`portal.azure.us`), or run `az cloud set --name AzureUSGovernment` and `az login`.
2. `./nerdio init`: answer `usgovernment` to the cloud question. It writes `cloud` into the
   platform stage, and 01-platform's `nerdio_config_inputs` output carries it on to stage 02.
3. `scripts/pipeline/bootstrap.sh` and `./nerdio assistant` read the cloud from `az cloud show`
   (or `ARM_ENVIRONMENT`) and write it into their own tfvars.
4. The pipeline stage sets `NERDIO_CLOUD` on both GitHub environments. The workflows read it to
   pick `azure/login`'s cloud and token audience, and Packer's `cloud_environment_name`.

## What changes with `cloud = "usgovernment"`

| Piece | Change | Source |
|---|---|---|
| azurerm, azuread, azapi, msgraph providers | `environment = var.cloud` in every stage | Provider docs: azuread lists `usgovernment` (L4, GCC High) and `usgovernmentl5`/`dod`; msgraph and azapi the same family of values |
| Private DNS zones | Government zone names (`modules/network`, readiness engine) | [Compare Azure Government and global Azure](https://learn.microsoft.com/azure/azure-government/compare-azure-government-global-azure#guidance-for-developers) |
| Nerdio app settings (`modules/nerdio-core`) | `*.azurewebsites.us`, `*.vault.usgovcloudapi.net`, `*.database.usgovcloudapi.net`, `login.microsoftonline.us`, `AzureUSGovernment` | Same page |
| Marketplace install hostname (`modules/nerdio-manager`) | `*.azurewebsites.us` | Same page |
| OpenBao VM DNS name | `*.cloudapp.usgovcloudapi.net` | Azure Government DNS suffix |
| GitHub OIDC federation (`modules/deploy-pipeline`, workflows) | Audience `api://AzureADTokenExchangeUSGov`; `azure/login` `environment: azureusgovernment` | [Configure an app to trust a managed identity](https://learn.microsoft.com/entra/workload-id/workload-identity-federation-config-app-trust-managed-identity) lists the audience per cloud |
| Stage 02 REST gap filler | Token endpoint `login.microsoftonline.us` | [Entra national cloud endpoints](https://learn.microsoft.com/entra/identity-platform/authentication-national-cloud) |
| Chat (`modules/assistant`) | Easy Auth issuer and Claude federation issuer on `login.microsoftonline.us`; `AZURE_AUTHORITY_HOST`; Government blob and Key Vault hosts in `assistant/pipeline.py` | [Container Apps Entra auth](https://learn.microsoft.com/azure/container-apps/authentication-entra), [Storage with Entra ID](https://learn.microsoft.com/azure/storage/blobs/authorize-access-azure-active-directory) |
| Packer | `cloud_environment_name = "USGovernment"` | Packer Azure plugin docs |

Two `check` blocks warn (they don't block a plan) when `cloud` isn't `public`: one in stage 02
for the `nerdio/nme` provider, one in `modules/assistant` for Claude.

## What each dependency does in Azure Government

Public documentation only, read on 2026-11-10. "Unknown" means no public source says either way.

| Dependency | Azure Government / GCC High | Status |
|---|---|---|
| **Nerdio Manager for Enterprise** | Installs from the Government Marketplace. No billing in the Government tenant: license activation needs a commercial or partner tenant (only aggregate counts cross). User Cost Attribution isn't available. Only app-credential subscription linking; managed identity and split-identity installs aren't supported. NME in Government can manage commercial identity; NME in commercial can't manage Government AVD. ([Nerdio](https://nmehelp.getnerdio.com/hc/en-us/articles/40495096260493-Nerdio-Manager-in-Azure-Government-What-to-know)) | Supported by Nerdio, with limits |
| NME in **DoD** | Nerdio's MSP edition says it doesn't work with DoD clouds ([Nerdio MSP](https://nmmhelp.getnerdio.com/hc/en-us/articles/26125603051405-Does-Nerdio-Manager-work-with-Azure-Government-Clouds)); the Enterprise page doesn't mention DoD | Treat as unsupported |
| Kit's Terraform-native install (`nerdio-core`) in Government | Nerdio documents the Marketplace path only. Whether its app accepts a Terraform-built install there, and whether any part of it relies on managed identity, is not documented | **Unknown**: needs a Government spike |
| **`nerdio/nme` provider** | Token endpoint is hard-coded to `login.microsoftonline.com`; an internal token URL field isn't exposed ([stack options](knowledge/stack-options.md)) | **Blocked** until Nerdio exposes it |
| Nerdio AI (Copilot, ScriptPro, AnalyticsPro) | Uses Azure OpenAI in the tenant. Azure OpenAI exists in Government (US Gov Arizona and Virginia, endpoint `openai.azure.us`, GPT-4o through GPT-5.x families, no batch) ([Azure OpenAI in Government](https://learn.microsoft.com/azure/ai-foundry/openai/azure-government)). Nerdio doesn't say whether its AI features are turned on in Government | **Unknown** on Nerdio's side |
| **Azure Virtual Desktop** | Available; endpoints `*.wvd.azure.us` and `login.microsoftonline.us`; RDP Shortpath over TURN in preview; AVD on Azure Local in preview with no portal provisioning ([required FQDNs](https://learn.microsoft.com/azure/virtual-desktop/required-fqdn-endpoint), [what's new](https://learn.microsoft.com/azure/virtual-desktop/whats-new)) | Supported |
| App Service, Key Vault, SQL, Automation, Log Analytics, Functions | GA at FedRAMP High and DoD IL4/IL5 ([Government GA roadmap](https://learn.microsoft.com/azure/azure-government/documentation-government-product-roadmap)). App Service managed certificates and App Service Domains aren't available ([comparison](https://learn.microsoft.com/azure/azure-government/compare-azure-government-global-azure#web)); the kit uses neither | Supported |
| **Container Apps** (the chat's host) | Public preview in US Gov Virginia was announced in July 2024; not on the Government GA roadmap pages read; Container Apps private endpoints are listed for public regions only ([Private Link availability](https://learn.microsoft.com/azure/private-link/availability)) | **Unknown** whether GA |
| **Claude** for the chat | Microsoft states Claude models aren't available to GCC High or DoD customers in Microsoft 365 ([AI subprocessors](https://learn.microsoft.com/copilot/implement/connect-to-ai-subprocessor#opt-in-regions-and-exclusions)); Foundry's Claude pages list no Government regions ([Claude in Foundry](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/claude-models)). The Claude API's federation guide documents only the commercial Entra issuer ([Anthropic: WIF with Entra](https://platform.claude.com/docs/en/manage-claude/wif-providers/azure)). Either path would send prompts outside the Government boundary | **Not available** inside Government |
| Workload identity federation (GitHub OIDC) | Supported; the audience is `api://AzureADTokenExchangeUSGov` | Supported (now parameterized) |
| Microsoft Graph and Entra | GCC High: `graph.microsoft.us`, `login.microsoftonline.us`; DoD: `dod-graph.microsoft.us`. Tokens aren't interchangeable across clouds. B2B collaboration has limits; MFA trusted IPs aren't supported ([Graph national clouds](https://learn.microsoft.com/graph/deployments), [comparison: identity](https://learn.microsoft.com/azure/azure-government/compare-azure-government-global-azure#identity)) | Supported (providers handle it) |
| **Cloud Shell** | GA in Azure Government; session regions US Gov Arizona and Virginia; reached through `portal.azure.us` (`console.azure.us`) ([GA roadmap](https://learn.microsoft.com/azure/azure-government/documentation-government-product-roadmap), [persisting storage](https://learn.microsoft.com/azure/cloud-shell/persisting-shell-storage)). An older CLI quickstart still says there's no Cloud Shell in Government; the newer pages win. `shell.azure.com` shortcuts in the kit point at commercial | Supported; iPad unverified |
| Readiness engine | Already reads every endpoint from `az cloud show` | Supported |
| Intune via Nerdio, Windows 365 | Not checked for Government in this pass | Out of scope here |

## Gap list

Ordered by what blocks a Government deployment first.

1. **`nerdio/nme` provider can't sign in to Government.** Stage 02 is unusable there.
   Workaround: configure Nerdio in its console, or move the needed calls to the `restapi` gap
   filler (already cloud-aware). Upstream ask: expose a token URL or cloud setting. Add it to the
   [upstream asks](knowledge/nerdio/upstream-contributions.md); nothing goes to Nerdio until the
   owner says so.
2. **The chat has no Claude inside Government.** Options for the owner to choose between (open
   question, see the decision): keep the chat in a commercial tenant and drive a Government
   deployment only through the GitHub pipeline with no tenant data in prompts; offer an Azure
   OpenAI model provider in Government; or set up Government tenants without the chat
   (`./nerdio init` plus the pipeline). Until then the kit warns and the chat stays commercial.
3. **No Government test bed.** Azure Government needs an eligibility-validated subscription.
   Every "supported" row above is from documentation, not a run.
4. **Terraform's own GitHub OIDC audience.** `azure/login` now asks for the Government audience,
   but the azurerm, azuread, azapi and msgraph providers request their own GitHub token in the
   pipeline. Whether they ask for `api://AzureADTokenExchangeUSGov` when `environment` is
   `usgovernment` must be checked in the first Government plan.
5. **Terraform-native install in Government.** Nerdio documents only the Marketplace path there,
   and says managed identity isn't supported. Check `modules/nerdio-core` against that before
   offering it; until then prefer `nerdio_install = "marketplace"` in Government.
6. **Container Apps GA status** in Government, for the chat and the VNet runner
   (`modules/vnet-runner`).
7. **Small hard-codes left on purpose:** `assistant/agent.py` asks for the commercial Foundry
   scope (Foundry has no Claude in Government anyway), `scripts/nerdio/profiles.py` links to
   `shell.azure.com`, and `modules/network` uses the `AzureCloud` service tag (its name is the
   same in Government).
8. **DoD (IL5)** isn't modeled: `cloud` accepts only `public` and `usgovernment`.
9. **Nerdio licensing** in Government needs a commercial or partner tenant for billing. That's a
   procurement step for the tenant owner, not something the kit automates.

## Plan

Directional, after the current 90-day window ([roadmap](knowledge/stack-options.md)).

1. **Done in this change:** one `cloud` setting, default `public`, flows through every stage,
   module, workflow, script and Packer; warnings where Government can't work yet; tests for both
   clouds.
2. **Government spike** (needs a Government subscription; owner's call): Cloud Shell from
   `portal.azure.us` on an iPad, `00-pipeline` and `01-platform` plans, gap 4, Container Apps
   status, and `./nerdio preflight` against the tenant. Plan only; the tenant owner applies.
3. **Nerdio:** draft the provider token-URL ask and ask Nerdio whether its AI features and a
   Terraform-built install are supported in Government. Hold until the owner approves sending.
4. **Chat in Government:** owner picks an option from gap 2; record it as a new decision.
5. **After that:** Intune and Windows 365 in GCC High (the `microsoft365` provider supports GCC
   High and DoD), and DoD only if Nerdio supports it.
