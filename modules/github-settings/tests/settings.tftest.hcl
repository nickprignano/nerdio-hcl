# Offline plan tests with a mocked provider: terraform init -backend=false && terraform test

mock_provider "github" {}

variables {
  repository = "nerdio-hcl"
  labels = {
    "kb-feedback" = { color = "1d76db", description = "Knowledge base feedback" }
    "no-kb"       = { color = "ededed" }
  }
  ruleset = { required_checks = ["terraform", "secrets"] }
}

run "conventions" {
  command = plan

  assert {
    condition     = github_repository.this.allow_merge_commit && github_repository.this.allow_auto_merge
    error_message = "Decision 0014: merge commits and auto-merge stay on."
  }
  assert {
    condition     = github_workflow_repository_permissions.this.default_workflow_permissions == "read"
    error_message = "The default workflow token must stay read-only."
  }
  assert {
    condition     = github_repository_ruleset.branch[0].conditions[0].ref_name[0].include == tolist(["refs/heads/main"])
    error_message = "The ruleset must protect the branch the apply environment trusts."
  }
  assert {
    condition     = github_repository_ruleset.branch[0].rules[0].non_fast_forward && github_repository_ruleset.branch[0].rules[0].deletion
    error_message = "The protected branch can't be force-pushed or deleted."
  }
  assert {
    condition     = github_repository_ruleset.branch[0].rules[0].pull_request[0].required_approving_review_count == 0
    error_message = "Decision 0014: no required review, since the owner can't approve their own pull requests."
  }
  assert {
    condition     = alltrue([for c in github_repository_ruleset.branch[0].rules[0].required_status_checks[0].required_check : c.integration_id == 15368])
    error_message = "Required checks must come from GitHub Actions, not any commit status."
  }
  assert {
    condition     = github_repository_ruleset.branch[0].bypass_actors[0].bypass_mode == "pull_request"
    error_message = "The admin bypass covers pull requests only, never direct pushes."
  }
  assert {
    condition     = github_repository.this.security_and_analysis[0].secret_scanning_push_protection[0].status == "enabled"
    error_message = "Decision 0016 step 11: push protection stays on."
  }
  assert {
    condition     = github_repository_dependabot_security_updates.this.enabled && github_repository_vulnerability_alerts.this.enabled
    error_message = "Dependabot alerts and security updates are on by default."
  }
  assert {
    condition     = length(github_issue_label.this) == 2
    error_message = "Only the declared labels are managed."
  }
}

run "opt_out" {
  command = plan

  variables {
    ruleset  = { enabled = false }
    actions  = { can_open_pull_requests = false }
    security = { dependabot_alerts = false }
  }

  assert {
    condition     = length(github_repository_ruleset.branch) == 0
    error_message = "ruleset.enabled = false must leave the branch alone."
  }
  assert {
    condition     = !github_workflow_repository_permissions.this.can_approve_pull_request_reviews
    error_message = "Opting out must turn off Actions pull requests."
  }
  assert {
    condition     = !github_repository_dependabot_security_updates.this.enabled
    error_message = "Security updates need alerts; turning alerts off turns them off too."
  }
}
