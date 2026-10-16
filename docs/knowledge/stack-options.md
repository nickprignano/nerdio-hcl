# Roadmap: turnkey, maximum-automation Nerdio deployment

Which manual steps can be automated, how a user drives the kit, which tools in the HashiCorp,
IBM and Microsoft stacks are worth adding, and what Nerdio would need to change. Upstream asks are
tracked with evidence in [nerdio/upstream-contributions.md](nerdio/upstream-contributions.md).

Revised 2026-10-16. **Goal:** automate everything that can and should be automated, and
wrap it in a turnkey experience, copy-paste, button or chat, so a community user does as little
heavy lifting as possible. Every item is judged on two tests: does it remove a manual step, and
does it make the kit easier to pick up? Claims were red-teamed against primary sources. Nothing here is built yet.

## The experience

One engine, three front doors. All three run the same Terraform, Packer and scripts, so there's one
thing to maintain and test.

**The engine:** a single `nerdio` entry point (a Makefile or a small script) with `preflight`,
`bootstrap`, `deploy`, `image`, `check` and `destroy` commands. Every front door calls these.

**Front door 1, copy-paste:** a [GitHub template repo](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template)
plus a dev container, so Codespaces or VS Code opens with Terraform, Packer, az, pwsh, Playwright
and the `nme` provider already installed. The user runs `./nerdio bootstrap`, answers a few prompts,
and runs `./nerdio deploy`.

**Front door 2, button:** GitHub Actions workflows with `workflow_dispatch` input forms, so each
operation is a form plus a Run button in the Actions tab:
- **Deploy:** environment name, region, directory type, host pool size.
- **Build image:** runs Packer and points the host pools at the new version.
- **Roll out image:** pick a host pool and a schedule.
- **Day-2 actions:** reimage, drain or run a script, through Nerdio's API.
- **Check:** health and the end-user launch test.
- **Destroy.**

Protected environments add an approval click before anything touches production.

**Front door 3, chat (the primary path):** see "Guided setup by chat" below. Chat leads the user
through the whole setup and then hands off to the engine and the buttons. It never replaces them.

**The one step that can't be removed: bootstrap.** Someone with Owner and Global Admin rights has to
create the deployment identity once. `./nerdio bootstrap` does this in a single run:
- Sign in with az.
- Run preflight checks: roles, resource provider registration, vCPU quota, region support.
- Create the state storage.
- Create the GitHub OIDC federated credential and an Entra app with the least-privilege roles.
- Write the repo secrets and variables with `gh`.

After that, everything is a button or a chat. There's no Azure "Deploy to Azure" button for
Terraform, so this script is the copy-paste entry. Cloud Shell can run it.

**Turnkey defaults:** a guided config generator writes `terraform.tfvars` from a few questions, and
an "opinionated defaults" profile covers the rest (Entra-joined, one pooled host pool, FSLogix on
Azure Files, the Packer image). Advanced users edit tfvars directly.

**HCP Terraform no-code modules** would also give a button UX inside HCP Terraform. *Not verified:*
which paid tier includes them, so treat this as optional. GitHub Actions is the free default.

## Guided setup by chat (white-glove)

The assistant is the concierge. It gathers the parameters, gets the user ready, runs or triggers the
engine, and walks them through everything before and after the deployment. The engine underneath stays
deterministic and scriptable, so the kit still works without AI, and every change remains reviewable code.

**Phases the assistant leads:**
1. **Discover:** ask about the goal in plain language: users, use cases, regions, identity model
   (Entra-joined, AD DS or Entra DS), GPU or not, budget, compliance needs. Then recommend a
   profile from the opinionated defaults and explain the trade-offs.
2. **Prepare:** check readiness and explain the gaps:
   - Roles: Owner on the subscription; Global Admin, or Privileged Role Admin plus Cloud App Admin.
   - Licensing: a Nerdio license (separate Marketplace offer), and AVD user eligibility (M365 E3/E5,
     Business Premium and similar; *verify the current list*).
   - Quota, resource provider registration and region support.
   - Network reachability to domain controllers for AD DS.
   It runs `./nerdio preflight` and translates failures into next steps.
