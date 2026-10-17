output "resource_group_name" {
  description = "Resource group with the state storage and deploy identities."
  value       = module.pipeline.resource_group_name
}

output "storage_account_name" {
  description = "Storage account for Terraform state and saved plans."
  value       = module.pipeline.storage_account_name
}

output "github_environments" {
  description = "GitHub environments the deploy workflow uses."
  value       = module.pipeline.github_environments
}

output "storage_account_id" {
  description = "Storage account resource ID; ./nerdio assistant --pipeline reads it to give the chatbot access."
  value       = module.pipeline.storage_account_id
}

output "environment" {
  description = "Kit environment this pipeline deploys."
  value       = var.environment
}
