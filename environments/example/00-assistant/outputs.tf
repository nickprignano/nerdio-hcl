output "url" {
  description = "Open this in your browser to start the guided setup."
  value       = module.assistant.url
}

output "github_setup_url" {
  description = "Open once to create the chat's GitHub App for the deploy pipeline. Null without the pipeline."
  value       = module.assistant.github_setup_url
}

output "claude_federation" {
  description = "What the Claude API federation rule matches (not secrets). ./nerdio assistant --connect-claude reads it."
  value       = module.assistant.claude_federation
}

output "model_provider" {
  description = "Which model the chat uses: claude-api, foundry or azure-openai (the default in Azure Government)."
  value       = module.assistant.model_provider
}
