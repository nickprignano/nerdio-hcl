output "url" {
  description = "Open this in your browser to start the guided setup."
  value       = module.assistant.url
}

output "github_key_vault_name" {
  description = "Where scripts/pipeline/github-app-key.sh imports the GitHub App's private key. Null without the pipeline."
  value       = module.assistant.github_key_vault_name
}
