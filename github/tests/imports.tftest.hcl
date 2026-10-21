# Offline tests of the import wiring with mocked providers: terraform init -backend=false && terraform test

mock_provider "github" {
  mock_data "github_repository" {
    defaults = { description = "", homepage_url = "", has_issues = true, has_projects = false, has_wiki = false, has_discussions = false }
  }
  mock_data "github_issue_labels" {
    defaults = {
      labels = [
        { name = "No-KB", color = "ededed", description = "", url = "" },
        { name = "bug", color = "d73a4a", description = "", url = "" },
      ]
    }
  }
}



# Imports can't run against a mock provider, so each imported resource gets an override.
override_resource {
  target = module.settings.github_repository.this
}
override_resource {
  target = module.settings.github_repository_vulnerability_alerts.this
}
override_resource {
  target = module.settings.github_repository_dependabot_security_updates.this
}
override_resource {
  target = module.settings.github_workflow_repository_permissions.this
}
override_resource {
  target = module.settings.github_issue_label.this
}
override_resource {
  target = module.settings.github_repository_ruleset.branch
}

variables {
  owner      = "contoso"
  repository = "example"
}

run "ruleset_exists" {
  command = plan

  override_data {
    target = data.github_rest_api.rulesets
    values = {
      body = "[{\"id\": 42, \"name\": \"protect-main\", \"target\": \"branch\"}, {\"id\": 7, \"name\": \"tags\", \"target\": \"tag\"}]"
    }
  }

  assert {
    condition     = local.ruleset_matches == [42]
    error_message = "Only the default-branch ruleset is adopted."
  }
}

run "no_ruleset_yet" {
  command = plan

  override_data {
    target = data.github_rest_api.rulesets
    values = { body = "[]" }
  }

  assert {
    condition     = length(local.ruleset_matches) == 0
    error_message = "With no ruleset, the plan creates one instead of importing."
  }
}

run "unmanaged_ruleset" {
  command = plan

  override_data {
    target = data.github_rest_api.rulesets
    values = { body = "[{\"id\": 1, \"name\": \"protect-main\", \"target\": \"branch\"}, {\"id\": 2, \"name\": \"someone-elses\", \"target\": \"branch\"}]" }
  }

  expect_failures = [check.no_unmanaged_rulesets]
}

run "label_case" {
  command = plan

  override_data {
    target = data.github_rest_api.rulesets
    values = { body = "[]" }
  }

  assert {
    condition     = local.labels_to_import == { "no-kb" = "No-KB" }
    error_message = "A declared label that exists in another case is adopted, not created again."
  }
}
