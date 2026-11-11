output "url" {
  description = "Open this to chat. Only members of the admin group can sign in."
  value       = local.app_url
}

output "foundry_resource" {
  description = "Foundry resource that serves the model. Null with the Claude API."
  value       = local.use_foundry ? azurerm_cognitive_account.foundry[0].name : null
}

output "model_provider" {
  description = "Which model the chat uses: claude-api, foundry or azure-openai (the default in Azure Government)."
  value       = local.model_provider
}

output "azure_openai_resource" {
  description = "Azure OpenAI account that serves the chat, for model_provider = \"azure-openai\". Null otherwise."
  value       = local.use_azure_openai ? azurerm_cognitive_account.openai[0].name : null
}

output "claude_federation" {
  description = <<-EOT
    What the Claude API's federation rule must match, for model_provider = "claude-api": this
    tenant's Entra issuer, the audience app and the chat's managed identity. Not secrets.
    `./nerdio assistant --connect-claude` reads it. Null with Foundry.
  EOT
  value = local.use_claude_api ? {
    issuer_url = local.entra_issuer
    audience   = local.claude_audience
    object_id  = azurerm_user_assigned_identity.app.principal_id
    tenant_id  = var.tenant_id
    connected  = alltrue([for k in ["organization_id", "federation_rule_id", "service_account_id"] : var.claude_api[k] != null])
  } : null
}

output "github_setup_url" {
  description = "Open once to create the chat's GitHub App for the deploy pipeline. Null without the pipeline."
  value       = local.pipeline_enabled ? "${local.app_url}/setup/github" : null
}
