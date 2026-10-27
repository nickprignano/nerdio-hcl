# Customer-Managed Key (CMK) encryption for AVD session host OS disks and Nerdio Manager:
# - Dedicated RBAC Key Vault with purge protection (or an existing Key Vault)
# - RSA key with automatic rotation policy
# - Per-region Disk Encryption Sets (DES) in each workload region's hostpools resource group

data "azurerm_client_config" "current" {}

locals {
  compact_prefix = substr(replace(lower(var.prefix), "/[^a-z0-9]/", ""), 0, 12)
  suffix         = substr(sha1("${data.azurerm_client_config.current.subscription_id}/${var.resource_group_name}/${var.prefix}"), 0, 6)
  kv_name        = coalesce(var.key_vault_name, "kvcmk${local.compact_prefix}${local.suffix}")
  create_kv      = var.existing_key_vault_id == null
  key_vault_id   = local.create_kv ? azurerm_key_vault.cmk[0].id : var.existing_key_vault_id
  deployer       = coalesce(var.deployer_object_id, data.azurerm_client_config.current.object_id)
}

resource "azurerm_key_vault" "cmk" {
  count                      = local.create_kv ? 1 : 0
  name                       = local.kv_name
  location                   = var.control_plane_location
  resource_group_name        = var.resource_group_name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  soft_delete_retention_days = 90
  # Azure Disk Encryption Sets require both soft-delete and purge protection on the Key Vault.
  purge_protection_enabled = true
  tags                     = var.tags
}

resource "azurerm_role_assignment" "deployer_crypto" {
  count                = local.create_kv ? 1 : 0
  scope                = azurerm_key_vault.cmk[0].id
  role_definition_name = "Key Vault Crypto Officer"
  principal_id         = local.deployer
}

resource "time_sleep" "kv_rbac" {
  count           = local.create_kv ? 1 : 0
  create_duration = "60s"
  depends_on      = [azurerm_role_assignment.deployer_crypto]
}

resource "azurerm_key_vault_key" "cmk" {
  name         = var.key_name
  key_vault_id = local.key_vault_id
  key_type     = "RSA"
  key_size     = var.key_size
  key_opts     = ["decrypt", "encrypt", "sign", "unwrapKey", "verify", "wrapKey"]
  tags         = var.tags

  rotation_policy {
    automatic {
      time_before_expiry = "P30D"
    }
    expire_after         = var.rotation_period
    notify_before_expiry = "P29D"
  }

  depends_on = [time_sleep.kv_rbac]
}

resource "azurerm_disk_encryption_set" "regional" {
  for_each                  = var.regions
  name                      = "des-${var.prefix}-${each.key}"
  resource_group_name       = each.value.resource_group_name
  location                  = each.value.location
  key_vault_key_id          = azurerm_key_vault_key.cmk.versionless_id
  auto_key_rotation_enabled = true
  encryption_type           = "EncryptionAtRestWithCustomerKey"
  tags                      = var.tags

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_role_assignment" "des_crypto_user" {
  for_each             = azurerm_disk_encryption_set.regional
  scope                = local.key_vault_id
  role_definition_name = "Key Vault Crypto Service Encryption User"
  principal_id         = each.value.identity[0].principal_id
}