3. **Configure:** fill in the parameters by interview, then write `terraform.tfvars` and show it for
   review. The questions come from one machine-readable parameter schema (names, descriptions,
   defaults, validation, which phase needs each one), so chat, the CLI wizard and the Actions
   forms all ask the same things.
4. **Bootstrap:** walk the admin through the one copy-paste step. The admin signs in and runs it
   themselves, and the assistant explains what it creates and checks the result.
5. **Deploy:** open the PR with the config, show `terraform plan` in plain language ("this creates
   23 resources, costs about $X/month"), and only start the deploy workflow after an explicit yes.
   It narrates progress and explains failures with the fix.
6. **Wizard steps:** either run the optional Playwright bridge, or give click-by-click guidance
   for the directory profile and registration screens, then confirm they're done through the API.
7. **Verify:** run the post-deploy checks, then lead the user through a first sign-in as a test
   user and interpret the results.
8. **Handover:** produce a short, environment-specific runbook covering what was built, where it
   is, how to add users and host pools, how to roll out a new image, cost levers, and the
   day-2 buttons and chat commands. It's written locally and never committed if it holds tenant details.

**How it's built:**
- `CLAUDE.md` plus skills in the repo (`.claude/skills/`: setup, deploy, image, troubleshoot,
  handover) that encode the phases above, so any user of Claude Code (terminal, desktop or web)
  gets the same guided flow.
- The parameter schema is the single source of truth. The skills read it, and so do
  `./nerdio init` (a plain CLI wizard for users without AI) and the workflow forms.
- MCP for context and actions: HashiCorp's Terraform MCP server for docs, and a Nerdio MCP server
  that's read-only by default for live state.
- MCP works with other clients too, but the skills are written for Claude Code first.

**Guardrails:**
- **Secrets never pass through the chat.** Secrets are entered into `az`, `gh` or Key Vault directly.
  The assistant only sees names and IDs, and generated tfvars stay gitignored (no-leak rule).
- **No apply without consent:** a plan summary and an explicit yes come first, and production
  environments also need the Actions approval click.
- **Every change goes through a PR,** so the chat can't drift from the code.
- **Token use is limited to the chat layer.** The engine, workflows, curator and Playwright use
  no model tokens.
- **Must test:** whether the interview reliably produces a valid config. Validate it with
  `terraform validate` plus schema checks before any plan.



| Manual step today | Can we automate it? | How | What Nerdio would need to change |
|---|---|---|---|
| Export the Marketplace template | **Yes** | Deploy Nerdio's own `Get-Nerdio/NMW` `templates/mainTemplate.json` (updated 2026-10-02) pinned to a commit, instead of a portal export. It's a solution template, so there are no Marketplace terms to accept (inferred: there's no plan, and licensing is a separate offer). | Declare that template a supported deploy path, with versioned releases. |
| Install script (Cloud Shell, or `deploy-az.ps1` run locally) | **Partly** | Do its work in Terraform. The kit already builds the Entra app. Still needed: the App Service settings, Key Vault secrets and SQL user the script writes, plus deploying the app code from Nerdio's package API (`/api/package` then `/{ver}/link`, which Nerdio's own update runbook uses). MB-External/NME-Terraform shows this works end to end. | Publish the script at a versioned URL, or document what it writes. Support running it as a service principal. Make the package API a supported path. |
| Admin consent (both prompts) | **Yes, already in the kit** | `grant_admin_consent = true` uses delegated grants and app role assignments (`modules/nerdio-identity`). *Inferred:* the wizard's second consent covers the same permission list; the first live run needs to confirm it. | None. |
| Wizard: network and host pool resource group | **Yes, already in the kit** | `nme_linked_network` and `nme_linked_resource_group` in stage 2. | None. |
| Wizard: directory profile (Entra-joined, AD DS or Entra DS) | **No API; optional Playwright bridge** | The API only has `GET /api/v1/ad/config`, with no create. Until that changes, an optional Playwright script can click through this step (see below). | Add an API (and a provider resource) to create directory profiles. |
| Wizard: registration and first-run state | **No API; optional Playwright bridge** | It's UI only, with no API. The same Playwright script covers it. | Add an API or setting to finish first-run setup. |
| Enable the REST API | **Yes, already in the kit** | The documented manual method: the client app tag `NMW_REST_API_CLIENT:<app id>`, the RestClient role and token version 2. `modules/nerdio-identity/rest_api.tf` does this. Nerdio says to wait a few minutes before using it. | Confirm the tag method is a supported replacement for the UI toggle. |
| Hand the secret from stage 1 to stage 2 | **Yes** | See Vault below. | None. |
| Install the `nme` provider (dev_overrides script) | **Partly** | Host it in an HCP Terraform private registry, or keep the install script. The repo has no LICENSE, so redistributing the binary is unclear. | Publish to the public Registry and add a license. |
| Import the Packer image into Nerdio | **Likely yes, untested** | Correction: the API *can* see gallery images. `GET /api/v1/image?imageType=ComputeGalleryImage` lists them, and `create-from-library` takes any `sourceImageId` from that list. The host pool `image` format for a gallery image isn't documented, and the provider example only shows Marketplace format. | Add an `nme_image` data source and a desktop image resource to the provider; desktop images aren't in its coverage matrix at all. |

**Result:** about 7 of the 10 steps can be removed by building on our side. The other two, the
directory profile and registration/first-run state, need Nerdio to add APIs. Until then, an
optional Playwright script can bridge them. Everything else is a supported-path ask rather than a
hard blocker.

## Optional bridge: Playwright for the two wizard steps

This is a stopgap, not the fix. The real fix is still the API request to Nerdio (upstream asks 1 and 2).

- **What it does:** a Playwright script in the repo signs in to the Nerdio console and completes
  the directory profile and first-run registration steps. It runs once per install, after
  stage 1 and before stage 2. Clicking through is unattended, but the run is still started by hand.
- **Why Playwright, not a computer-use agent:** it does the same thing every run, the community can
  review it in the repo, and it runs in CI with no model tokens.
- **Off by default:** it's opt-in (for example `enable_wizard_automation = false`). Without it, the
  runbook keeps the two manual steps.
- **It breaks when Nerdio changes the wizard.** Use role- and label-based locators, not CSS paths.
  Pin the script to the Nerdio versions it was tested against. Fail loudly with a screenshot, so a
  broken run falls back to the manual steps instead of leaving a half-finished install.
- **Sign-in is the hard part, and it can't touch the repo (no-leak rule).** The wizard needs an
  interactive Entra admin sign-in; a service principal can't use the UI. The options:
  - A saved Playwright session (`storageState`) captured by hand on a trusted machine and passed
    in at run time. It lives in Key Vault or a CI secret, never in the repo or logs, and expires quickly.
  - A dedicated break-glass admin account, scoped by Conditional Access to the runner.
    Most tenants require MFA, and nobody should weaken it for this.
  - Never: credentials in tfvars, plain env files, or committed traces.
  CI artifacts (screenshots, traces) can show tenant names and emails. Keep them private, or turn them off.
- **Where it runs:** a local one-shot command, or a manual (`workflow_dispatch`) GitHub Actions job
  using a protected environment that holds the session secret. It doesn't run on every push.
- **Must test live:** the selectors against the current wizard, and whether Nerdio's terms allow
  scripted UI use. If there's doubt, ask Nerdio along with the API request.

## Post-deployment checks with Playwright

These run after stage 2 and prove the deployment works the way a person would see it. They come in
three layers, and each layer uses the cheapest tool that can prove its point.

1. **API checks first (no browser).** Use Nerdio's REST API and Azure to confirm that the
   workspace, host pools, FSLogix and auto-scale profiles, and linked network exist and match the
   tfvars. `terraform test` or a short script can do this with the same REST client app, so no admin
   browser session is needed. This is most of the coverage.
2. **Host and job health via API (no browser).** Use Nerdio's `GET .../hostpool/{...}/host`,
   `/session`, `/auto-scale` and `/job/{id}` endpoints, and `/deployment/current` for the installed
   version. Use Azure's AVD session host status and built-in health checks (domain join, FSLogix,
   agent, stack) through ARM. Together they prove hosts were built and are healthy. An optional
   Playwright console screenshot is the only part left in the browser, and only as visual evidence.
