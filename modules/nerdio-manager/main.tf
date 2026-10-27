resource "azurerm_resource_group_template_deployment" "nerdio" {
  count               = var.template_file == null ? 0 : 1
  name                = var.deployment_name
  resource_group_name = var.resource_group_name
  deployment_mode     = "Incremental"
  template_content    = file(var.template_file)
  parameters_content  = jsonencode({ for k, v in var.parameters : k => { value = v } })
  tags                = var.tags

  lifecycle {
    # Nerdio updates its own app in place after install; re-running the original
    # template would roll that back. Change the template on purpose, not by drift.
    ignore_changes = [template_content]
  }
}

# The Marketplace deployment (from the Azure portal UI or an exported template) generates
# resource names, so look them up in the target resource group. Before a portal Marketplace
# deployment runs, the resource group is empty and web_app is null.
data "azurerm_resources" "web_apps" {
  resource_group_name = var.resource_group_name
  type                = "Microsoft.Web/sites"
  depends_on          = [azurerm_resource_group_template_deployment.nerdio]
}

data "azurerm_resources" "sql_servers" {
  resource_group_name = var.resource_group_name
  type                = "Microsoft.Sql/servers"
  depends_on          = [azurerm_resource_group_template_deployment.nerdio]
}

data "azurerm_resources" "key_vaults" {
  resource_group_name = var.resource_group_name
  type                = "Microsoft.KeyVault/vaults"
  depends_on          = [azurerm_resource_group_template_deployment.nerdio]
}

data "azurerm_resources" "automation_accounts" {
  resource_group_name = var.resource_group_name
  type                = "Microsoft.Automation/automationAccounts"
  depends_on          = [azurerm_resource_group_template_deployment.nerdio]
}

data "azurerm_resources" "storage_accounts" {
  resource_group_name = var.resource_group_name
  type                = "Microsoft.Storage/storageAccounts"
  depends_on          = [azurerm_resource_group_template_deployment.nerdio]
}

locals {
  web_app = try(one(data.azurerm_resources.web_apps.resources), null)
}
