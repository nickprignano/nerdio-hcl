mock_provider "azurerm" {
  mock_data "azurerm_client_config" {
    defaults = {
      subscription_id = "00000000-0000-0000-0000-000000000000"
      tenant_id       = "11111111-1111-1111-1111-111111111111"
      object_id       = "22222222-2222-2222-2222-222222222222"
    }
  }
}

mock_provider "time" {}

variables {
  prefix                 = "contoso-nme"
  control_plane_location = "eastus2"
  resource_group_name    = "rg-contoso-nerdio"
  regions = {
    eastus2 = {
      location            = "eastus2"
      resource_group_name = "rg-contoso-eastus2-hostpools"
    }
    westeurope = {
      location            = "westeurope"
      resource_group_name = "rg-contoso-westeurope-hostpools"
    }
  }
}

run "creates_cmk_key_vault_and_regional_des" {
  command = plan

  assert {
    condition     = length(azurerm_key_vault.cmk) == 1 && azurerm_key_vault.cmk[0].purge_protection_enabled
    error_message = "CMK Key Vault must be created with purge protection enabled."
  }

  assert {
    condition     = length(azurerm_disk_encryption_set.regional) == 2 && length(azurerm_role_assignment.des_crypto_user) == 2
    error_message = "Each region should get its own Disk Encryption Set and Key Vault Crypto Service Encryption User role assignment."
  }
}

run "uses_existing_key_vault_when_provided" {
  command = plan

  variables {
    existing_key_vault_id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-sec/providers/Microsoft.KeyVault/vaults/kv-existing"
  }

  assert {
    condition     = length(azurerm_key_vault.cmk) == 0 && output.key_vault_id == "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-sec/providers/Microsoft.KeyVault/vaults/kv-existing"
    error_message = "When existing_key_vault_id is set, no new Key Vault should be created."
  }
}
