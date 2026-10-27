# Resource providers are registered by the azurerm provider block in the root module
# (resource_providers_to_register), which skips any already registered. The old per-provider
# resource failed on subscriptions that had them. Forget it without unregistering anything.
removed {
  from = azurerm_resource_provider_registration.this

  lifecycle {
    destroy = false
  }
}

resource "azurerm_resource_group" "this" {
  for_each = { for k, v in var.resource_groups : k => v if !contains(var.existing_resource_groups, k) }
  name     = each.value
  location = var.location
  tags     = merge(var.tags, { "nerdio-kit-role" = each.key })
}

data "azurerm_resource_group" "existing" {
  for_each = { for k, v in var.resource_groups : k => v if contains(var.existing_resource_groups, k) }
  name     = each.value
}

locals {
  all_resource_groups = merge(azurerm_resource_group.this, data.azurerm_resource_group.existing)
}

resource "azurerm_log_analytics_workspace" "avd" {
  count               = var.create_log_analytics ? 1 : 0
  name                = "log-${var.prefix}-avd"
  location            = var.location
  resource_group_name = local.all_resource_groups["monitoring"].name
  sku                 = "PerGB2018"
  retention_in_days   = var.log_analytics_retention_days
  tags                = var.tags
}
