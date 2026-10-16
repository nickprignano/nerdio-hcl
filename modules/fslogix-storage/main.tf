resource "azurerm_storage_account" "profiles" {
  name                            = var.name
  location                        = var.location
  resource_group_name             = var.resource_group_name
  account_kind                    = "FileStorage"
  account_tier                    = "Premium"
  account_replication_type        = "ZRS"
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  shared_access_key_enabled       = true # FSLogix setup and some Nerdio actions still use keys; disable once you're on identity-only access.
  public_network_access           = "Disabled"
  allow_nested_items_to_be_public = false
  tags                            = var.tags

  azure_files_authentication {
    directory_type                 = var.identity_source
    default_share_level_permission = "None"

    dynamic "active_directory" {
      for_each = var.identity_source == "AD" ? [var.active_directory] : []
      content {
        domain_name         = active_directory.value.domain_name
        domain_guid         = active_directory.value.domain_guid
        domain_sid          = active_directory.value.domain_sid
        forest_name         = active_directory.value.forest_name
        netbios_domain_name = active_directory.value.netbios_domain_name
        storage_sid         = active_directory.value.storage_sid
      }
    }
  }

  share_properties {
    smb {
      versions                        = ["SMB3.1.1"]
      authentication_types            = ["Kerberos"]
      kerberos_ticket_encryption_type = ["AES-256"]
      channel_encryption_type         = ["AES-256-GCM"]
    }
  }

  lifecycle {
    precondition {
      condition     = var.identity_source != "AD" || var.active_directory != null
      error_message = "active_directory must be set when identity_source is AD."
    }
  }
}

resource "azurerm_storage_share" "profiles" {
  name               = var.share_name
  storage_account_id = azurerm_storage_account.profiles.id
  quota              = var.share_quota_gb
  enabled_protocol   = "SMB"
}

resource "azurerm_private_endpoint" "file" {
  name                = "pe-${var.name}-file"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.private_endpoint_subnet_id
  tags                = var.tags

  private_service_connection {
    name                           = "file"
    private_connection_resource_id = azurerm_storage_account.profiles.id
    subresource_names              = ["file"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [var.private_dns_zone_id]
  }
}

resource "azurerm_role_assignment" "users" {
  for_each             = toset(var.user_group_object_ids)
  scope                = azurerm_storage_account.profiles.id
  role_definition_name = "Storage File Data SMB Share Contributor"
  principal_id         = each.value
}

resource "azurerm_role_assignment" "admins" {
  for_each             = toset(var.admin_group_object_ids)
  scope                = azurerm_storage_account.profiles.id
  role_definition_name = "Storage File Data SMB Share Elevated Contributor"
  principal_id         = each.value
}