3. **End-user launch test (Playwright, test user).** Sign in to the Windows App web client
   (`windows.cloud.microsoft`) as a dedicated test user and check that the workspace shows the
   desktop. Optionally, launch a session and wait for the desktop to render. This is the only check
   that proves an end user can connect: Conditional Access, assignment, FSLogix sign-in and the
   session host image together. Nothing in the Nerdio or Azure APIs starts a user session, so
   this is the one check that needs a browser. Once a test sign-in has happened, Azure Monitor's
   `WVDConnections` and `WVDErrors` logs can confirm it with a query instead of a screenshot.

**Settings with no API.** If some post-deploy setting turns out to be UI-only, it gets its own small
Playwright step under the same rules as the wizard bridge: opt-in, pinned to the Nerdio versions it
was tested on, and listed as an upstream API ask. *Inferred:* most of these already have APIs
(notifications, RBAC assignments, portal branding are all in the spec), so check `api.json` before
scripting any UI.

**Trade-offs and rules:**
- **The test user** has an AVD assignment and nothing else. Its sign-in comes from a saved session
  or a Conditional Access-scoped account, kept in Key Vault or a CI secret, never in the repo.
  MFA stays on; the session is captured by hand.
- **Cost:** launching a session starts a session host. Run it on demand or nightly in a sandbox,
  not on every push, and let auto-scale shut the host down afterwards.
