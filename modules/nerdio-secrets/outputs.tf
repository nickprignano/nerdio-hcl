output "key_vault_id" {
  description = "Key Vault resource ID. Stage 2 reads the secret from here."
  value       = azurerm_key_vault.this.id
}

output "secret_name" {
  description = "Name of the secret that holds the Nerdio REST API client secret."
  value       = azurerm_key_vault_secret.rest_client.name
}

output "github_client_id" {
  description = "Client ID for azure/login or ARM_CLIENT_ID in the GitHub environment, or null. Not a secret."
  value       = try(azurerm_user_assigned_identity.github[0].client_id, null)
}
