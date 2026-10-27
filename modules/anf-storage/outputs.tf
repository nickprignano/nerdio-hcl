output "volume_id" {
  description = "Azure NetApp Files volume ID."
  value       = azurerm_netapp_volume.profiles.id
}

output "profile_share_unc" {
  description = "UNC path for the ANF SMB volume."
  value       = "\\\\${try(azurerm_netapp_volume.profiles.mount_ip_addresses[0], "anf-${var.prefix}")}\\${var.volume_path}"
}
