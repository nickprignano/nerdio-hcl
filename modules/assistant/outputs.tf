output "url" {
  description = "Open this to chat. Only members of the admin group can sign in."
  value       = local.app_url
}

output "foundry_resource" {
  description = "Foundry resource that serves the model."
  value       = azurerm_cognitive_account.foundry.name
}
