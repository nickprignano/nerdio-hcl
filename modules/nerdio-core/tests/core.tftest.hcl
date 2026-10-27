# Plan-only test with mocked providers: checks naming, wiring and the settings Nerdio reads,
# without an Azure tenant.

mock_provider "azurerm" {
  mock_data "azurerm_subscription" {
    defaults = {
      id           = "/subscriptions/00000000-0000-0000-0000-000000000000"
      display_name = "Example subscription"
    }
  }
  mock_data "azurerm_client_config" {
    defaults = {
      subscription_id = "00000000-0000-0000-0000-000000000000"
      tenant_id       = "11111111-1111-1111-1111-111111111111"
      object_id       = "22222222-2222-2222-2222-222222222222"
    }
  }
}

mock_provider "azuread" {
  mock_data "azuread_client_config" {
    defaults = {
      object_id = "22222222-2222-2222-2222-222222222222"
    }
  }
  mock_data "azuread_application_published_app_ids" {
    defaults = {
      result = { MicrosoftGraph = "00000003-0000-0000-c000-000000000000" }
    }
  }
}

mock_provider "azapi" {}

mock_provider "http" {
  mock_data "http" {
    defaults = {
      status_code = 200
    }
  }
}
mock_provider "time" {}

variables {
  resource_group_name = "rg-example-nerdio"
  location            = "eastus2"
  entra_app = {
    application_id              = "/applications/33333333-3333-3333-3333-333333333333"
    client_id                   = "44444444-4444-4444-4444-444444444444"
    service_principal_object_id = "55555555-5555-5555-5555-555555555555"
  }
  managed_resource_group_ids = {
    hostpools = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-example-hostpools"
  }
}

run "names_follow_nerdio_template" {
  command = plan

  assert {
    condition     = can(regex("^nmw-app-[0-9a-f]{13}$", azurerm_windows_web_app.this.name))
    error_message = "Web app name should be nmw-app-<13 character suffix>, as Nerdio's updater expects."
  }

  assert {
    condition     = azurerm_key_vault.this.name == replace(azurerm_windows_web_app.this.name, "nmw-app-", "nmw-app-kv-")
    error_message = "Nerdio's update script derives the web app name from the Key Vault name by removing -kv."
  }

  assert {
    condition     = length(azurerm_key_vault.this.name) <= 24 && length(azurerm_storage_account.data_protection.name) <= 24
    error_message = "Key Vault and storage names must fit in 24 characters."
  }
}

run "app_settings" {
  command = plan

  assert {
    condition     = azurerm_windows_web_app.this.app_settings["AzureAD:ClientId"] == var.entra_app.client_id
    error_message = "The web app should sign in as the Entra app."
  }

  assert {
    condition     = strcontains(azurerm_windows_web_app.this.app_settings["ConnectionStrings:DefaultConnection"], "Authentication=Active Directory Default")
    error_message = "SQL should use the web app's managed identity, not a password."
  }

  assert {
    condition     = azurerm_windows_web_app.this.app_settings["Deployment:SqlServerId"] == "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-example-nerdio/providers/Microsoft.Sql/servers/${azurerm_mssql_server.this.name}"
    error_message = "Deployment:SqlServerId should point at the SQL server."
  }

  assert {
    condition     = azurerm_mssql_server.this.azuread_administrator[0].azuread_authentication_only
    error_message = "SQL must use Entra authentication only."
  }
}

run "nerdio_rbac_is_scoped" {
  command = plan

  assert {
    condition     = toset(keys(azurerm_role_assignment.nerdio_app)) == toset(["contributor-nerdio", "contributor-hostpools", "reader", "backup-reader"])
    error_message = "Nerdio should get Contributor on its own and the managed resource groups only, plus Reader and Backup Reader on the subscription."
  }
}

run "private_mode" {
  command = plan

  variables {
    public_network_access_enabled = false
  }

  assert {
    condition     = !azurerm_key_vault.this.public_network_access_enabled && !azurerm_mssql_server.this.public_network_access_enabled && length(azurerm_mssql_firewall_rule.azure_services) == 0
    error_message = "Private mode should close Key Vault and SQL and drop the Azure services firewall rule."
  }
}

run "enterprise_ha_and_dr" {
  command = plan

  variables {
    dr_location              = "westus2"
    purge_protection_enabled = true
    enable_staging_slot      = true
    autoscale = {
      min_capacity = 1
      max_capacity = 3
    }
  }

  assert {
    condition     = length(azurerm_mssql_server.dr) == 1 && length(azurerm_mssql_failover_group.this) == 1
    error_message = "dr_location should create a partner SQL server and automatic failover group."
  }

  assert {
    condition     = azurerm_key_vault.this.purge_protection_enabled && length(azurerm_windows_web_app_slot.staging) == 1 && length(azurerm_monitor_autoscale_setting.plan) == 1
    error_message = "Enterprise HA should enable Key Vault purge protection, staging slot, and App Service Plan autoscale."
  }
}
