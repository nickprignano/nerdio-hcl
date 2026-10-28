---
status: accepted
date: 2026-10-28
decision-makers: [maintainers]
---

# 0030. End-to-end VNet runner, destructive-change guardrails, resource locks and GitOps answers

## Context and Problem Statement

Hardened enterprise deployments (`enable_hardening = true`, `disable_public_access = true`) close
public network access on Nerdio's Key Vault, SQL Server, and storage accounts, which blocks
GitHub-hosted runners (`ubuntu-latest`) from reaching state or secrets. In addition, early versions
of the `nerdio/nme` 0.x provider replace workspaces and linked networks when modified, stateful
production resources need protection against accidental deletion, static IaC scanning is expected in
enterprise CI, and platform teams want PR-driven GitOps alongside the setup chatbot without violating
Guardrail 4 (no tenant, subscription, or object IDs in the repository). How should the kit integrate
these four enterprise controls cleanly?

## Considered Options

- Keep `modules/vnet-runner` standalone, rely solely on manual reviewer inspection of plans, and
  keep `workflow_dispatch` as the only pipeline trigger
- Wire `modules/vnet-runner` end-to-end with a `/27` Consumption Workload Profile subnet and dynamic
  `runs-on` labels, enforce destructive-change guardrails in `stage.sh`, add `CanNotDelete` resource
  locks plus Trivy IaC scanning, and support tracked non-identifying `config/answers/<env>.json`
  GitOps workflows
- Require a separate private repository with committed `.tfvars` files for enterprise deployments

## Decision Outcome

Chosen option: "Wire `modules/vnet-runner` end-to-end with a `/27` Consumption Workload Profile
subnet and dynamic `runs-on` labels, enforce destructive-change guardrails in `stage.sh`, add
`CanNotDelete` resource locks plus Trivy IaC scanning, and support tracked non-identifying
`config/answers/<env>.json` GitOps workflows", because it preserves every public-repo guardrail while
giving enterprise teams private VNet execution, automated blast-radius protection, and PR-driven
day-2 change management.

- **End-to-end VNet runner (`modules/vnet-runner`, `modules/network`, `01-platform`, `00-pipeline`, `deploy.yml`):**
  - `modules/network` carves an optional `snet-vnet-runner` (`/27`, fourth `/27` of the second quarter)
    delegated to `Microsoft.App/environments`.
  - `modules/vnet-runner` uses a Consumption Workload Profile (`workload_profile_type = "Consumption"`)
    so only a `/27` is needed, and supports both GitHub App authentication (`application_id`,
    `installation_id`, `private_key_key_vault_secret_id`) and PAT authentication.
  - `00-pipeline` sets `NERDIO_RUNNER_LABELS` on `<env>-plan` and `<env>-apply`, and `deploy.yml`
    resolves `runs-on` dynamically from `inputs.runner_labels` or `vars.NERDIO_RUNNER_LABELS`.
- **Destructive-change guardrails (`scripts/pipeline/stage.sh`, `deploy.yml`):**
  - When `destroy = false`, `stage.sh` inspects `terraform show -json` for any `delete` action
    (including replacements) on stateful Stage 1 resources (SQL, Key Vault, Storage, ANF, VNet,
    Subnets, Compute Gallery, DES) and Stage 2 resources (`nme_workspace`, `nme_dynamic_host_pool`,
    `nme_static_host_pool`, `nme_linked_network`, `nme_linked_resource_group`, `nme_fslogix_profile`).
  - Plans that delete or replace those resources fail before uploading the plan tarball unless
    `allow_replace = true` is explicitly passed.
- **Resource locks & Trivy IaC scanning (`01-platform`, `00-pipeline`, `validate.yml`):**
  - `enable_resource_locks` defaults to `true` when `environment == "prod"` (and `false` for
    `sandbox`/`dev`), placing `CanNotDelete` locks on Nerdio SQL, Key Vaults, FSLogix storage, and
    ANF volumes; `00-pipeline` locks the state storage account by default.
  - `validate.yml` runs `trivy config --severity HIGH,CRITICAL --exit-code 1` with documented
    architectural exceptions in `.trivyignore`.
- **GitOps PR-plan & merge-apply (`config/answers/<env>.json`, `00-pipeline`, `deploy.yml`):**
  - Non-identifying answer sets (`config/answers/<env>.json`, containing no real GUIDs) can be
    committed to Git and are validated by `./nerdio schema check` and `validate.yml`.
  - Setting `github.allow_pr_plans = true` in `00-pipeline` lets PRs targeting `config/answers/*.json`
    run read-only plans against `<env>-plan`, while merging to `main` runs `stage = auto` (planning
    and gating `platform` and `config` behind `<env>-apply`).

### Consequences

- Good, because hardened environments with public access disabled have a turnkey, scale-to-zero
  runner path inside the AVD spoke VNet.
- Good, because accidental replacements in `nerdio/nme` 0.x or stateful Azure resources are caught
  automatically before reaching the approval gate.
- Good, because teams can choose between interactive chatbot-driven setup, button dispatches, or
  PR-driven GitOps without ever committing tenant or subscription IDs.