- **No leaks:** screenshots and traces show tenant names, UPNs and host names. Keep CI artifacts
  private and short-lived, or turn on traces only when a run fails.
- **Brittleness:** the Microsoft web client and the Nerdio console both change without notice. Use
  role- and label-based locators, report failures as "UI check failed" separately from "deployment
  failed", and never block a deploy on layer 2 or layer 3 alone.
- **Where it runs:** the same manual or scheduled GitHub Actions job as the wizard bridge, in a
  protected environment. No model tokens.

## Filling the provider gaps (staying in Terraform)

There's no Ansible: Terraform owns desired state, and Nerdio's own auto-scale, schedules and
scripted actions own runtime work. Where `nerdio/nme` has no resource:
- **Nerdio API objects with full create, read, update and delete:** app groups, secure variables,
  notifications, shell apps and RBAC assignments. Use the generic `Mastercard/restapi` provider
  (Apache-2.0; supports OAuth client credentials and per-object paths and methods; checked in its docs, not
  tested). Each one is a stopgap and an upstream contribution candidate.
- **One-off operations** (reimage, drain, power, run script, log off): today these are Actions
  workflows calling the REST API. Long term they'd be Terraform actions (1.14+) in `nerdio/nme`, as an upstream ask.
- **Entra and Intune gaps:** use `msgraph`'s generic resource.
- **Can't be fully declarative:** host pool reimage and script schedules (the API has create and
  update, no delete), app attach images (no delete), and the directory profile and first-run steps
  (no API; Playwright bridge).

## Corrections from the red team

1. **Nerdio post-processor:** an earlier claim was wrong. The API does see Compute Gallery images.
   The right bridge is still not a Packer plugin; it's an `nme_image` data source (an upstream
   contribution) or Packer's built-in `manifest` and `shell-local` post-processors calling the API.
2. **Vault workload identity federation** is **Vault Enterprise only**, added in 1.17, not 1.15.
   Community Vault on Azure uses a managed identity or a client secret.
3. **Vault minting secrets on the existing REST client app** works (`application_object_id`), but
   Vault's own identity then needs Graph `Application.ReadWrite.All`, which is a high privilege. The
   ephemeral resource revokes the secret when the run ends. That's fine because the `nme` provider
   only needs it during the run, so no long-lived REST secret would exist at all.
