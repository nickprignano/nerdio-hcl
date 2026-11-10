---
status: proposed
date: 2026-11-10
decision-makers: [maintainers]
---

# 0033. CI/CD: one reusable stage workflow, plans on pull requests, daily drift check, Bicep stage

## Context and Problem Statement

The gated pipeline ([0016](0016-gated-deploy-pipeline.md), [0030](0030-enterprise-guardrails-locks-and-gitops.md))
plans and applies from the Actions tab, the setup chatbot or a merged answers file. Gaps remained
for running the kit as ordinary CI/CD: `deploy.yml` repeated the same sign-in and secrets block in
five jobs; a pull request that changed the kit's code got no plan, so reviewers judged Terraform
changes blind; nothing noticed when Azure or Nerdio's console drifted from `main`; workflow actions
were pinned to moving tags while their jobs hold OIDC tokens for the apply identity; and the Bicep
variant ([0032](README.md)) had no way through the gate. How should the kit close these without
adding secrets, weakening least privilege or applying anything without a reviewer?

## Considered Options

- Keep `deploy.yml` as is and document manual plans and drift checks
- One reusable `stage.yml` that every caller uses; read-only plans on same-repository pull requests
  posted as a comment; a scheduled read-only drift plan that files an issue; a `bicep` stage that
  saves a hash-checked what-if and re-checks it before deploying a deployment stack; SHA-pinned
  actions kept current by Dependabot
- Move to Terraform Cloud / HCP Terraform runs or Azure DevOps Pipelines

## Decision Outcome

Chosen option: the second, because it keeps everything GitHub- and Azure-native, reuses the
identities and environments the bootstrap already creates, and adds no stored secret.

- **`stage.yml` (workflow_call)** runs one stage's plan, apply or unlock in `<env>-plan` or
  `<env>-apply`. Environment secrets are read inside it, so callers pass none. `deploy.yml` and
  `drift.yml` both call it.
- **Pull request plans.** A same-repository pull request touching `modules/`, `environments/example/`,
  `bicep/`, `scripts/pipeline/` or `schema/parameters.json` plans the environment named in the
  repository variable `NERDIO_PR_PLAN_ENV` (unset: off) as the plan identity, only when
  `github.allow_pr_plans = true`, and a job with only
  `pull-requests: write` posts the masked summary as one comment, updated per push. Fork pull
  requests are skipped; they get no OIDC token anyway. Merged code never applies on its own.
- **Drift.** `drift.yml` runs daily for the environments in `NERDIO_DRIFT_ENVS` (off when unset),
  plans each stage with `DRIFT=true` (nothing saved to apply; the destructive-change guardrail
  reports instead of failing), and a job with only `issues: write` opens, updates or closes one
  `infra-drift` issue per environment. It catches portal edits, Nerdio console edits (the
  `nerdio/nme` refresh) and code merged but never applied.
- **Bicep stage.** `stage.sh` builds `bicep/main.bicep` and the environment's `.bicepparam`, runs
  `az deployment sub what-if --validation-level ProviderNoRbac` as the plan identity, and saves the
  compiled template, parameters and change list with a SHA-256. The apply re-checks the hash, then
  runs what-if again as the apply identity and refuses if the change list differs, because ARM has
  no saved plan that refuses to go stale the way a Terraform plan does. It deploys as a
  subscription deployment stack (`detachAll`, no deny settings yet). The config stage reads
  `nerdio_config_inputs` from the stack's outputs when there is no Terraform platform state.
- **Plan identity for Bicep.** What-if is an action (`Microsoft.Resources/deployments/whatIf/action`),
  not a read, so Reader can't call it. `plan_bicep_whatif = true` adds a custom role with only the
  what-if and validate actions. Off by default.
- **Supply chain.** Every `uses:` is pinned to a commit SHA with its version in a comment;
  `.github/dependabot.yml` bumps actions, the assistant's pip packages and its base image weekly.
  `validate.yml` lints the workflows with a checksum-verified actionlint.

### Consequences

- Good, because reviewers see a plan before merging and drift becomes a tracked issue, with no new
  Azure rights for Terraform and only two read-like actions for Bicep.
- Good, because one place signs in and masks IDs; a fix to the stage job reaches every caller.
- Bad, because pull request plans run the branch's Terraform as the plan identity, which can read
  state (and the secrets in it). That is why they stay opt-in (`allow_pr_plans`) and same-repository only.
- Bad, because Bicep what-if can report values it can't evaluate (`reference()`, secure values) as
  changes, so a stack's re-check can refuse an apply that would have been fine; plan again.
- Neutral: Microsoft Graph Bicep resources aren't supported by deployment stacks or what-if; the
  Bicep variant's identity slice will need its own non-stack deployment step.

## More Information

Not yet run against a live tenant. Live checks to do first: a pull request plan comment, a drift
issue opened and closed, and whether `ProviderNoRbac` what-if works with Reader plus the custom
role. Azure DevOps Pipelines support is a possible follow-up: `stage.sh` would need its
`::add-mask::` lines made GitHub-only first, or they would print the IDs they hide.
