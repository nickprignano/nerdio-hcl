# Deploy pipeline

Plan and apply the kit from GitHub Actions instead of pasting commands into Cloud Shell. Every
apply waits for a named reviewer to approve it in GitHub, and applies exactly the plan they saw.
Design and trade-offs: [decision 0016](knowledge/decisions/0016-gated-deploy-pipeline.md).

This is the first half of chat-driven deployment. Next, the setup chatbot gets tools to start a
plan and explain it back to you; it will be able to ask for an apply but never approve one.

## How it works

| Piece | What it does |
|---|---|
| `<env>-plan` GitHub environment | Any run from `main` can use it. Its identity is read-only: **Reader** on the subscription, **Directory.Read.All** in Graph, and the state storage |
| `<env>-apply` GitHub environment | Needs a reviewer's approval, from `main` only, with no admin bypass. Only then does GitHub issue the token its identity trusts |
| Two managed identities | One per environment, federated to exactly that environment with GitHub OIDC. No client secret exists anywhere |
| State storage account | Terraform state (container `tfstate`) and saved plans (container `plans`, deleted after 7 days). Entra sign-in only; shared keys are off |
| `.github/workflows/deploy.yml` | Plans a stage, lists the changes in the run summary, and saves the plan. If you ticked **apply**, the apply job waits for approval, checks the saved plan's hash and applies it |

Tenant, subscription and object IDs are stored as environment secrets so GitHub masks them, and
the workflow replaces any other GUID before printing. A public repository's Actions logs are
public, so the run summary shows resource addresses and actions, not values.

The apply identity is powerful: Contributor and Role Based Access Control Administrator on the
subscription, and the Graph roles stage 1 needs to create Nerdio's app registrations and grant
admin consent (`Application.ReadWrite.All`, `AppRoleAssignment.ReadWrite.All`,
`DelegatedPermissionGrant.ReadWrite.All`, `Group.ReadWrite.All`). That's what the approval gate
protects. If you'd rather grant consent yourself, set `grant_admin_consent = false` and trim
`apply_graph_roles` in `modules/deploy-pipeline`.

## Set it up (once, in Cloud Shell)

```bash
cd ~/nerdio-hcl
./nerdio init                        # if you haven't answered the setup questions yet
gh auth login                        # choose "Login with a web browser"; works on an iPad
./scripts/pipeline/bootstrap.sh      # review the plan, type yes
```

It reads your tenant and subscription from `az account show`, the repository from git, and you
as the approver (set `NME_REVIEWERS=login1,login2` for others). It publishes your `./nerdio`
answers to the plan environment, with `me` replaced by your object ID, and then moves its own
state into the new storage account.

You need Owner on the subscription (or Contributor plus Role Based Access Control
Administrator), Privileged Role Administrator or Global Administrator to grant the Graph roles,
and admin on the repository.

**Already applied from Cloud Shell?** Run `./scripts/pipeline/bootstrap.sh --adopt` to move the
01-platform and 02-nerdio-config state into the pipeline's storage. Don't run it while an apply is
in progress. The first pipeline plan will move Key Vault roles and app ownership from you to the
apply identity; add yourself to `entra_app.owner_object_ids` if you want to stay an app owner.

**Changed your answers?** `./scripts/pipeline/bootstrap.sh --answers-only` republishes them.

## Deploy

Actions > **deploy** > **Run workflow**: pick the environment and stage (platform first, then
config), and tick **apply** to apply after the plan. Read the plan in the run summary, then
approve the `<env>-apply` deployment (GitHub's mobile app works). Nerdio's first-run wizard
still runs in the browser between the stages, because Nerdio has no API for it yet.

## Limits, for now

- Only `nerdio_install = "terraform"` and `nme_secret_store = "key_vault"`. The Marketplace path
  needs a portal download, and OpenBao needs a network path from the runner.
- Key Vault and the state storage must accept connections from GitHub-hosted runners. With
  hardening that turns public access off, run the pipeline on a self-hosted runner in the VNet.
- Required reviewers on GitHub environments need a public repository or a paid GitHub plan.
- Not yet run against a live tenant.
