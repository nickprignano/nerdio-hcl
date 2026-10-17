output "url" {
  description = "Open this to chat. Only members of the admin group can sign in."
  value       = local.app_url
}

output "foundry_resource" {
  description = "Foundry resource that serves the model."
  value       = azurerm_cognitive_account.foundry.name
}

output "github_key_vault_name" {
  description = "Key Vault to import the GitHub App's private key into (scripts/pipeline/github-app-key.sh). Null without the pipeline."
  value       = one(azurerm_key_vault.github[*].name)
}
