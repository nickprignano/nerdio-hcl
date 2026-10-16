variable "key_vault_name" {
  description = "Key Vault name (3 to 24 letters, digits and dashes, globally unique)."
  type        = string
  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9-]{1,22}[a-zA-Z0-9]$", var.key_vault_name))
    error_message = "key_vault_name must be 3 to 24 letters, digits and dashes, start with a letter and not end with a dash."
  }
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group for the Key Vault."
  type        = string
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}

variable "secret_name" {
  description = "Name of the Key Vault secret that holds the Nerdio REST API client secret."
  type        = string
  default     = "nme-rest-client-secret"
}

variable "secret_value" {
  description = "The Nerdio REST API client secret. Ephemeral: it is written with a write-only attribute, so this module never stores it in state."
  type        = string
  sensitive   = true
  ephemeral   = true
}

variable "secret_version" {
  description = "Number that changes whenever the secret is replaced (nerdio-identity's rest_api_client_secret_version). A new number rewrites the Key Vault secret."
  type        = number
}

variable "secret_expiration_date" {
  description = "Expiry of the secret (RFC 3339), copied onto the Key Vault secret so expiry shows in Azure. Null leaves it unset."
  type        = string
  default     = null
}

variable "reader_object_ids" {
  description = "Principals that may read the secret in stage 2 (users, groups or service principals). The identity running Terraform is always included."
  type        = list(string)
  default     = []
}

variable "github_oidc" {
  description = <<-EOT
    Optional. Creates a user-assigned identity that a GitHub Actions job in this repository and
    environment can sign in as with OIDC (no stored secret), and lets it read the secret.
    repository is "owner/name".
  EOT
  type = object({
    repository  = string
    environment = optional(string, "sandbox")
  })
  default = null
  validation {
    condition     = var.github_oidc == null || can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_oidc.repository))
    error_message = "github_oidc.repository must look like owner/name."
  }
}

variable "public_network_access_enabled" {
  description = "Allow the Key Vault's public endpoint (RBAC still applies). Cloud Shell and GitHub-hosted runners need it unless they reach the VNet."
  type        = bool
  default     = true
}

variable "purge_protection_enabled" {
  description = "Turn on purge protection. Safer for production, but the vault name stays reserved for the retention period after a destroy."
  type        = bool
  default     = false
}
