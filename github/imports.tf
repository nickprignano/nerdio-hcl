# Adopt what already exists on every run. With no saved state, these imports are what lets plan
# compare the code with GitHub: anything that matches shows as "import" with no change, anything
# that differs shows as an update, and anything missing shows as a create.

locals {
  repo = var.repository
}

import {
  to = module.settings.github_repository.this
  id = local.repo
}

import {
  to = module.settings.github_repository_vulnerability_alerts.this
  id = local.repo
}

import {
  to = module.settings.github_repository_dependabot_security_updates.this
  id = local.repo
}

import {
  to = module.settings.github_workflow_repository_permissions.this
  id = local.repo
}

# Labels: import only the declared labels that exist; a missing one is created.
data "github_issue_labels" "existing" {
  repository = local.repo
}

locals {
  # GitHub matches label names without regard to case, so an existing "No-KB" is adopted as "no-kb".
  existing_labels = { for l in data.github_issue_labels.existing.labels : lower(l.name) => l.name }
  labels_to_import = {
    for k in keys(module.settings.labels_declared) : k => local.existing_labels[lower(k)]
    if contains(keys(local.existing_labels), lower(k))
  }
}

import {
  for_each = local.labels_to_import
  to       = module.settings.github_issue_label.this[each.key]
  id       = "${local.repo}:${each.value}"
}

# The ruleset: there's no data source for rulesets, so list them through the provider's own REST
# call, with the same token as everything else.
data "github_rest_api" "rulesets" {
  endpoint = "repos/${var.owner}/${local.repo}/rulesets"
}

locals {
  branch_rulesets = [for r in jsondecode(data.github_rest_api.rulesets.body) : r if r.target == "branch"]
  ruleset_matches = [for r in local.branch_rulesets : r.id if r.name == module.settings.ruleset_name]
}

check "one_ruleset" {
  assert {
    condition     = length(local.ruleset_matches) <= 1
    error_message = "More than one branch ruleset is named \"${module.settings.ruleset_name}\"; rename or delete the extra one before planning."
  }
}

# A branch ruleset this code doesn't manage changes what can merge without showing in the plan.
check "no_unmanaged_rulesets" {
  assert {
    condition     = length(local.branch_rulesets) == length(local.ruleset_matches)
    error_message = "Branch rulesets not managed here: ${join(", ", [for r in local.branch_rulesets : r.name if r.name != module.settings.ruleset_name])}. Add them to the code or delete them."
  }
}

import {
  for_each = { for id in slice(local.ruleset_matches, 0, min(1, length(local.ruleset_matches))) : "0" => id }
  to       = module.settings.github_repository_ruleset.branch[0]
  id       = "${local.repo}:${each.value}"
}
