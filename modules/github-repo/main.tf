# Repository settings the kit relies on, so nothing has to be clicked in GitHub's settings pages.
# Each resource manages one setting and leaves the rest of the repository alone.

locals {
  # Issue forms only apply labels that already exist. kb-freshness creates them too; this makes
  # them exist from the first bootstrap, before any workflow has run.
  labels = {
    "kb-feedback"    = { color = "1d76db", description = "Knowledge base feedback" }
    "kb-known-error" = { color = "d93f0b", description = "Known error for the troubleshooting catalog" }
    "kb-accepted"    = { color = "0e8a16", description = "Reviewed; turn into a KB pull request" }
    "kb-freshness"   = { color = "fbca04", description = "KB pages to re-check" }
  }
}

resource "github_issue_label" "this" {
  for_each    = local.labels
  repository  = var.repository
  name        = each.key
  color       = each.value.color
  description = each.value.description
}

# Every workflow declares its own permissions, so the default token can stay read-only.
resource "github_workflow_repository_permissions" "this" {
  repository                       = var.repository
  default_workflow_permissions     = "read"
  can_approve_pull_request_reviews = var.actions_can_open_pull_requests
}

resource "github_repository_ruleset" "branch" {
  count       = var.protect_branch ? 1 : 0
  name        = "protect-${var.branch}"
  repository  = var.repository
  target      = "branch"
  enforcement = "active"

  conditions {
    ref_name {
      include = ["refs/heads/${var.branch}"]
      exclude = []
    }
  }

  rules {
    deletion         = true
    non_fast_forward = true

    pull_request {
      # A single maintainer must be able to merge their own pull request.
      required_approving_review_count = 0
    }
  }
}
