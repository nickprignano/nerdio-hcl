variable "tenant_id" {
  description = "Entra tenant ID. The bootstrap script reads it from az account show."
  type        = string
}

variable "subscription_id" {
  description = "Subscription the pipeline deploys into. The bootstrap script reads it from az account show."
  type        = string
}

variable "name" {
  description = "Short name for the pipeline's resources, for example nme-sbx."
  type        = string
}

variable "location" {
  description = "Azure region for the state storage and identities."
  type        = string
  default     = "eastus2"
}

variable "environment" {
  description = "Kit environment: the GitHub environments are <environment>-plan and <environment>-apply."
  type        = string
  default     = "sandbox"
}

variable "github" {
  description = "Repository the pipeline runs from, and the GitHub logins allowed to approve an apply."
  type = object({
    owner      = string
    repository = string
    reviewers  = list(string)
    branch     = optional(string, "main")
  })
}

variable "github_settings" {
  description = <<-EOT
    Repository settings the bootstrap manages. protect_branch adds a ruleset so the branch the
    apply trusts only changes through pull requests. actions_can_open_pull_requests lets the
    kb-feedback workflow open its pull request.
  EOT
  type = object({
    protect_branch                 = optional(bool, true)
    actions_can_open_pull_requests = optional(bool, true)
  })
  default = {}
}

variable "tags" {
  description = "Tags for every Azure resource."
  type        = map(string)
  default = {
    workload   = "avd"
    managed-by = "terraform"
  }
}
