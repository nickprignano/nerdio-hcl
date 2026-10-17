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
| Chat deploy (`./nerdio assistant`) | Subscription admin | Same as above, able to assign *Cognitive Services User*, *Key Vault Crypto Officer*, *Storage Blob Data Contributor* and *Storage Blob Data Reader* | **Application Administrator** or **Cloud Application Administrator** (the chat's sign-in app) | Once, and for chat updates |
| Admin consent, if the pipeline doesn't grant it (`grant_admin_consent = false`) | Entra admin | | **Privileged Role Administrator** or **Global Administrator** | Once per app |
| Approve an apply | A named GitHub reviewer | None | None | Per run, in GitHub |
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
| Setup chat (managed identity) | Chat deploy | **Cognitive Services User** on its Foundry resource; **Storage Blob Data Contributor** on the `answers` container; **Storage Blob Data Reader** on `plans`; **Key Vault Crypto Officer** on its own vault, which holds only the GitHub App key | None | While someone is chatting |
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
  keep the branch ruleset on (`github_settings.protect_branch`).
- **Private networking.** `enable_hardening` turns public access off; plans and applies then
  need a runner inside the network (chatbot-first inventory, step 19).

## Not covered yet

- **Sovereign clouds (such as Azure Government) and on-premises.** The kit targets Azure public
  cloud. Before using it elsewhere, check at least: the cloud's endpoints for every provider and
  for Cloud Shell, whether GitHub OIDC federation and Claude on Foundry are offered there, which
  Nerdio edition runs there, and the tenant's own approval rules. The Azure Government and Azure
  Local gaps found so far are in [stack-options.md](knowledge/stack-options.md); the apply
  identity's rights there also depend on Nerdio's app-credential linking in Government.
- **Removing rights after setup.** Nothing yet expires the apply identity's rights between
  deployments. Until it does, the approval gate is what protects them.
