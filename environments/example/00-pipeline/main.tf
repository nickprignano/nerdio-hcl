# One-time bootstrap for the deploy pipeline (decision 0016): state storage, the plan and apply
# identities, and the GitHub environments that gate an apply behind a reviewer's approval.
# Run it from Cloud Shell with scripts/pipeline/bootstrap.sh; after this, plans and applies run
# in GitHub Actions.

module "pipeline" {
  source = "../../../modules/deploy-pipeline"

  name            = var.name
  location        = var.location
  tenant_id       = var.tenant_id
  subscription_id = var.subscription_id
  environment     = var.environment
  github          = var.github
  tags            = var.tags

  apply_roles            = var.access.apply_roles
  apply_assignable_roles = var.access.apply_assignable_roles
  apply_graph_roles      = var.access.apply_graph_roles
  plan_graph_roles       = var.access.plan_graph_roles
}

# Repository settings the kit relies on: the kb-* labels, a read-only default workflow token,
# Actions allowed to open pull requests, and a ruleset protecting the branch the apply trusts.
module "github_repo" {
  source = "../../../modules/github-repo"

  repository                     = var.github.repository
  branch                         = var.github.branch
  protect_branch                 = var.github_settings.protect_branch
  actions_can_open_pull_requests = var.github_settings.actions_can_open_pull_requests
}
