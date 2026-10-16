output "app_service_id" {
  description = "Nerdio Manager web app ID."
  value       = azurerm_windows_web_app.this.id
}

output "app_service_name" {
  description = "Nerdio Manager web app name."
  value       = azurerm_windows_web_app.this.name
}

output "app_service_hostname" {
  description = "Default hostname. Known at plan time, so the Entra app can use it before the web app exists."
  value       = local.names.default_hostname
}

output "sql_server_ids" {
  description = "Map of name to ID: the Nerdio SQL server."
  value       = { (local.names.sql_server) = azurerm_mssql_server.this.id }
}

output "key_vault_ids" {
  description = "Map of name to ID: the Nerdio Key Vault."
  value       = { (local.names.key_vault) = azurerm_key_vault.this.id }
}

output "storage_account_ids" {
  description = "Map of name to ID: the data protection storage account."
  value       = { (local.names.storage) = azurerm_storage_account.data_protection.id }
}

output "automation_account_ids" {
  description = "Map of name to ID: the updater and scripted-actions Automation accounts."
  value = {
    (local.names.automation)       = azurerm_automation_account.this.id
    (local.names.scripted_actions) = azurerm_automation_account.scripted_actions.id
  }
}

output "install_job_id" {
  description = "Automation job that installed the app code. Its output is under the updater Automation account's Jobs."
  value       = azapi_resource_action.install.resource_id
}
