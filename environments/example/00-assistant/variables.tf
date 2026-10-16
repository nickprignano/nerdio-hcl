variable "tenant_id" {
  description = "Entra tenant. ./nerdio assistant reads it from az account show."
  type        = string
}

variable "subscription_id" {
  description = "Subscription the assistant runs in. ./nerdio assistant reads it from az account show."
  type        = string
}

variable "name" {
  description = "Base name for the assistant's resources."
  type        = string
  default     = "nme-assistant"
}

variable "location" {
  description = "Region for the app."
  type        = string
  default     = "eastus2"
}

variable "resource_group_name" {
  description = "Resource group to create for the assistant."
  type        = string
  default     = "rg-nme-assistant"
}

variable "admin_group" {
  description = "Display name of the Entra group whose members may use the assistant."
  type        = string
}

variable "image" {
  description = "Assistant container image. Pin a digest for production."
  type        = string
  default     = "ghcr.io/nickprignano/nerdio-hcl-assistant:main"
}

variable "foundry" {
  description = "Claude on Microsoft Foundry (see modules/assistant)."
  type = object({
    location          = optional(string, "eastus2")
    create_deployment = optional(bool, true)
    deployment_name   = optional(string, "claude-opus-5-5")
    model_name        = optional(string, "claude-opus-5-5")
    model_version     = optional(string)
    sku_name          = optional(string, "GlobalStandard")
    capacity          = optional(number, 50)
  })
  default = {}
}

variable "kit_repo_url" {
  description = "Repository the Cloud Shell commands clone (your fork, if you use one)."
  type        = string
  default     = "https://github.com/nickprignano/nerdio-hcl"
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default = {
    workload   = "nerdio-assistant"
    managed-by = "terraform"
  }
}
