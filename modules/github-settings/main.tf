# One repository's GitHub settings, declared so drift shows up in `terraform plan`. The same
# module and defaults serve every repository that follows ai-brain decision 0014's GitHub work
# conventions; each repository passes only what is its own (description, checks, labels).
#
# It never creates or deletes the repository: the github/ root imports it, and prevent_destroy
# makes any plan that would delete it fail.

locals {
  ruleset_name = coalesce(var.ruleset.name, "protect-${var.branch}")
}

resource "github_repository" "this" {
  name         = var.repository
  description  = var.repo.description
  homepage_url = var.repo.homepage_url
  topics       = var.repo.topics

  has_issues      = var.repo.has_issues
  has_projects    = var.repo.has_projects
  has_wiki        = var.repo.has_wiki
  has_discussions = var.repo.has_discussions

  allow_merge_commit     = var.merge.allow_merge_commit
  allow_squash_merge     = var.merge.allow_squash_merge
  allow_rebase_merge     = var.merge.allow_rebase_merge
  allow_auto_merge       = var.merge.allow_auto_merge
  allow_update_branch    = var.merge.allow_update_branch
  delete_branch_on_merge = var.merge.delete_branch_on_merge

  security_and_analysis {
    secret_scanning {
      status = var.security.secret_scanning ? "enabled" : "disabled"
    }
    secret_scanning_push_protection {
      status = var.security.push_protection ? "enabled" : "disabled"
    }
  }

  lifecycle {
    prevent_destroy = true
    # Visibility, the default branch, archiving and template status are changed on purpose, by
    # hand, never by a settings run. Vulnerability alerts have their own resource below. GitHub
    # turns advanced security on for every public repository and it can't be changed there.
    ignore_changes = [
      visibility, private, default_branch, archived, is_template, vulnerability_alerts, has_downloads,
      security_and_analysis[0].advanced_security,
    ]
  }
}

resource "github_repository_vulnerability_alerts" "this" {
  repository = github_repository.this.name
  enabled    = var.security.dependabot_alerts
}

resource "github_repository_dependabot_security_updates" "this" {
  repository = github_repository.this.name
  enabled    = var.security.dependabot_alerts && var.security.dependabot_security_updates
  depends_on = [github_repository_vulnerability_alerts.this]
}

resource "github_issue_label" "this" {
  for_each    = var.labels
  repository  = github_repository.this.name
  name        = each.key
  color       = each.value.color
  description = each.value.description
}

# Every workflow declares its own permissions, so the default token can stay read-only.
resource "github_workflow_repository_permissions" "this" {
  repository                       = github_repository.this.name
  default_workflow_permissions     = "read"
  can_approve_pull_request_reviews = var.actions.can_open_pull_requests
}

resource "github_repository_ruleset" "branch" {
  count       = var.ruleset.enabled ? 1 : 0
  name        = local.ruleset_name
  repository  = github_repository.this.name
  target      = "branch"
  enforcement = "active"

  conditions {
    ref_name {
      include = ["refs/heads/${var.branch}"]
      exclude = []
    }
  }

  dynamic "bypass_actors" {
    for_each = var.ruleset.admin_bypass ? [1] : []
    content {
      actor_type  = "RepositoryRole"
      actor_id    = 5 # the built-in repository admin role
      bypass_mode = "pull_request"
    }
  }

  rules {
    deletion         = true
    non_fast_forward = true

    pull_request {
      required_approving_review_count = var.ruleset.required_approvals
    }

    dynamic "required_status_checks" {
      for_each = length(var.ruleset.required_checks) > 0 ? [1] : []
      content {
        strict_required_status_checks_policy = false
        dynamic "required_check" {
          for_each = var.ruleset.required_checks
          content {
            context        = required_check.value
            integration_id = var.ruleset.checks_app_id
          }
        }
      }
    }
  }
}
