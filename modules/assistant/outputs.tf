output "url" {
  description = "Open this to chat. Only members of the admin group can sign in."
  value       = local.app_url
}

output "foundry_resource" {
  description = "Foundry resource that serves the model."
  value       = azurerm_cognitive_account.foundry.name
}

output "github_setup_url" {
  description = "Open once to create the chat's GitHub App for the deploy pipeline. Null without the pipeline."
  value       = local.pipeline_enabled ? "${local.app_url}/setup/github" : null
}
