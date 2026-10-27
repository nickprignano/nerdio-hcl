# Terraform equivalent of Nerdio's "Enable Private Endpoints" runbook: the App Service
# reaches SQL, Key Vault, Blob Storage and Automation through private endpoints in the AVD VNet.

resource "azurerm_app_service_virtual_network_swift_connection" "nerdio" {
  app_service_id = var.app_service_id
  subnet_id      = var.app_integration_subnet_id
}

resource "azurerm_private_endpoint" "sql" {
  for_each            = var.sql_server_ids
  name                = "pe-${each.key}-sql"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.private_endpoint_subnet_id
  tags                = var.tags

  private_service_connection {
    name                           = "sql"
    private_connection_resource_id = each.value
    subresource_names              = ["sqlServer"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [var.private_dns_zone_ids["sql"]]
  }
}

resource "azurerm_private_endpoint" "vault" {
  for_each            = var.key_vault_ids
  name                = "pe-${each.key}-vault"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.private_endpoint_subnet_id
  tags                = var.tags

  private_service_connection {
    name                           = "vault"
    private_connection_resource_id = each.value
    subresource_names              = ["vault"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [var.private_dns_zone_ids["vault"]]
  }
}

resource "azurerm_private_endpoint" "blob" {
  for_each            = lookup(var.private_dns_zone_ids, "blob", null) != null ? var.storage_account_ids : {}
  name                = "pe-${each.key}-blob"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.private_endpoint_subnet_id
  tags                = var.tags

  private_service_connection {
    name                           = "blob"
    private_connection_resource_id = each.value
    subresource_names              = ["blob"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [var.private_dns_zone_ids["blob"]]
  }
}

resource "azurerm_private_endpoint" "automation" {
  for_each            = lookup(var.private_dns_zone_ids, "automation", null) != null ? var.automation_account_ids : {}
  name                = "pe-${each.key}-automation"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.private_endpoint_subnet_id
  tags                = var.tags

  private_service_connection {
    name                           = "automation"
    private_connection_resource_id = each.value
    subresource_names              = ["DSCAndHybridWorker"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [var.private_dns_zone_ids["automation"]]
  }
}

resource "azurerm_private_endpoint" "web" {
  count               = var.private_app_service ? 1 : 0
  name                = "pe-${element(split("/", var.app_service_id), 8)}-web"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.private_endpoint_subnet_id
  tags                = var.tags

  private_service_connection {
    name                           = "sites"
    private_connection_resource_id = var.app_service_id
    subresource_names              = ["sites"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [var.private_dns_zone_ids["web"]]
  }
}

locals {
  lockdown_ids = var.disable_public_access && var.lockdown_with_cli ? merge(
    { for k, id in var.sql_server_ids : "sql-${k}" => { id = id, kind = "sql" } },
    { for k, id in var.key_vault_ids : "kv-${k}" => { id = id, kind = "kv" } },
    { for k, id in var.storage_account_ids : "st-${k}" => { id = id, kind = "st" } },
    { for k, id in var.automation_account_ids : "aa-${k}" => { id = id, kind = "aa" } },
    var.private_app_service ? { "web" = { id = var.app_service_id, kind = "web" } } : {},
  ) : {}
}

resource "terraform_data" "disable_public_access" {
  for_each         = local.lockdown_ids
  triggers_replace = [each.value.id]

  provisioner "local-exec" {
    interpreter = ["bash", "-c"]
    command     = <<-EOT
      set -euo pipefail
      case "${each.value.kind}" in
        sql) az sql server update --ids "${each.value.id}" --enable-public-network false --output none ;;
        kv)  az keyvault update --ids "${each.value.id}" --public-network-access Disabled --output none ;;
        st)  az storage account update --ids "${each.value.id}" --public-network-access Disabled --output none ;;
        aa)  az resource update --ids "${each.value.id}" --set properties.publicNetworkAccess=false --output none ;;
        web) az resource update --ids "${each.value.id}" --set properties.publicNetworkAccess=Disabled --output none ;;
      esac
    EOT
  }

  depends_on = [
    azurerm_private_endpoint.sql,
    azurerm_private_endpoint.vault,
    azurerm_private_endpoint.blob,
    azurerm_private_endpoint.automation,
    azurerm_private_endpoint.web,
  ]
}
