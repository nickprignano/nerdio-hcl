variable "name_prefix" {
  description = "Short prefix for the Container Apps environment and runner job."
  type        = string
}

variable "location" {
  description = "Azure region for the Container Apps environment and runner job."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group where the VNet runner resources are created."
  type        = string
}

variable "infrastructure_subnet_id" {
  description = "Subnet ID inside the AVD VNet for the Container Apps Environment (/23 or larger, or /27 with workload profiles)."
  type        = string
}

variable "log_analytics_workspace_id" {
  description = "Log Analytics workspace resource ID for Container Apps logs."
  type        = string
}

variable "github_repo_url" {
  description = "Full HTTPS URL of the GitHub repository (for example, https://github.com/contoso/nerdio-hcl)."
  type        = string
}

variable "github_pat_key_vault_secret_id" {
  description = "Versionless Key Vault secret URI holding the GitHub App installation token or fine-grained PAT with Actions/Self-hosted runners access."
  type        = string
}

variable "key_vault_id" {
  description = "Resource ID of the Key Vault holding the GitHub runner secret."
  type        = string
}

variable "runner_image" {
  description = "Container image for the ephemeral GitHub Actions runner."
  type        = string
  default     = "ghcr.io/actions/actions-runner:latest"
}

variable "runner_labels" {
  description = "Labels registered by the ephemeral runner."
  type        = list(string)
  default     = ["self-hosted", "linux", "x64", "vnet"]
}

variable "max_executions" {
  description = "Maximum concurrent runner job executions."
  type        = number
  default     = 2
}

variable "tags" {
  description = "Tags applied to all resources."
  type        = map(string)
  default     = {}
}
