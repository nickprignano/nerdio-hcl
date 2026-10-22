output "labels" {
  description = "Issue labels this module manages."
  value       = sort(keys(github_issue_label.this))
}

output "protected_branch" {
  description = "The branch the ruleset protects, or null when the ruleset is off."
  value       = var.ruleset.enabled ? var.branch : null
}

# Known before anything is read, so a root module can use them to decide what to import.
output "labels_declared" {
  description = "The labels this module declares, by name."
  value       = var.labels
}

output "ruleset_name" {
  description = "The name of the default-branch ruleset."
  value       = local.ruleset_name
}
