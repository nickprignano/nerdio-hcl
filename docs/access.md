# Access: who and what needs which rights, and why

Every right the kit asks for is listed here, with its scope, when it's needed and how to take it
away again ([decision 0019](knowledge/decisions/0019-least-privilege-explicit-access.md)). Assume
the tenant has strict rules: privileged roles held only through PIM, change approval, and
reviewers who want a reason for each grant. If a right isn't on this page, the kit shouldn't need
it; treat that as a bug.

Two kinds of access:

- **People** run a one-time step in Cloud Shell. Their rights are needed only for that step, so
  activate them through PIM for the step and let them expire.
- **Identities** (managed identities and app registrations) do the work afterwards. Their rights
  are standing, so each one is scoped as tightly as the kit allows, and the powerful ones only
  work after a person approves a run in GitHub.

## People

| Step | Who | Azure | Entra | How long |
|---|---|---|---|---|
| Intake | The tenant's own process | | | Before anything else ([runbook](deployment-runbook.md)) |
| Pipeline bootstrap (`scripts/pipeline/bootstrap.sh`) | Subscription admin | **Owner**, or **Contributor** plus **Role Based Access Control Administrator** that can assign *Reader*, *Contributor*, *Role Based Access Control Administrator* and *Storage Blob Data Contributor* | **Privileged Role Administrator** (to grant the identities their Graph roles) | Once per environment |
| Chat deploy (`./nerdio assistant`) | Subscription admin | Same as above, able to assign *Key Vault Crypto Officer*, *Storage Blob Data Contributor*, *Storage Blob Data Reader* and, with Foundry, *Cognitive Services User* | **Application Administrator** or **Cloud Application Administrator** (the chat's sign-in app and, with the Claude API, its audience app) | Once, and for chat updates |
| Connect the chat to the Claude API (`./nerdio assistant --connect-claude`) | Anthropic organization admin | None beyond the chat deploy | None | Once. Signs in with `ant auth login --scope org:admin`; log out after. Or do it in the Claude Console (`--console`) |
| Admin consent, if the pipeline doesn't grant it (`grant_admin_consent = false`) | Entra admin | | **Privileged Role Administrator** or **Global Administrator** | Once per app |
| Readiness check (`./nerdio preflight`, or `nerdio-preflight.pyz` standalone) | Anyone planning or checking a deploy | **Reader** on the subscription, and on the hub network's and private DNS zones' subscriptions when they live elsewhere. Every default check only reads ([decision 0026](knowledge/decisions/0026-read-only-readiness-engine.md)) | Your own default user read rights; **Directory Readers** for tenant-wide reads. Rights it can't use give `no-access`, never a failure | Each run |
| Readiness check after the install (`--stage post-install` or `post-wizard`, pipeline stage **verify**) | Whoever checks Nerdio Manager | **Reader** on the subscription; **Key Vault Reader** on Nerdio's vault for certificate expiry (metadata only); **Security Reader** for the Defender check. Still read-only | **Directory Readers** for Nerdio's app registration, consent and role holders | Each run |
| Readiness check, Nerdio data tier (`--nerdio-data`) | A Nerdio admin, after the install | **Key Vault Secrets User** on the kit's secret store only: a standing right to read the REST client secret. Standalone needs none (the secret is in your own shell) | None; Nerdio's API checks the REST client's own role | Each run |
| Readiness probe (`--probe url-check`) | Whoever may run code on a session host, with change approval | **Virtual Machine Contributor** on that one VM (Run Command runs as SYSTEM) | None | Each run, after a typed yes |
| Approve an apply | A named GitHub reviewer | None | None | Per run, in GitHub |
| Apply GitHub settings (`./github/settings.sh apply`) | The repository owner | None | None. On GitHub: a fine-grained token for this repository only with *Administration: read and write*, *Issues: read and write* (labels) and *Metadata: read* | One day; revoke it after the apply ([github/](../github/README.md)) |
| Nerdio first-run wizard | Nerdio admin | None beyond what Nerdio asks for | Sign-in only | Once |

Portal note: when you give someone Owner or Role Based Access Control Administrator, Azure offers
a condition. Its recommended choice ("all roles except privileged administrator roles") blocks
the bootstrap, because the bootstrap gives the apply identity *Role Based Access Control
Administrator* (constrained, below). Use "only assign selected roles to selected principals" with
the roles in the table, or give the bootstrap admin an unconditioned role for the step and remove
it after.

## Identities

| Identity | Created by | Azure rights | Entra (Microsoft Graph) rights | Used when |
|---|---|---|---|---|
| Pipeline **plan** identity | Bootstrap | **Reader** on the subscription; the state storage | **Directory.Read.All** | Any plan or readiness check from `main` |
| Pipeline **apply** identity | Bootstrap | **Contributor** and **Role Based Access Control Administrator** on the subscription. Azure only lets it assign or remove the roles in `apply_assignable_roles` (a role assignment condition), so it can't grant Owner or widen its own access | **Application.ReadWrite.All**, **Group.ReadWrite.All**, **Directory.Read.All**, and by default **AppRoleAssignment.ReadWrite.All** and **DelegatedPermissionGrant.ReadWrite.All** so it can grant admin consent (drop both if you consent yourself, below) | Only after a reviewer approves the run in GitHub |
| Setup chat (managed identity) | Chat deploy | With Foundry, **Cognitive Services User** on its Foundry resource. With the pipeline, **Storage Blob Data Contributor** on the `answers` container, **Storage Blob Data Reader** on `plans` and **Key Vault Crypto Officer** on its own vault, which holds only the GitHub App key | None. With the Claude API it asks Entra for tokens for its audience app, which has no permissions of its own | While someone is chatting |
| Setup chat on the Claude side (service account) | `--connect-claude` | None | None. In Anthropic: *developer* organization role, *user* in its own workspace, and a federation rule that accepts only the chat's managed identity (object ID, tenant, audience) and mints 10-minute `workspace:inference` tokens | While someone is chatting |
| Settings reader (GitHub App) | The owner, once ([github/](../github/README.md)) | None | None. On GitHub: *Administration: read* (security settings, Dependabot, workflow token), *Issues: read* (labels, needed on private repositories) and *Metadata: read*, on this repository only. Its key is a secret of the `github-settings-read` environment, which only `main` can use | The daily drift plan |
| Chat's GitHub App | `/setup/github`, two clicks | None | None. On GitHub: *Actions: read and write* on this repository only | When the chat starts a plan |
| Nerdio web app (managed identity) | Platform stage | **Contributor** on the Nerdio resource group and the groups it manages; **Reader** and **Backup Reader** on the subscription; Key Vault roles on its own vault | None | Always: it is Nerdio |
| Nerdio Entra app | Platform stage | Key Vault roles on Nerdio's vault | The delegated and application permissions Nerdio documents for its install (`modules/nerdio-identity`), granted by admin consent | Always: it is Nerdio |
| Automation account (managed identity) | Platform stage | **Website Contributor** on the Nerdio web app | None | Nerdio's app updates |

## Making it stricter

These are supported switches, not forks of the kit. Set them in `00-pipeline/terraform.tfvars`
(`access = { ... }`) or the stage's own variables.

- **Grant admin consent yourself.** Set `grant_admin_consent = false` and leave
  *AppRoleAssignment.ReadWrite.All* and *DelegatedPermissionGrant.ReadWrite.All* out of
  `access.apply_graph_roles`. Those two are the most powerful Graph roles the kit uses: an
  identity holding them could grant itself more. An Entra admin then consents once per app.
- **Narrow what the apply identity can assign.** `access.apply_assignable_roles` lists the roles;
  remove any for features you don't use (for example the FSLogix SMB roles).
- **Use your own custom roles.** Put their names in `access.apply_roles` instead of Contributor;
  keep `apply_assignable_roles` in step with what your stages assign.
- **Split the bootstrap.** The Azure part needs a subscription admin; the Graph roles need a
  Privileged Role Administrator. They can be different people, each activating their role
  through PIM for the step.
- **Keep the approval gate tight.** Name specific reviewers (`NME_REVIEWERS`), not a team, and
  keep the branch ruleset on (`ruleset.enabled` in `github/main.tf`).
- **Private networking.** `enable_hardening` turns public access off; enable `enable_vnet_runner`
  and `modules/vnet-runner` in `01-platform` (`github.runner_labels = ["self-hosted", "linux", "x64", "vnet"]`
  in `00-pipeline`) so plans and applies run inside the AVD spoke VNet ([decision 0030](knowledge/decisions/0030-enterprise-guardrails-locks-and-gitops.md)).
- **Resource locks (`CanNotDelete`).** `enable_resource_locks` defaults to `true` for `prod` in
  `01-platform` (and `enable_resource_lock = true` on `00-pipeline`), locking SQL, Key Vaults,
  FSLogix/ANF storage and state storage against accidental deletion. Creating or removing
  `azurerm_management_lock` resources requires `Microsoft.Authorization/locks/*` (included in
  `Owner` and `User Access Administrator`, or add a custom lock role to `access.apply_roles`).

## Not covered yet

- **Sovereign clouds (such as Azure Government) and on-premises.** The kit targets Azure public
  cloud. Before using it elsewhere, check at least: the cloud's endpoints for every provider and
  for Cloud Shell, whether GitHub OIDC federation, Claude on Foundry and the Claude API's federation
  with that cloud's Entra issuer are offered there, which
  Nerdio edition runs there, and the tenant's own approval rules. The Azure Government and Azure
  Local gaps found so far are in [stack-options.md](knowledge/stack-options.md); the apply
  identity's rights there also depend on Nerdio's app-credential linking in Government.
- **Removing rights after setup.** Nothing yet expires the apply identity's rights between
  deployments. Until it does, the approval gate is what protects them.
