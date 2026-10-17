# Deploy pipeline

Plan and apply the kit from GitHub Actions instead of pasting commands into Cloud Shell. Every
apply waits for a named reviewer to approve it in GitHub, and applies exactly the plan they saw.
Design and trade-offs: [decision 0016](knowledge/decisions/0016-gated-deploy-pipeline.md).

You can drive it from the Actions tab, or from the [setup chatbot](assistant.md): it saves your
answers, starts a plan and explains it back to you. The chatbot can ask for an apply but never
approve one ([Connect the chatbot](#connect-the-chatbot)).

## How it works

| Piece | What it does |
|---|---|
| `<env>-plan` GitHub environment | Any run from `main` can use it. Its identity is read-only: **Reader** on the subscription, **Directory.Read.All** in Graph, and the state storage |
| `<env>-apply` GitHub environment | Needs a reviewer's approval, from `main` only, with no admin bypass. Only then does GitHub issue the token its identity trusts |
| Two managed identities | One per environment, federated to exactly that environment with GitHub OIDC. No client secret exists anywhere |
| State storage account | Terraform state (container `tfstate`), saved plans and their change lists (container `plans`, deleted after 7 days) and the answers each environment plans from (container `answers`, one versioned blob per environment). Entra sign-in only; shared keys are off |
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
as the approver (set `NME_REVIEWERS=login1,login2` for others). It moves its own state into the
new storage account, then publishes your `./nerdio` answers there (`answers/<env>.json`), with
`me` replaced by your object ID.

You need Owner on the subscription (or Contributor plus Role Based Access Control
Administrator), Privileged Role Administrator or Global Administrator to grant the Graph roles,
and admin on the repository.

**Already applied from Cloud Shell?** Run `./scripts/pipeline/bootstrap.sh --adopt` to move the
01-platform and 02-nerdio-config state into the pipeline's storage. Don't run it while an apply is
in progress. The first pipeline plan will move Key Vault roles and app ownership from you to the
apply identity; add yourself to `entra_app.owner_object_ids` if you want to stay an app owner.

`--adopt` also carries over the variable values your Cloud Shell runs used (for example the
`sandbox.auto.tfvars` that `cloudshell-bootstrap.sh` wrote). A Cloud Shell run names things its
own way, so planning from your answers alone would replace the deployment. Terraform evaluates
those files and the script publishes the result as `answers/<env>.<stage>.adopted.tfvars.json`;
values of sensitive variables, and the tenant, subscription and deployer IDs, are left out. Each
pipeline plan lays them over the answers, and the plan summary lists them, so the chatbot can say
which values come from Cloud Shell. To go back to planning from answers only, delete that blob:

```bash
az storage blob delete --auth-mode login --account-name <state storage> --container-name answers \
  --name sandbox.platform.adopted.tfvars.json
```

**Changed your answers?** `./scripts/pipeline/bootstrap.sh --answers-only` publishes them again,
or save them from the chatbot. Earlier versions are kept as blob versions.

## Deploy

Actions > **deploy** > **Run workflow**: pick the environment and stage (platform first, then
config), and tick **apply** to apply after the plan. Stage **preflight** runs the read-only
readiness check (`./nerdio preflight`) from the saved answers as the plan identity, and never
applies. Its checks of a person's roles come back as "manual", because the apply identity holds
those roles by design. Read the plan in the run summary, then
approve the `<env>-apply` deployment (GitHub's mobile app works). Nerdio's first-run wizard
still runs in the browser between the stages, because Nerdio has no API for it yet.

## Connect the chatbot

The chatbot starts runs as a GitHub App that can only use Actions on this repository. Its
private key lives in Key Vault as a non-exportable, sign-only key: the bot asks Key Vault to sign
a ten-minute token and never sees the key. The bot's managed identity can write the `answers`
container, read the `plans` container and use the keys in its own Key Vault, which holds only
that key, and nothing else in Azure.

1. **Connect the chatbot** (Cloud Shell):

   ```bash
   ./nerdio assistant --admin-group "AVD Admins" --pipeline
   ```

   It prints a setup link, `https://<your chat>/setup/github`.
2. **Create the GitHub App** (in the browser, once): open that link and sign in. It sends GitHub
   a ready-made app definition (GitHub's [manifest flow](https://docs.github.com/en/apps/sharing-github-apps/registering-a-github-app-from-a-manifest)):
   private, no webhook, *Actions: read and write* and nothing else. Click **Create GitHub App**,
   then **Install** on this repository only. GitHub hands the new app's private key straight to
   the chatbot, which imports it into Key Vault; nobody downloads or pastes a `.pem`.

To replace the app, open `/setup/github?replace=true`, then delete the old app in GitHub.

Now ask the chatbot to deploy. It saves your answers and starts a platform plan, each only after
you say yes, then reads the plan back to you. When you're happy, it starts a run that asks to
apply, and you approve that run in GitHub.

A GitHub App can't be an environment reviewer, so the bot can't approve its own run. With
Actions write it could also re-run or cancel other workflow runs in this repository; the kit's
code only ever dispatches `deploy.yml`. To cut it off, suspend or uninstall the app in GitHub.

## What the chatbot can read back

Each run leaves its result in the `plans` container, under `<env>/<run id>-<attempt>/`:

| Blob | What's in it |
|---|---|
| `preflight.json` | Each readiness check's status, detail and fix, IDs masked |
| `<stage>.json` | The plan's change list, and which values were adopted from Cloud Shell |
| `<stage>-apply.json` | The apply's result. After the platform stage it includes the names Nerdio's first-run wizard asks for: the console URL, the AVD network and the resource groups |
| either, on failure | The error and the last 30 lines of the log, IDs masked |

So the chat can explain a failure, and walk you through the wizard with exact names, without
anyone opening the run's log. None of it goes to the public run log.

## Limits, for now

- Only `nerdio_install = "terraform"` and `nme_secret_store = "key_vault"`. The Marketplace path
  needs a portal download, and OpenBao needs a network path from the runner.
- Key Vault and the state storage must accept connections from GitHub-hosted runners. With
  hardening that turns public access off, run the pipeline on a self-hosted runner in the VNet.
- Required reviewers on GitHub environments need a public repository or a paid GitHub plan.
- Not yet run against a live tenant.
