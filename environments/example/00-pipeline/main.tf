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

# Repository settings (labels, workflow token, the ruleset on the branch the apply trusts) moved to
# github/, which has its own state and a daily drift check. Forget them here without touching GitHub.
removed {
  from = module.github_repo

  lifecycle {
    destroy = false
  }
}
