---
title: "Upstream contribution candidates (`nerdio/nme`)"
summary: "Gaps, API asks and doc fixes we could raise with Nerdio, with evidence"
topic: nerdio
status: partial
last_reviewed: 2026-10-16
---

# Upstream contribution candidates (`nerdio/nme`)

Things this project could contribute to [Nerdio's Terraform provider](https://github.com/Get-Nerdio/NME-Terraform-Provider),
if Nerdio accepts outside contributions. Each entry has the evidence behind it so it can become
an issue or PR without re-research. Checked against commit `65e547f` (2026-09-21).

**Status values:** *candidate* (found, not raised) · *raised* (issue/PR link) · *merged* · *dropped* (say why).

## Before contributing anything

- **No license file.** The repo has no `LICENSE`, so by default nobody else has rights to reuse
  or modify the code, and there's no `CONTRIBUTING` guide. Ask Nerdio which license applies and
  whether they take outside PRs (and under what CLA, if any) before writing code for it.
- Nerdio already tracks its own gaps in
  [AVD-COVERAGE.md](https://github.com/Get-Nerdio/NME-Terraform-Provider/blob/main/AVD-COVERAGE.md).
  Line up with that matrix so a contribution fills a gap they've acknowledged.
- They state that imperative actions (power, reimage, drain, run script, log off, convert, clone)
  are out of scope for the provider by design. Don't propose those.

## Feature gaps

<!-- BEGIN GENERATED: feature_gaps (edit the YAML, then run scripts/kb/build.py) -->
| Gap | Evidence | Why it matters | Status |
|---|---|---|---|
| App groups and app group assignments | AVD-COVERAGE 3.1 "Manage app groups" and 3.4 "Assign / unassign users & groups to app groups": ❌ | Users can't be granted desktops as code; the kit has to stop at the host pool. | candidate |
| Session host lifecycle (create, delete, list) | AVD-COVERAGE 3.2: ❌, no data source | Host counts on static pools can't be declared. | candidate |
| Host pool data sources | AVD-COVERAGE §4 "No host pool data sources" | Other stacks can't reference pools the kit didn't create. Likely the smallest useful first PR. | candidate |
| RemoteApps and MSIX app attach | AVD-COVERAGE 3.4: ❌ | RemoteApp deployments need console work. | candidate |
| Reimage and script-execution schedules | AVD-COVERAGE 3.4: ❌ | Image rollout cadence isn't reviewable as code. | candidate |
| Personal host-to-user assignment | AVD-COVERAGE 3.2: 🟡 (`nme_user_assignment` is RBAC only) | Personal-desktop pools need manual assignment. | candidate |
| Per-host-pool auto-scale override profiles | AVD-COVERAGE 3.3: ❌ |  | candidate |
| `nme_image` data source and a desktop image resource | The API already lists gallery images (`GET /api/v1/image?imageType=ComputeGalleryImage`), and `create-from-library` takes any `sourceImageId` from that list (OpenAPI spec `internal/client/api.json`). Desktop images are absent from AVD-COVERAGE entirely. A [community request](https://nmmhelp.getnerdio.com/hc/en-us/community/posts/40030830038541) asks for better gallery and version handling. | A Packer-built gallery image can't be looked up or registered in Nerdio as code. The host pool `image` format for a gallery image isn't documented; the provider example only shows Marketplace format. | candidate |
| Terraform actions for one-off operations | Terraform 1.14+ supports provider actions. Nerdio treats imperative operations (reimage, drain, run script) as out of scope for resources, but actions are designed for exactly these. | Day-2 operations could run from the same Terraform engine instead of separate REST calls in workflows. | candidate |
| A Nerdio MCP server | No Nerdio MCP server exists; the REST API covers hosts, sessions, jobs and images. The roadmap's chat front door would use one, read-only by default with write actions gated behind confirmation. | Lets a chat assistant inspect and operate Nerdio safely. Could be built by us first and offered upstream. | candidate |
| In-place update for `workspace`, `linked_resource_group`, `linked_network` | AVD-COVERAGE §4: no update operation in the NME API, so changes force replacement | Replacing a linked network under live pools is disruptive. Needs a Nerdio API change first, so it's a request, not a PR. | candidate |
| Workload identity federation (client assertion) in the provider | The provider only accepts `client_secret` (`internal/provider/provider.go`, commit `65e547f`). azurerm and azuread already accept OIDC tokens from GitHub Actions and other federated sources. | It would remove the last secret in the kit: the pipeline could sign in to the Nerdio API with GitHub OIDC or a managed identity, and no Key Vault or Vault hand-off would be needed ([decision 0015](../decisions/0015-secrets-key-vault-default-openbao-optional.md)). | candidate |
| Azure Government sign-in (token URL or cloud setting) in the provider | The token endpoint defaults to `https://login.microsoftonline.com/<tenant>/oauth2/v2.0/token` (`internal/provider/provider_clients.go`, commit `65e547f`). The client config already has a `TokenURL` field, but the provider schema doesn't expose it. Nerdio supports NME in Azure Government ([help article 40495096260493](https://nmehelp.getnerdio.com/hc/en-us/articles/40495096260493)). | The provider can't authenticate against `login.microsoftonline.us`, so no Gov or GCC High install can be configured as code. Likely the smallest provider change on this list: a `token_url` attribute with an `NME_TOKEN_URL` variable, or a `cloud` enum. | candidate |
| Azure Local hybrid networks and hybrid host pools | NME supports AVD on Azure Local through "Link Hybrid Network" and Hybrid Host Pools ([25499377328909](https://nmehelp.getnerdio.com/hc/en-us/articles/25499377328909), [40495096378125](https://nmehelp.getnerdio.com/hc/en-us/articles/40495096378125)). The provider only has `hci_gpu_allocation_mode` on `nme_vm_deployment_profile`; the OpenAPI spec has no hybrid network, custom location or hybrid host pool paths. | Azure Local deployments stop at the Azure side; linking the cluster and creating pools stays in the console. | candidate |
| Windows 365 resources or data sources | NME manages Azure network connections, provisioning policies, user settings and Cloud PC lifecycle ([25499404997901](https://nmehelp.getnerdio.com/hc/en-us/articles/25499404997901)). The OpenAPI spec's only Cloud PC trace is `uploadToCloudPc` on the set-as-image call. | The kit can create Cloud PC objects through Graph (`microsoft365` provider), but Terraform and Nerdio can't agree on who owns them without at least a read API in Nerdio. | candidate |
<!-- END GENERATED: feature_gaps -->

## Nerdio API asks (need a Nerdio change, not a provider PR)

These are what stand between the kit and a zero-touch install; see
[../stack-options.md](../stack-options.md). Listed in priority order.

<!-- BEGIN GENERATED: api_asks (edit the YAML, then run scripts/kb/build.py) -->
| Ask | Evidence | Why it matters | Status |
|---|---|---|---|
| Directory profile create API and provider resource | The API only has `GET /api/v1/ad/config` (OpenAPI spec, commit `65e547f`); the profile is chosen in the setup wizard. | The only hard blocker to zero-touch: every install needs a human in the wizard for this. | candidate |
| First-run / registration completion API | Registration and first-run state are UI only. | Second wizard step with no API. | candidate |
| Supported non-interactive install path | `Get-Nerdio/NMW` `templates/mainTemplate.json` exists but isn't declared a supported, versioned deploy path. The install script has no public versioned URL and doesn't support service-principal auth. The package API (`/api/package`, `/{ver}/link`) is used by Nerdio's own update runbook but isn't documented. | Would let Terraform replace the portal export and install script on a supported path. | candidate |
| Documented package API and a flat `app.zip` at a stable URL | The kit's install job uses the undocumented `/api/package` and `/{ver}/link` calls and unpacks a zip inside a zip ([platform.md](platform.md#terraform-install-the-kits-default)). | With a stable, documented URL, `azurerm_windows_web_app` could deploy the code directly and the Automation job could go. | candidate |
| Managed identity for data protection storage | The app reads container SAS URLs from Key Vault (`DataProtection--Storage--Path`, `Deployment--LocksContainerSasUrl`); the kit has to mint 10-year SAS tokens. | Identity-based storage access would remove the only long-lived credential left in the install. | candidate |
| Are scripted UI sessions allowed? | The roadmap has an optional Playwright bridge for the two wizard-only steps ([stack-options.md](../stack-options.md#optional-bridge-playwright-for-the-two-wizard-steps)). Nerdio's terms on automating the console UI weren't checked. | Ask before publishing the bridge in a public kit; the API asks above remain the real fix. | candidate |
| Intune policy, backup and approvals API | NME manages Intune compliance, configuration profiles, baselines, Conditional Access, apps and Windows Update with backups and an approval workflow ([25499402447373](https://nmehelp.getnerdio.com/hc/en-us/articles/25499402447373), [32612203319693](https://nmehelp.getnerdio.com/hc/en-us/articles/32612203319693)). The OpenAPI spec has only an Intune device console-connect call and Intune devices in user entitlements; turning the integration on is a console step with Global Administrator consent. | Policy as code today has to go straight to Graph, which skips Nerdio's approvals. An API (and turning the integration on without the console) would let Terraform drive Nerdio-managed Intune with its guardrails intact. | candidate |
| A license on Get-Nerdio/NME-SE (the readiness script) | The repository publishes Test-NmeDeploymentReadiness.ps1 with no license file | Community tools can't reuse or package its checks; the kit can only cite facts from it. | candidate |
| A read-only mode for the readiness script | The script creates throwaway copies of the installer's resources, so it needs Owner | In strict tenants running it is itself a change needing approval; a validate-only mode would run under Reader plus deployments/validate. | candidate |
| A documented read of Nerdio Manager's version | Neither the health page payload nor the REST API docs expose the version | Readiness checks can't confirm a feature's minimum version (8.0 for the current Copilot), so they report manual. | candidate |
| Read APIs or settings for feature state (Copilot, MCP, Azure runbooks, REST API) | These are toggled only in Settings in the console | Post-wizard checks can't tell whether a feature is on. | candidate |
| Publish the primary app's Graph permission list | Nerdio's permissions article references the list but doesn't include it | Reviewers in strict tenants need the exact list before consent; readiness checks can't compare against it. | candidate |
| A published schema for NmeReadinessOutput.json | The readiness script writes JSON with no documented format | The kit could import its results into one report instead of asking people to compare two. | candidate |
<!-- END GENERATED: api_asks -->

## Docs and packaging

<!-- BEGIN GENERATED: docs_packaging (edit the YAML, then run scripts/kb/build.py) -->
| Item | Evidence | Suggested fix | Status |
|---|---|---|---|
| Registry publishing plus a LICENSE | README installs from GitHub release zips via `dev_overrides`, and notes `terraform init` "can therefore fail". The repo has no license, so even hosting the binary in a private registry is legally unclear. | Add a license and publish to the public Registry. That makes Terraform Stacks and HCP Terraform runs straightforward (Stacks can use private-registry providers, but only with redistribution rights). Until then, document a `filesystem_mirror` install, which keeps `terraform init` and lock files working (see [restricted-networks.md](../terraform/restricted-networks.md#workaround-filesystem-mirror)). | candidate (draft ask with evidence prepared 2026-10-16, to raise at Nerdio's partner advisory board; not sent) |
| Version numbers disagree | The only GitHub release is `v0.0.1-preview.1`, but the README's snippets use `0.1.0` and `examples/main/main.tf` and `examples/provider/provider.tf` use `0.0.1`. | Make the README and examples match the published release. | candidate |
| README references missing CI | README's layout table lists `.github/workflows`, but the public repo has no `.github` folder. | Publish the workflows, or drop the row. | candidate |
| Linux and Windows amd64 builds only | README: "packages the provider for Linux amd64 and Windows amd64". | Add darwin/arm64 and linux/arm64 to the release matrix. | candidate |
| REST API enablement by tag | The documented manual method (client app tag `NMW_REST_API_CLIENT:<app-id>`, RestClient role, token version 2) is how the kit enables the API without the UI. Which app ID goes in the tag is ambiguous in Nerdio's article. *Unverified* until a live run. | Ask Nerdio to confirm the tag method is a supported replacement for the UI toggle, and document auth setup end to end. | candidate |
| Azure Government install and API endpoints | Nerdio's Gov article covers a Marketplace install with app-credential linking only, no managed-identity or split-identity installs, and no User Cost Attribution ([40495096260493](https://nmehelp.getnerdio.com/hc/en-us/articles/40495096260493)). It doesn't say whether `mainTemplate.json` works in Gov, which package API host Gov installs use, or which token audience the REST API expects there. | Document the Gov endpoints (package API, REST API scope and token authority) and whether the template path is supported in Gov. | candidate |
<!-- END GENERATED: docs_packaging -->

## Adding an entry

Add an entry to [upstream.yaml](upstream.yaml) with the gap, a link or quote as evidence, why it
matters, and `status: candidate`, then run `python3 scripts/kb/build.py` to regenerate the tables
above. When it's raised upstream, set `status: raised` and add the issue or PR as `link`.
