output "volume_id" {
  description = "Azure NetApp Files volume ID."
  value       = azurerm_netapp_volume.profiles.id
}

output "profile_share_unc" {
  description = "UNC path for the ANF SMB volume."
  value       = "\\\\${azurerm_netapp_account.this.name}\\${azurerm_netapp_volume.profiles.volume_path}"
}
