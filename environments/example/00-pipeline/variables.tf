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

variable "answers_file" {
  description = "Path to the ./nerdio answers to publish for the pipeline (written by the bootstrap script). Null leaves them unset."
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags for every Azure resource."
  type        = map(string)
  default = {
    workload   = "avd"
    managed-by = "terraform"
  }
}
