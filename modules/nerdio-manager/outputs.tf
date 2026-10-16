output "deployment_outputs" {
  description = "Raw outputs of the Marketplace template."
  value       = jsondecode(azurerm_resource_group_template_deployment.nerdio.output_content)
}

output "app_service_id" {
  description = "Nerdio Manager App Service ID."
  value       = local.web_app.id
}

output "app_service_name" {
  description = "Nerdio Manager App Service name."
  value       = local.web_app.name
}

output "app_service_hostname" {
  description = "Default hostname; open https://<this> to run the post-deploy install step."
  value       = "${local.web_app.name}.azurewebsites.net"
}

output "sql_server_ids" {
  description = "Map of name to ID: Nerdio SQL server IDs."
  value       = { for r in data.azurerm_resources.sql_servers.resources : r.name => r.id }
}

output "key_vault_ids" {
  description = "Map of name to ID: Key Vault IDs created by the template."
  value       = { for r in data.azurerm_resources.key_vaults.resources : r.name => r.id }
}

output "automation_account_ids" {
  description = "Map of name to ID: Automation account IDs."
  value       = { for r in data.azurerm_resources.automation_accounts.resources : r.name => r.id }
}

output "storage_account_ids" {
  description = "Map of name to ID: Storage account IDs created by the template (scripts, temp VHDs, diagnostics)."
  value       = { for r in data.azurerm_resources.storage_accounts.resources : r.name => r.id }
}
