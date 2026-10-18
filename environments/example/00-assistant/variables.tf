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

variable "model_provider" {
  description = <<-EOT
    Where the chat gets Claude: "claude-api" (the Claude API through workload identity federation,
    the main path) or "foundry" (Claude on Microsoft Foundry, if Microsoft grants you quota).
    ./nerdio assistant --model-provider sets it.
  EOT
  type        = string
  default     = "claude-api"
}

variable "effort" {
  description = "Model effort for the chat: low, medium, high, xhigh or max (see modules/assistant)."
  type        = string
  default     = "medium"
}

variable "claude_api" {
  description = "The Claude API's federation IDs (see modules/assistant). ./nerdio assistant --connect-claude fills them in."
  type = object({
    model              = optional(string, "claude-opus-5-5")
    organization_id    = optional(string)
    federation_rule_id = optional(string)
    service_account_id = optional(string)
    workspace_id       = optional(string)
  })
  default  = {}
  nullable = false
}

variable "foundry" {
  description = "Claude on Microsoft Foundry, for model_provider = \"foundry\" (see modules/assistant)."
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

variable "pipeline" {
  description = "Connects the chat to the deploy pipeline (see modules/assistant). ./nerdio assistant --pipeline fills it in."
  type = object({
    storage_account_id = string
    environment        = string
    github = object({
      repository = string
      branch     = optional(string, "main")
    })
  })
  default = null
}