4. **Terraform Stacks isn't blocked.** It's on HCP Terraform (all plans, including Free up to 500
   resources) and Terraform Enterprise 2.0. Stacks can use providers from the private registry, so
   `nme` could be hosted there, but the missing LICENSE makes that legally unclear. It's also only
   worth doing once the steps between stages are automated.
5. **HCP Packer has no free tier anymore** (paid, $500 trial credit). Pin the gallery version in
   Terraform as the free default, and keep HCP Packer optional.
6. **Boundary RDP credential injection** is Enterprise/HCP only (GA 0.21) and doesn't support Entra
   ID sign-in. Drop it from the roadmap; Azure Bastion covers this.
7. **azuread can't keep secrets out of state:** `azuread_application_password` always stores the
   value, and azuread 3.x has no write-only arguments. Vault (item 3) or Key Vault `value_wo` are
   the ways around it.
8. **Ansible:** it *can* reach Nerdio-built hosts through the `azure_rm` inventory by tag. The real
   reason to prefer Nerdio scripted actions is that autoscale keeps creating new hosts. The
   open-source `ansible/ansible` Terraform provider exists; the `ansible/aap` provider and its actions need AAP.
9. **microsoft365 community provider** is at v1.4.0, not pre-1.0, but it's effectively maintained by
   one person. **msgraph** is still a preview (v0.6.0).
10. **Vault Radar's CLI** needs HCP credentials, so it isn't a free tool. Gitleaks plus GitHub
    secret scanning (free on public repos) covers the repo.
11. **Licensing:** the BUSL licensor is now IBM. Each release becomes MPL-2.0 after four years.
    OpenBao has an Azure secrets engine as an external plugin.

## Tool verdicts

| Tool | Verdict | Why |
|---|---|---|
| Vault (Community) or OpenBao | Build | Removes the manual secret hand-off between stages. Workload identity federation for the Azure engine is Enterprise only. |
| Packer | Already in the kit | Pin the gallery image version in Terraform. |
| HCP Packer | Optional only | Paid, no free tier. |
| Ansible | Dropped ([decision 0006](decisions/0006-no-ansible.md)) | Terraform owns desired state; Nerdio auto-scale, schedules and scripted actions own runtime work. |
| azuread | Already in the kit | Covers apps, groups and Conditional Access; stores client secrets in state. |
| msgraph (preview v0.6.0) | For Graph gaps azuread doesn't cover | Official but preview. |
| microsoft365 community provider (v1.4.0) | Optional Intune module, later | Purpose-built resources, but effectively one maintainer. |
| GitHub Actions `workflow_dispatch` | The button UX ([decision 0007](decisions/0007-button-ux.md)) | Free, form inputs, runs the same engine. |
| HCP Terraform no-code modules | Optional | Tier not verified. |
| Terraform MCP server (HashiCorp) | Chat front door | Official; pairs with a Nerdio MCP server we'd build. |
| Terraform Stacks | Later | Available on all HCP Terraform plans and TFE 2.0; worth it once the steps between stages are automated and `nme` has a license. |
| Boundary | Dropped | RDP credential injection is Enterprise/HCP only and has no Entra sign-in; Azure Bastion covers this. |
| Turbonomic, Cloudability, Instana | Document only | Turbonomic conflicts with Nerdio auto-scale; Cloudability only needs consistent tags; Instana has no AVD sensor. |
| Vault Radar | Dropped | Needs HCP credentials; gitleaks plus GitHub secret scanning cover the repo. |

## Build order

**We build (no Nerdio change needed):**
1. **Single-apply install.** Swap the portal export for the pinned `mainTemplate.json`, add the
   App Service settings, Key Vault secrets and SQL bootstrap the script writes, and deploy the code
   from the package API. This is the biggest win: it removes the export and the install script.
2. **Secret hand-off without a manual export.** Vault mints a short-lived REST client secret per run,
   or Community Vault/Key Vault stores it with write-only and ephemeral resources.
3. **Image link.** Look up gallery images through the API and confirm the host pool `image` format
   in a live sandbox run.
