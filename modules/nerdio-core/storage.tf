# Blob storage for the ASP.NET data protection key ring and Nerdio's deployment locks. Nerdio reads
# both as SAS URLs from Key Vault, so the account keeps shared keys enabled.

resource "azurerm_storage_account" "data_protection" {
  name                             = local.names.storage
  location                         = var.location
  resource_group_name              = var.resource_group_name
  account_tier                     = "Standard"
  account_replication_type         = "GRS"
  account_kind                     = "StorageV2"
  min_tls_version                  = "TLS1_2"
  https_traffic_only_enabled       = true
  allow_nested_items_to_be_public  = false
  cross_tenant_replication_enabled = false
  shared_access_key_enabled        = true
  public_network_access            = var.public_network_access_enabled ? "Enabled" : "Disabled"
  tags                             = var.tags

  network_rules {
    default_action = var.public_network_access_enabled ? "Allow" : "Deny"
    bypass         = ["AzureServices"]
  }
}

resource "azurerm_storage_container" "data_protection" {
  for_each              = toset([local.names.dp_container, local.names.locks_container])
  name                  = each.value
  storage_account_id    = azurerm_storage_account.data_protection.id
  container_access_type = "private"
}

# Fixed start and expiry keep the SAS stable between plans.
resource "time_static" "sas_start" {}

data "azurerm_storage_account_blob_container_sas" "data_protection" {
  for_each          = azurerm_storage_container.data_protection
  connection_string = azurerm_storage_account.data_protection.primary_connection_string
  container_name    = each.value.name
  https_only        = true
  start             = time_static.sas_start.rfc3339
  expiry            = timeadd(time_static.sas_start.rfc3339, "87600h")

  permissions {
    read   = true
    add    = false
    create = true
    write  = true
    delete = false
    list   = false
  }
}

locals {
  blob_endpoint = trimsuffix(azurerm_storage_account.data_protection.primary_blob_endpoint, "/")
  sas           = { for k, v in data.azurerm_storage_account_blob_container_sas.data_protection : k => trimprefix(v.sas, "?") }
}

resource "azurerm_key_vault_secret" "data_protection_path" {
  name         = "DataProtection--Storage--Path"
  key_vault_id = azurerm_key_vault.this.id
  value        = "${local.blob_endpoint}/${local.names.dp_container}/${local.names.dp_blob}?${local.sas[local.names.dp_container]}"
  content_type = "SAS URL"
  depends_on   = [time_sleep.key_vault_rbac]
}

resource "azurerm_key_vault_secret" "locks_container" {
  name         = "Deployment--LocksContainerSasUrl"
  key_vault_id = azurerm_key_vault.this.id
  value        = "${local.blob_endpoint}/${local.names.locks_container}?${local.sas[local.names.locks_container]}"
  content_type = "SAS URL"
  depends_on   = [time_sleep.key_vault_rbac]
}
