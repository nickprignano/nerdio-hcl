# Entra-only SQL. Nerdio's template makes the app connect as the SQL server admin through a
# generated login and password. Here the admin is an Entra group whose only members are the
# Nerdio web app's managed identity and the Nerdio service principal: the same rights, with no password.

data "azuread_client_config" "current" {}

resource "azuread_group" "sql_admins" {
  display_name     = local.names.sql_admins
  description      = "Entra admin of the Nerdio Manager SQL server. Members: the Nerdio web app identity and the Nerdio app."
  security_enabled = true
  owners           = [coalesce(var.deployer_object_id, data.azuread_client_config.current.object_id)]
  members = concat(
    [
      azurerm_windows_web_app.this.identity[0].principal_id,
      var.entra_app.service_principal_object_id,
    ],
    var.enable_staging_slot ? [azurerm_windows_web_app_slot.staging[0].identity[0].principal_id] : [],
  )
}

resource "azurerm_mssql_server" "this" {
  name                          = local.names.sql_server
  location                      = var.location
  resource_group_name           = var.resource_group_name
  version                       = "12.0"
  minimum_tls_version           = "1.2"
  public_network_access_enabled = var.public_network_access_enabled
  tags                          = merge(var.tags, { displayName = "SqlServer" })

  azuread_administrator {
    login_username              = azuread_group.sql_admins.display_name
    object_id                   = azuread_group.sql_admins.object_id
    tenant_id                   = data.azurerm_client_config.current.tenant_id
    azuread_authentication_only = true
  }

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_mssql_database" "this" {
  name        = local.names.database
  server_id   = azurerm_mssql_server.this.id
  collation   = "SQL_Latin1_General_CP1_CI_AS"
  sku_name    = var.database_sku
  max_size_gb = var.database_max_size_gb
  tags        = merge(local.paas_tags, { displayName = "Database" })
}

# Same rule as Nerdio's template; the private endpoint in modules/nerdio-hardening replaces it.
resource "azurerm_mssql_firewall_rule" "azure_services" {
  count            = var.public_network_access_enabled ? 1 : 0
  name             = "AllowAllWindowsAzureIps"
  server_id        = azurerm_mssql_server.this.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# Microsoft's minimum Graph roles for a SQL server identity that resolves group and
# service principal logins.
data "azuread_application_published_app_ids" "well_known" {}

data "azuread_service_principal" "msgraph" {
  client_id = data.azuread_application_published_app_ids.well_known.result["MicrosoftGraph"]
}

resource "azuread_app_role_assignment" "sql_identity" {
  for_each            = var.grant_admin_consent ? toset(["User.Read.All", "GroupMember.Read.All", "Application.Read.All"]) : toset([])
  app_role_id         = data.azuread_service_principal.msgraph.app_role_ids[each.value]
  principal_object_id = azurerm_mssql_server.this.identity[0].principal_id
  resource_object_id  = data.azuread_service_principal.msgraph.object_id
}

resource "azurerm_mssql_server" "dr" {
  count                         = var.dr_location != null ? 1 : 0
  name                          = local.names.sql_server_dr
  location                      = var.dr_location
  resource_group_name           = var.resource_group_name
  version                       = "12.0"
  minimum_tls_version           = "1.2"
  public_network_access_enabled = var.public_network_access_enabled
  tags                          = merge(var.tags, { displayName = "SqlServerDR" })

  azuread_administrator {
    login_username              = azuread_group.sql_admins.display_name
    object_id                   = azuread_group.sql_admins.object_id
    tenant_id                   = data.azurerm_client_config.current.tenant_id
    azuread_authentication_only = true
  }

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_mssql_firewall_rule" "azure_services_dr" {
  count            = var.dr_location != null && var.public_network_access_enabled ? 1 : 0
  name             = "AllowAllWindowsAzureIps"
  server_id        = azurerm_mssql_server.dr[0].id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

resource "azuread_app_role_assignment" "sql_dr_identity" {
  for_each            = var.dr_location != null && var.grant_admin_consent ? toset(["User.Read.All", "GroupMember.Read.All", "Application.Read.All"]) : toset([])
  app_role_id         = data.azuread_service_principal.msgraph.app_role_ids[each.value]
  principal_object_id = azurerm_mssql_server.dr[0].identity[0].principal_id
  resource_object_id  = data.azuread_service_principal.msgraph.object_id
}

resource "azurerm_mssql_failover_group" "this" {
  count     = var.dr_location != null ? 1 : 0
  name      = local.names.sql_failover
  server_id = azurerm_mssql_server.this.id
  databases = [azurerm_mssql_database.this.id]
  tags      = local.paas_tags

  partner_server {
    id = azurerm_mssql_server.dr[0].id
  }

  read_write_endpoint_failover_policy {
    mode          = "Automatic"
    grace_minutes = 60
  }
}
