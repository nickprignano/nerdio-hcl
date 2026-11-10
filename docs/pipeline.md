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
| `<env>-plan` GitHub environment | Any run from `main` (and pull requests when `github.allow_pr_plans = true`) can use it. Its identity is read-only: **Reader** on the subscription, **Directory.Read.All** in Graph, and the state storage |
| `<env>-apply` GitHub environment | Needs a reviewer's approval, from `main` only, with no admin bypass. Only then does GitHub issue the token its identity trusts |
| Two managed identities | One per environment, federated to that environment with GitHub OIDC. No client secret exists anywhere |
| State storage account | Terraform state (container `tfstate`), saved plans and their change lists (container `plans`, deleted after 7 days) and the answers each environment plans from (container `answers`, one versioned blob per environment), protected by a `CanNotDelete` management lock. Entra sign-in only; shared keys are off |
| `.github/workflows/stage.yml` | The reusable job every pipeline workflow calls: signs in to one environment with OIDC, masks IDs and runs `scripts/pipeline/stage.sh` to plan, apply or unlock one stage ([decision 0033](knowledge/decisions/0033-ci-cd-reusable-stage-pr-plans-drift.md)) |
| `.github/workflows/drift.yml` | A daily read-only plan of each environment you list, with an `infra-drift` issue when Azure or Nerdio no longer match `main` ([Drift](#drift)) |
| `.github/workflows/deploy.yml` | Plans a stage, blocks accidental deletion or replacement of stateful Stage 1/2 resources unless `allow_replace` is ticked, lists the changes in the run summary, and saves the plan. If you ticked **apply** (or merged `config/answers/<env>.json` to `main`), the apply job waits for approval, checks the saved plan's hash and applies it |

Tenant, subscription and object IDs are stored as environment secrets so GitHub masks them, and
the workflow replaces any other GUID before printing. A public repository's Actions logs are
public, so the run summary shows resource addresses and actions, not values.

The apply identity is powerful: Contributor and Role Based Access Control Administrator on the
subscription, and the Graph roles stage 1 needs to create Nerdio's app registrations and grant
admin consent (`Application.ReadWrite.All`, `AppRoleAssignment.ReadWrite.All`,
`DelegatedPermissionGrant.ReadWrite.All`, `Group.ReadWrite.All`). That's what the approval gate
protects. Its Role Based Access Control Administrator role carries a condition, so it can only
assign the roles the kit uses (`apply_assignable_roles`), never Owner. To narrow it further, for
example to grant admin consent yourself, set `access` in `00-pipeline/terraform.tfvars`;
[access.md](access.md) lists every right and why the kit needs it.

## Set it up (once, in Cloud Shell)

```bash
cd ~/nerdio-hcl
./nerdio use trial                                         # once: remember this tenant and subscription as "trial"
gh auth login                                              # choose "Login with a web browser"; works on an iPad
./nerdio assistant --admin-group "AVD Admins" --pipeline   # or ./scripts/pipeline/bootstrap.sh --assistant "AVD Admins"
```

Pass `./scripts/pipeline/bootstrap.sh` without `--assistant` if you aren't deploying the setup
chatbot.

### Enter the tenant and subscription once

Nothing in the kit asks you to type a tenant or subscription ID. They come from your Cloud Shell
sign-in, and you pin them once per environment:

- **Cloud Shell** signs you in to the directory you open it in. Open
  `https://shell.azure.com/<tenant domain>` and add it to your home screen, one icon per tenant.
- **`./nerdio use <env>`** saves the signed-in tenant and subscription for that environment, after
  you type yes, to `~/.config/nerdio-hcl/profiles/<env>.json` in your Cloud Shell home folder. Only
  you can read it, and it's never in the repo. After that, `./nerdio` commands and the bootstrap
  check it: they switch to that subscription if you're signed in to the right tenant, and stop if
  you're not. `./nerdio use` lists your environments; `--forget` removes one. The bootstrap uses
  the last environment you picked, or `NME_ENV`, and saves it on its first run if you haven't.
- **The pipeline** stores them as GitHub environment variables when you bootstrap. The deploy
  workflow and the setup chat read them from there, so they never come up again.

They aren't secrets (sign-in is OIDC, with no stored password), but they identify the tenant, so
the kit keeps them out of the repo, the chat and shared output.

The repository settings the kit relies on live in [`github/`](../github/README.md), with their
own state and a daily drift check: the `kb-*` issue labels, a read-only default workflow token,
Actions allowed to open pull requests (for kb-feedback), and a ruleset on `main` so it only
changes through pull requests and can't be force-pushed or deleted. The apply environment trusts
`main`, so that ruleset is part of the gate: run `./github/settings.sh apply` right after the
bootstrap.

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

Actions > **deploy** > **Run workflow**: pick the environment and stage (`platform` first, then
`config`, `auto` to run `platform` then `config`, `assistant` to update the setup chatbot, or
`bicep` for the [Bicep variant](#bicep-variant)), and tick **apply** to apply after the plan.
By default, the plan job blocks any plan that deletes or replaces stateful Stage 1 (SQL, Key Vault,
FSLogix/ANF, VNet, Compute Gallery) or Stage 2 (`nme_workspace`, host pools, linked networks/RGs,
FSLogix profiles) resources when `destroy` is false; tick **allow_replace** only when a replacement
is intentional ([decision 0030](knowledge/decisions/0030-enterprise-guardrails-locks-and-gitops.md)).

### GitOps mode (`config/answers/<env>.json`)

Prefer Pull Requests for Day-2 changes? Commit a non-identifying answer file to
[`config/answers/<env>.json`](../config/answers/README.md) (containing region, workload, sizing and
Entra group display names, with zero GUIDs per [guardrail 4](guardrails.md)):

- Opening a pull request validates the file against `schema/parameters.json` and, when
  `github.allow_pr_plans = true` is set in `00-pipeline`, automatically runs a read-only
  `terraform plan` in `<env>-plan`.
- Merging to `main` runs `stage = auto`, planning and gating `platform` and `config` behind the
  `<env>-apply` reviewer approval and syncing the merged answers back to `answers/<env>.json`.

Stage **preflight** runs the read-only readiness check (`./nerdio preflight`) from the saved answers
as the plan identity, and never applies. Its checks of a person's roles come back as "manual",
because the apply identity holds those roles by design. Stage **verify** runs the same check after
Nerdio's wizard (`--stage post-wizard`), including the kit's own Terraform checks from the platform
state. Stages **fix-quota** and **fix-vcpu** preview an App Service quota support ticket or VM
family vCPU quota increase in the plan job and send `./nerdio fix quota` / `vcpu --yes` in the gated
`<env>-apply` job after a reviewer approves it. Read the plan in the run summary, then approve the
`<env>-apply` deployment (GitHub's mobile app works). Nerdio's first-run wizard still runs in the
browser between the stages, because Nerdio has no API for it yet.

### Plans on pull requests

With `github.allow_pr_plans = true` in `00-pipeline`, a pull request from a branch of this
repository that changes `modules/`, `environments/example/`, `bicep/`, `scripts/pipeline/` or
`schema/parameters.json` gets a read-only plan of the platform and config stages, posted as one
comment that each push updates. Turn it on by naming the environment to plan in the repository
variable `NERDIO_PR_PLAN_ENV` (`gh variable set NERDIO_PR_PLAN_ENV --body sandbox`); while it's
unset, code changes get no plan, so a repository without a pipeline isn't sent failing runs. A
pull request that changes `config/answers/<env>.json` plans that environment, as before. Nothing applies from a pull request, and merged code doesn't apply on its own either:
run **deploy** with apply ticked, and a reviewer approves it. Pull requests from forks are
skipped; GitHub gives them no OIDC token.

A pull request plan runs the branch's Terraform as the plan identity, which can read state and
the secrets in it. That's why it is off by default and limited to this repository's branches,
which only people with write access can push.

## Drift

`drift.yml` plans each environment every day at 05:17 UTC as the read-only plan identity and
saves nothing that could be applied. Turn it on with two repository variables (Settings >
Secrets and variables > Actions > Variables, or `gh variable set`):

```bash
gh variable set NERDIO_DRIFT_ENVS --body '["sandbox"]'
gh variable set NERDIO_DRIFT_STAGES --body '["platform","config"]'   # optional; this is the default
```

When a plan shows changes, it opens an issue titled `Drift: <env>`, labelled `infra-drift`, with
the masked change list. Later runs update it, and the first clean run closes it. A change means
one of three things: someone changed a resource outside the pipeline (the portal, a script),
someone changed Nerdio Manager's console (the `config` stage refreshes the `nerdio/nme`
resources), or `main` has code or answers that were never applied. To restore `main`, run
**deploy** with apply; to keep the outside change, change the code or answers to match. A plan
that would delete or replace a stateful resource is reported, not blocked, because nothing
applies from a drift run. Run it now from Actions > **drift** > **Run workflow**.

## Bicep variant

Stage **bicep** deploys the platform from the Bicep variant (decision 0032, in progress)
(`bicep/main.bicep`, with `bicep/environments/<env>/platform.bicepparam`) through the same gate:

1. **Plan** (plan identity): renders the answers like a Terraform plan, builds the template and
   parameters, and runs `az deployment sub what-if --validation-level ProviderNoRbac`. The
   compiled template, parameters and change list are saved with their SHA-256, like a Terraform plan.
2. **Apply** (after a reviewer approves): checks the hash, runs what-if again as the apply
   identity and stops if Azure would now change anything the reviewer didn't see. ARM has no
   saved plan that goes stale on its own, so this re-check stands in for Terraform's. Then it
   deploys exactly that template as the subscription deployment stack `nerdio-<prefix>-platform`
   (`detachAll`, no deny settings yet).
3. Run stage **config** afterwards as usual: it reads `nerdio_config_inputs` from the stack's
   outputs when there's no Terraform platform state.

Reader can't call what-if (it's an action, not a read), so set `access = { plan_bicep_whatif = true }`
in `00-pipeline` first: it gives the plan identity a custom role with only the what-if and
validate actions. What-if can list values it can't evaluate (`reference()`, secure values) as
changes, so the apply's re-check may ask you to plan again. Add `"bicep"` to
`NERDIO_DRIFT_STAGES` to drift-check the stack.

## Keeping the pipeline itself safe

- Every action in every workflow is pinned to a commit SHA, with the version in a comment.
  Dependabot (`.github/dependabot.yml`) opens a weekly pull request to bump them, and the
  setup chatbot's Python packages and base image; each goes through the normal checks.
- `validate.yml` lints every workflow with actionlint (checksum-verified) and builds and lints the
  Bicep variant when it's in the tree.
- Reusing the stage from another repository isn't supported: `stage.yml` checks out the calling
  repository and its GitHub environments, so fork or template this repository instead.

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
| `preflight.json`, `verify.json` | Each readiness check's status, detail and fix, IDs masked |
| `<stage>.json` | The plan's change list, and which values were adopted from Cloud Shell |
| `<stage>-apply.json` | The apply's result. After the platform stage it includes the names Nerdio's first-run wizard asks for: the console URL, the AVD network and the resource groups |
| either, on failure | The error and the last 30 lines of the log, IDs masked |

So the chat can explain a failure, and walk you through the wizard with exact names, without
anyone opening the run's log. None of it goes to the public run log.

## Limits, for now

- Requires `nme_secret_store = "key_vault"`. OpenBao needs a network path from the runner.
  For `nerdio_install = "marketplace"`, run the `platform` stage once after deploying Nerdio
  Manager from the Azure Marketplace (with `existing_entra_app_client_id` set if Nerdio's install
  script created `nerdio-nmw-app`) before running the `config` stage.
- Key Vault and the state storage must accept connections from GitHub-hosted runners until the
  VNet runner is enabled. With hardening that turns public access off (`enable_hardening = true`),
  set `enable_vnet_runner = true` and `vnet_runner` in `01-platform`, and set `github.runner_labels`
  (or pass `runner_labels` on `deploy.yml`) to `["self-hosted", "linux", "x64", "vnet"]`.
- Required reviewers on GitHub environments need a public repository or a paid GitHub plan.
- Not yet run against a live tenant, including the pull request plans, drift issues and Bicep
  stage from [decision 0033](knowledge/decisions/0033-ci-cd-reusable-stage-pr-plans-drift.md).
