output "container_app_environment_id" {
  description = "Resource ID of the VNet-integrated Container Apps Environment."
  value       = azurerm_container_app_environment.this.id
}

output "runner_job_id" {
  description = "Resource ID of the ephemeral GitHub Actions Container Apps Job."
  value       = azurerm_container_app_job.runner.id
}

output "runner_identity_principal_id" {
  description = "Principal ID of the runner's User-Assigned Managed Identity."
  value       = azurerm_user_assigned_identity.runner.principal_id
}
