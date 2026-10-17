# Offline plan tests with a mocked provider: terraform init -backend=false && terraform test

mock_provider "github" {}

variables {
  repository = "nerdio-hcl"
}

run "defaults" {
  command = plan

  assert {
    condition     = length(github_issue_label.this) == 4
    error_message = "All four kb-* labels must exist before the issue forms are used."
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
}

run "opt_out" {
  command = plan

  variables {
    protect_branch                 = false
    actions_can_open_pull_requests = false
  }

  assert {
    condition     = length(github_repository_ruleset.branch) == 0
    error_message = "protect_branch = false must leave the branch alone."
  }
  assert {
    condition     = !github_workflow_repository_permissions.this.can_approve_pull_request_reviews
    error_message = "Opting out must turn off Actions pull requests."
  }
}
