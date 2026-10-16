locals {
  # Providers listed in Nerdio's prerequisites, plus the ones the kit itself uses.
  resource_providers = toset([
    "Microsoft.DesktopVirtualization",
    "Microsoft.Compute",
    "Microsoft.Storage",
    "Microsoft.Automation",
    "Microsoft.RecoveryServices",
    "Microsoft.Sql",
    "Microsoft.Insights",
    "Microsoft.KeyVault",
    "Microsoft.Web",
    "Microsoft.Network",
    "Microsoft.OperationalInsights",
  ])
}

resource "azurerm_resource_provider_registration" "this" {
  for_each = var.register_resource_providers ? local.resource_providers : toset([])
  name     = each.value
}

resource "azurerm_resource_group" "this" {
  for_each = var.resource_groups
  name     = each.value
  location = var.location
  tags     = merge(var.tags, { "nerdio-kit-role" = each.key })

  depends_on = [azurerm_resource_provider_registration.this]
}

resource "azurerm_log_analytics_workspace" "avd" {
  count               = var.create_log_analytics ? 1 : 0
  name                = "log-${var.prefix}-avd"
  location            = var.location
  resource_group_name = azurerm_resource_group.this["monitoring"].name
  sku                 = "PerGB2018"
  retention_in_days   = var.log_analytics_retention_days
  tags                = var.tags
}
