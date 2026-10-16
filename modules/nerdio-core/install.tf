# Installs the app code by starting the updater runbook once, inside Azure. The job name is
# derived from the web app and the requested version, so it runs on the first apply and again
# only when package_version changes. Applies don't wait for it; the check in web_app.tf reports
# when Nerdio answers.

resource "azapi_resource_action" "install" {
  type        = "Microsoft.Automation/automationAccounts/jobs@2023-11-01"
  resource_id = "${azurerm_automation_account.this.id}/jobs/${uuidv5("url", "${azurerm_windows_web_app.this.id}?version=${var.package_version}")}"
  method      = "PUT"

  body = {
    properties = {
      runbook = { name = azurerm_automation_runbook.updater.name }
      parameters = {
        packageVersion = var.package_version
        maintenanceUri = var.maintenance_service_url
      }
    }
  }

  depends_on = [
    azurerm_automation_variable_string.this,
    azurerm_role_assignment.automation_web_app,
    azurerm_role_assignment.key_vault,
    azurerm_role_assignment.nerdio_app,
    azurerm_mssql_database.this,
    azurerm_mssql_firewall_rule.azure_services,
    azuread_group.sql_admins,
    azuread_application_certificate.app,
    azurerm_key_vault_key.data_protection,
    azurerm_key_vault_secret.data_protection_path,
    azurerm_key_vault_secret.locks_container,
    azurerm_automation_certificate.scripted_actions,
  ]
}
