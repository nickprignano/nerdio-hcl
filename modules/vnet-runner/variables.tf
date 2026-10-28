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
  description = "Optional versionless Key Vault secret URI holding a fine-grained PAT with Actions/Self-hosted runners access (set either this or github_app)."
  type        = string
  default     = null

  validation {
    condition     = var.github_pat_key_vault_secret_id != null || var.github_app != null
    error_message = "Set either github_pat_key_vault_secret_id or github_app."
  }
}

variable "github_app" {
  description = "Optional GitHub App credentials (recommended for enterprise over a PAT). private_key_key_vault_secret_id is the versionless Key Vault secret URI holding the PEM private key."
  type = object({
    application_id                  = string
    installation_id                 = string
    private_key_key_vault_secret_id = string
  })
  default = null
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
