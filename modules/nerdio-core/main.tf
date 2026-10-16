# Nerdio Manager core, built in Terraform instead of Nerdio's Marketplace template and install
# script. It creates the same resources and app settings, with three differences:
# - SQL uses Entra authentication only. The template uses a SQL admin login and password.
# - The Nerdio app signs in with Key Vault certificates, not a client secret.
# - The app code is deployed by an Automation job that runs in Azure, so the machine running
#   Terraform needs nothing beyond Terraform (it works from Cloud Shell or a pipeline).

data "azurerm_client_config" "current" {}

data "azurerm_subscription" "current" {}

locals {
  # Nerdio's template: uniqueString(subscription().id, resourceGroup().id), 13 characters.
  suffix = coalesce(var.name_suffix, substr(sha1("${data.azurerm_subscription.current.id}/resourceGroups/${var.resource_group_name}"), 0, 13))

  names = {
    web_app          = "${var.app_name}-${local.suffix}"
    plan             = "${var.app_name}-plan-${local.suffix}"
    sql_server       = "${var.app_name}-sql-${local.suffix}"
    database         = "${var.app_name}-db"
    key_vault        = "${var.app_name}-kv-${local.suffix}"
    app_insights     = "${var.app_name}-insights-${local.suffix}"
    automation       = "${var.app_name}-automation-${local.suffix}"
    scripted_actions = "${var.app_name}-scripted-actions-${local.suffix}"
    law              = "${var.app_name}-law-${local.suffix}"
    logs_law         = "${var.app_name}-law-insights-${local.suffix}"
    storage          = "nmwdp${local.suffix}"
    sql_admins       = "${var.app_name}-${local.suffix}-sql-admins"
    app_cert         = "nme-app-cert"
    scripted_cert    = "nmw-scripted-action-cert"
    data_protection  = "DataProtection-main"
    dp_container     = "dataprotectionkeys"
    dp_blob          = "keys.xml"
    locks_container  = "locks"
    updater_runbook  = "nmwUpdateRunAs"
    default_hostname = "${var.app_name}-${local.suffix}.azurewebsites.net"
    key_vault_uri    = "https://${var.app_name}-kv-${local.suffix}.vault.azure.net"
    sql_server_fqdn  = "${var.app_name}-sql-${local.suffix}.database.windows.net"
  }

  paas_tags = merge(var.tags, { NMW_OBJECT_TYPE = "PAAS" })
}

resource "azurerm_log_analytics_workspace" "insights" {
  name                = local.names.logs_law
  location            = var.location
  resource_group_name = var.resource_group_name
  retention_in_days   = 30
  tags                = var.tags
}

resource "azurerm_application_insights" "this" {
  name                = local.names.app_insights
  location            = var.location
  resource_group_name = var.resource_group_name
  application_type    = "web"
  workspace_id        = azurerm_log_analytics_workspace.insights.id
  tags                = var.tags
}

# The workspace Nerdio sends AVD host diagnostics to (Deployment:LogAnalyticsWorkspace).
resource "azurerm_log_analytics_workspace" "avd" {
  name                = local.names.law
  location            = var.location
  resource_group_name = var.resource_group_name
  retention_in_days   = 30
  tags                = merge(var.tags, { NMW_OBJECT_TYPE = "LOG_ANALYTICS_WORKSPACE" })
}
