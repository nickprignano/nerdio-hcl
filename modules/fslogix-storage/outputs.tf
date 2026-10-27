locals {
  file_suffix = var.cloud == "usgovernment" ? "file.core.usgovcloudapi.net" : "file.core.windows.net"
}

output "storage_account_id" {
  description = "Profile storage account ID."
  value       = azurerm_storage_account.profiles.id
}

output "storage_account_name" {
  description = "Profile storage account name, linked in Nerdio under Storage > Azure Files."
  value       = azurerm_storage_account.profiles.name
}

output "profile_share_unc" {
  description = "UNC path for the FSLogix VHDLocations setting."
  value       = "\\\\${azurerm_storage_account.profiles.name}.${local.file_suffix}\\${azurerm_storage_share.profiles.name}"
}

output "app_attach_share_unc" {
  description = "UNC path for the App Attach SMB share when app_attach_share_quota_gb is set, or null."
  value       = try("\\\\${azurerm_storage_account.profiles.name}.${local.file_suffix}\\${azurerm_storage_share.app_attach[0].name}", null)
}
