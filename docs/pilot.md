# First production pilot in a governed tenant

The first deployment the kit makes into a tenant that **stays up**: a work or customer
subscription governed by an intake or change process, with privileged roles held through PIM.
It follows the same path as the [dress rehearsal](dress-rehearsal.md), with the gates, rights and
rollback such a tenant expects.

**Status: not ready.** The pilot waits on three things, in this order:

1. The tenant's **intake approval** for this deployment ([phase 0](#phase-0-intake)).
2. A dress rehearsal that met its [exit criteria](dress-rehearsal.md#exit-criteria).
3. The [pilot decisions](#pilot-decisions) below, settled and written into the intake request.

This page holds no commands for the governed tenant. Each step names the rehearsal step it
repeats; run it only once the go/no-go list is all yes.

## Phase 0: intake

Nothing reaches the tenant before intake approves it: not the chat, not the pipeline bootstrap,
not a quota request. Never work around intake to save time, even for a step that's easy to undo.

What the intake request needs, all of it from this repository:

| Intake asks | Where it comes from |
|---|---|
| What gets deployed, per stage | The plan of each stage, from the rehearsal; [architecture.md](architecture.md) |
| Every right for people and identities, and how long | [Access for the pilot](#access-for-the-pilot), [access.md](access.md) |
| Standing identities and what they can do | The pipeline's plan and apply identities, Nerdio's web app identity and Entra app, the Automation identity |
| Data leaving the tenant | GitHub Actions (OIDC sign-in, masked plan summaries); Nerdio's package download; the setup chat's calls to the Claude API, only if the chat is in scope |
| Change window and duration | Elapsed times from the rehearsal log |
| Cost | App Service B3, SQL S1, NAT gateway, FSLogix share, session hosts at the planned scale |
| Rollback | [Rollback](#rollback) |
| Owner and approvers | You, plus the second reviewer the [decisions](#pilot-decisions) name |

### Is read-only `./nerdio preflight` allowed before approval?

It's the intake owner's call, so ask for it explicitly as the first, separate item: "read-only
discovery before the deployment request". The case for it:

- It only reads ([decision 0026](knowledge/decisions/0026-read-only-readiness-engine.md)): Reader
  on the subscription and your default directory read rights (Directory Readers for tenant-wide
  reads). It creates nothing in Azure or Entra, and rights it lacks show as `no-access`.
- Its report stays in your Cloud Shell home (`--save`, mode 600), masked by default. The
  standalone `nerdio-preflight.pyz` does the same without cloning the kit.
- It turns the intake request's guesses (quota, policy denies, address overlaps, existing DNS
  zones) into facts, which makes the request smaller and the approval faster.

What is **not** read-only and needs intake approval like any change: every `./nerdio fix`
(quota tickets, PIM activations it requests for you), `--probe url-check` (Run Command on a VM),
the pipeline bootstrap and the chat deploy. A Reader sign-in for the run, with privileged roles
left inactive, keeps preflight honest.

## Pilot decisions

Settle these before the intake request; each changes what you ask for.

| Decision | Recommendation | Why |
|---|---|---|
| Where the pipeline repository lives | A **private** copy in an organization the tenant's owner accepts, not the public kit repository | A public repository's Actions logs and plan comments are public, even masked, and its GitHub environments would tie the governed tenant to a public repository. The kit's own repository stays the upstream |
| Setup chat in the pilot | **No**; use the CLI and the pipeline for the pilot, and add the chat later as its own intake item | The chat is a standing app with outbound calls to the Claude API and its own rights; it isn't needed to deploy |
| Admin consent | **By hand** (`grant_admin_consent = false`, the two consent Graph roles left out of `access.apply_graph_roles`) | Those two are the most powerful Graph roles the kit uses; an Entra admin consents once per app instead |
| Resource locks | **On** (the `prod` default), with a lock role for the apply identity | The deployment stays up. See rehearsal log R2 |
| Approvers | **Two named reviewers** | A single maintainer approving their own run won't pass most change processes. See rehearsal log R4 |
| Kit environment name | `prod` | The workflows offer `sandbox`, `dev` and `prod`; `prod` turns on locks and production sizing |
| Engine | **Terraform** | The Bicep variant covers only the landing zone ([decision 0032](knowledge/decisions/0032-bicep-variant.md)) |
| Copilot | **Off** for the pilot | Optional and separable; turn it on later with `nerdio_ai` |
| Hardening (private endpoints) | Decide with intake; if on, plan the VNet runner | `disable_public_access` needs a route into the VNet for later applies ([deployment-runbook.md step 5](deployment-runbook.md#5-second-apply-hardening)) |
| Network | The hub, peering and DNS zones intake names | Preflight checks overlap, hub rights and existing privatelink zones |

## Go/no-go

All yes before the change window opens. Any no is a no-go.

- [ ] Intake approved this deployment, for this subscription, in this window.
- [ ] Read-only discovery approved and run; its report reviewed with no `fail` left.
- [ ] Dress rehearsal met its exit criteria on the current kit commit; the run log's breaks are
      fixed in `main` or have workarounds written into this page.
- [ ] The [pilot decisions](#pilot-decisions) are settled and match what intake approved.
- [ ] PIM eligibility confirmed for each role in [access](#access-for-the-pilot), including any
      that need an approver or a ticket number.
- [ ] Quota in place: App Service plan, VM family vCPUs at full scale, Azure OpenAI only if Copilot.
- [ ] Nerdio license and AVD user licenses confirmed (no command can check these).
- [ ] Both reviewers available in the window; the pipeline repository's ruleset is on.
- [ ] Rollback owner named, and the abort time agreed (when to stop and roll back rather than
      fix forward).
- [ ] Nothing about the tenant (IDs, domains, names) is in the repository, issues or chat.

## Access for the pilot

People activate roles through PIM for the step and let them expire. Identities keep their rights,
scoped as below; the full list with reasons is [access.md](access.md).

### PIM activations, in order

| Step | Role to activate | Scope | Who | Suggested length |
|---|---|---|---|---|
| Read-only discovery | None beyond **Reader** (and **Directory Readers** for tenant-wide reads) | Subscription; hub and DNS subscriptions if elsewhere | You | The run |
| Pipeline bootstrap, Azure part | **Owner**, or **Contributor** + **Role Based Access Control Administrator** limited to the roles in access.md | Subscription | Subscription admin | 2 hours |
| Pipeline bootstrap, Graph part | **Privileged Role Administrator** | Tenant | Privileged role admin (can be a different person) | 1 hour |
| Admin consent after the platform apply | **Privileged Role Administrator** or **Global Administrator** | Tenant | Entra admin | 1 hour |
| Nerdio wizard | Sign-in only (the wizard's own consent prompts need the consent role above) | Nerdio console | Nerdio admin | The wizard |
| Hub peering, if the hub is elsewhere | **Network Contributor** on the hub network | Hub subscription | Network owner | 1 hour |

`./nerdio fix roles` can activate eligible roles, but only once intake allows it; PIM settings
that need an approver or a ticket still need the portal.

### Standing identities

| Identity | Rights in the pilot | Notes |
|---|---|---|
| Pipeline plan identity | Reader on the subscription, Directory.Read.All, state storage | Pull request plans off (`github.allow_pr_plans = false`) |
| Pipeline apply identity | Contributor; Role Based Access Control Administrator limited to `apply_assignable_roles`; a lock-only custom role; Application.ReadWrite.All, Group.ReadWrite.All, Directory.Read.All | No consent roles. Only works after a reviewer approves |
| Nerdio web app (managed identity) | Contributor on Nerdio's groups, Reader and Backup Reader on the subscription, its own Key Vault roles | It is Nerdio |
| Nerdio Entra app | The permissions Nerdio documents, granted by the Entra admin | |
| Automation account | Website Contributor on the Nerdio web app | Nerdio's updates |

## Step order

Each step repeats the rehearsal step shown, against `prod`, after the go/no-go list. Stop at any
step whose result differs from the rehearsal, and decide with the rollback owner.

| # | Step | Rehearsal step | Gate |
|---|---|---|---|
| 1 | Pin the tenant as `prod` and write the answers (`environment = prod`, decisions above) | 1, 2 | Intake approved |
| 2 | Read-only preflight, saved and reviewed | 2 | Discovery approved |
| 3 | Pipeline bootstrap with the pilot's `access` settings, then the repository ruleset | 3 (without the chat) | PIM: bootstrap roles |
| 4 | Preflight from the pipeline | 5 | |
| 5 | Platform plan, both reviewers read it, approve the apply | 6 | Reviewer approval |
| 6 | Admin consent for Nerdio's apps | 3 (consent note) | PIM: consent role |
| 7 | Install check (`--stage post-install`) | 7 | |
| 8 | Nerdio wizard | 8 | |
| 9 | Config plan and apply | 9 | Reviewer approval |
| 10 | Verify (`--stage post-wizard`) | 10 | |
| 11 | Drift on for `prod` | 12 | |
| 12 | Hardening apply, if decided | deployment-runbook step 5 | Reviewer approval |
| 13 | Handover runbook (the `handover` skill) and the intake closeout | | |

Record each step's start, end and result in the change record, and any break in the rehearsal's
[run log](dress-rehearsal.md#run-log) marked as the pilot, without tenant details.

## Rollback

Decide before the window which of these is the abort point. Each pipeline rollback is a plan a
reviewer approves; nothing rolls back on its own.

| Failed at | Roll back by | Notes |
|---|---|---|
| Preflight or bootstrap plan | Nothing to undo | Fix and replan |
| Bootstrap apply | Destroy `00-pipeline` (rehearsal 14.5) | Removes the identities and GitHub environments |
| Platform apply, partway | Fix forward and apply again if the plan is small and understood; otherwise destroy stage `platform` | Locks are Terraform's own and go first in a destroy. A stateful replace is blocked unless `allow_replace` is ticked; never tick it in the pilot without the rollback owner |
| Install job or wizard | Rerun the Automation job; if Nerdio won't start, destroy stage `platform` | Nothing outside Nerdio's groups depends on it yet |
| Config apply | Revert the answers change and apply stage `config` again, or destroy stage `config` | Session hosts Nerdio built must go from Nerdio's console first |
| After go-live | Treat as a normal change: plan, review, apply | Drift issues show anything changed outside the pipeline |

Full removal is the rehearsal's teardown order (14.1, 14.2, 14.4 if the chat was deployed, 14.5),
with Key Vault purge protection in mind: a protected vault's name can't be reused until it
expires.

## After the pilot

- Turn off or narrow standing rights you don't need between deployments; nothing in the kit
  expires them yet ([access.md](access.md#not-covered-yet)).
- Feed the rehearsal and pilot logs back: known errors, preflight checks that would have caught a
  break, and access rows that were missing.
- Add the setup chat, Copilot or the Bicep variant as their own intake items, one at a time.
