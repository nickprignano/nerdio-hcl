resource "azurerm_automation_account" "this" {
  name                = local.names.automation
  location            = var.location
  resource_group_name = var.resource_group_name
  sku_name            = "Basic"
  tags                = var.tags

  identity {
    type = "SystemAssigned"
  }
}

# Variables Nerdio's updater runbook reads.
resource "azurerm_automation_variable_string" "this" {
  for_each = {
    subscriptionId    = data.azurerm_client_config.current.subscription_id
    resourceGroupName = var.resource_group_name
    webAppName        = local.names.web_app
  }
  name                    = each.key
  resource_group_name     = var.resource_group_name
  automation_account_name = azurerm_automation_account.this.name
  value                   = each.value
  encrypted               = true
}

# Deploys a Nerdio package to the web app. Nerdio's in-app updater calls it by this name with a
# package URL; the install job below calls it with a version instead.
resource "azurerm_automation_runbook" "updater" {
  name                    = local.names.updater_runbook
  location                = var.location
  resource_group_name     = var.resource_group_name
  automation_account_name = azurerm_automation_account.this.name
  runbook_type            = "PowerShell"
  log_progress            = false
  log_verbose             = true
  description             = "Deploy a Nerdio Manager package to the web app (managed identity)."
  content                 = file("${path.module}/runbooks/nmw-update.ps1")
  tags                    = var.tags
}

# Zip deploy through the SCM site with an Entra token needs Website Contributor on the app.
resource "azurerm_role_assignment" "automation_web_app" {
  scope                = azurerm_windows_web_app.this.id
  role_definition_name = "Website Contributor"
  principal_id         = azurerm_automation_account.this.identity[0].principal_id
}

resource "azurerm_automation_account" "scripted_actions" {
  name                = local.names.scripted_actions
  location            = var.location
  resource_group_name = var.resource_group_name
  sku_name            = "Basic"
  tags                = var.tags
}

data "azurerm_key_vault_secret" "scripted_actions_pfx" {
  name         = azurerm_key_vault_certificate.scripted_actions.name
  key_vault_id = azurerm_key_vault.this.id
  depends_on   = [azurerm_key_vault_certificate.scripted_actions]
}

resource "azurerm_automation_certificate" "scripted_actions" {
  name                    = "ScriptedActionRunAsCert"
  resource_group_name     = var.resource_group_name
  automation_account_name = azurerm_automation_account.scripted_actions.name
  base64                  = data.azurerm_key_vault_secret.scripted_actions_pfx.value
  exportable              = true
}
