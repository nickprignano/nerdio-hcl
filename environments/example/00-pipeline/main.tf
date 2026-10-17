# One-time bootstrap for the deploy pipeline (decision 0016): state storage, the plan and apply
# identities, and the GitHub environments that gate an apply behind a reviewer's approval.
# Run it from Cloud Shell with scripts/pipeline-bootstrap.sh; after this, plans and applies run
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
}
