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
  value       = "\\\\${azurerm_storage_account.profiles.name}.file.core.windows.net\\${azurerm_storage_share.profiles.name}"
}
