output "labels" {
  description = "Issue labels the kit's workflows and issue forms use."
  value       = sort(keys(github_issue_label.this))
}

output "protected_branch" {
  description = "The branch the ruleset protects, or null when protect_branch is off."
  value       = var.protect_branch ? var.branch : null
}