4. **Pipeline.** Run the stages in order in GitHub Actions with OIDC. Move to Stacks later if the
   provider gets a license.
5. **Optional Playwright bridge** for the directory profile and first-run steps, opt-in and
   removed once Nerdio ships APIs for them.
6. **Post-deploy checks:** Terraform `check` blocks and `terraform test` calling the Nerdio REST and
   Azure APIs, plus one Playwright end-user launch test through the Windows App web client.
7. **Experience layer:** the `nerdio` entry point, `bootstrap` with preflight checks, the dev container,
   and the Actions workflow forms. The engine comes first, then the button forms.
8. **Gap fillers:** restapi-provider resources for app groups and the other uncovered objects.
9. **Guided chat setup:** the parameter schema first (shared with the CLI wizard and the forms),
   then `CLAUDE.md` and the setup, deploy, troubleshoot and handover skills, then the read-only Nerdio MCP server.

Suggested sequence: 1 → 4 → 7 (bootstrap and engine) gives a working one-command deploy; the
parameter schema and setup skill (9) come next so the guided flow wraps it early. 2, 3, 5, 6 and 8
harden it, and the MCP server comes last.

**Nerdio changes (upstream asks, in priority order):**
1. A directory profile create API and resource. This is the hard blocker.
2. A first-run and registration completion API.
3. A supported install path: versioned template and artifacts, a non-interactive install, and a documented package API.
4. Registry publishing plus a LICENSE.
5. Desktop image and image catalog resources in the provider.

**Dropped or documented only:** Boundary, Turbonomic, Cloudability, Instana, Vault Radar and HCP
Packer (optional only).

## Must test live before relying on it
- Whether a host pool `image` accepts a Compute Gallery image ID.
- Whether the Terraform grants match the wizard's second consent.
- Whether tag-based REST API enablement works without ever opening the UI.
- Whether the package API and settings approach (MB-External style) survives Nerdio's self-update.
- Whether the Playwright selectors work on the current wizard, and how long a saved session stays valid.
- Whether the Windows App web client can be driven headless to a rendered desktop, and how long that takes.

## Sources
- Nerdio OpenAPI spec: `internal/client/api.json` in Get-Nerdio/NME-Terraform-Provider (commit 65e547f, 2026-09-21)
- Nerdio template: github.com/Get-Nerdio/NMW `templates/mainTemplate.json`; update runbook `scripted-actions/azure-runbooks/Update Nerdio Manager.ps1`
- Nerdio help: Deploy NME (28419266386189), Advanced installation methods (26124326251405), Create Entra ID application (26124326326669), REST API manual configuration (27422824784269) at nmehelp.getnerdio.com
- Community: github.com/MB-External/NME-Terraform, github.com/oWretch/Nerdio-Terraform, github.com/roanp/NerdioTerraform
- Vault Azure engine: https://developer.hashicorp.com/vault/docs/secrets/azure (WIF badge: Vault Enterprise)
- Ephemeral resources: https://developer.hashicorp.com/terraform/language/block/ephemeral ; terraform-provider-vault CHANGELOG (5.0.0, 5.6.0)
- Stacks: https://developer.hashicorp.com/terraform/language/stacks ; https://developer.hashicorp.com/terraform/cloud-docs/registry/publish-providers
- HCP Packer tiers: https://developer.hashicorp.com/hcp/docs/packer/manage-registry ; https://www.ibm.com/products/hashicorp/pricing
- Boundary RDP: https://developer.hashicorp.com/boundary/docs/rdp-compatibility
- Ansible: github.com/ansible-collections/azure ; github.com/ansible/terraform-provider-ansible ; github.com/ansible/terraform-provider-aap
- IBM: ibm.com/products/turbonomic/pricing ; automation-management.ideas.ibm.com/ideas/TURBO-I-899 ; ibm.com/docs/en/SSE1JP5/src/pages/ecosystem/index.html
- Microsoft: github.com/microsoft/terraform-provider-msgraph ; github.com/deploymenttheory/terraform-provider-microsoft365

_Last reviewed: 2026-10-16_
