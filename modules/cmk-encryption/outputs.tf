output "key_vault_id" {
  description = "ARM resource ID of the Key Vault holding the Customer-Managed Key."
  value       = local.key_vault_id
}

output "key_vault_key_id" {
  description = "Versionless Key Vault key ID used by the Disk Encryption Sets."
  value       = azurerm_key_vault_key.cmk.versionless_id
}

output "disk_encryption_set_ids" {
  description = "Regional Disk Encryption Set ARM IDs keyed by region key."
  value       = { for k, des in azurerm_disk_encryption_set.regional : k => des.id }
}
