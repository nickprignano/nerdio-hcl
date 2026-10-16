variable "name" {
  description = "Base name for the assistant's resources, e.g. \"nme-assistant\"."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,20}[a-z0-9]$", var.name))
    error_message = "Use 4-22 lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "location" {
  description = "Region for the Container App and its logs."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group the assistant lives in (created by the caller)."
  type        = string
}

variable "tenant_id" {
  description = "Entra tenant users sign in from."
  type        = string
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}

variable "image" {
  description = "Container image for the assistant. Pin a digest (…@sha256:…) for production."
  type        = string
}

variable "admin_group_object_id" {
  description = "Entra group whose members may sign in. Nobody else can open the app."
  type        = string
}

variable "foundry" {
  description = <<-EOT
    Microsoft Foundry resource that serves Claude. location must be a region that offers Claude.
    With create_deployment = false, deploy the model in the Foundry portal and set deployment_name to it.
  EOT
  type = object({
    location          = string
    create_deployment = optional(bool, true)
    deployment_name   = optional(string, "claude-opus-5-5")
    model_name        = optional(string, "claude-opus-5-5")
    model_version     = optional(string)
    sku_name          = optional(string, "GlobalStandard")
    capacity          = optional(number, 50)
  })
}

variable "effort" {
  description = "Model effort: low, medium or high. Medium suits a guided interview."
  type        = string
  default     = "medium"
  validation {
    condition     = contains(["low", "medium", "high"], var.effort)
    error_message = "effort must be low, medium or high."
  }
}

variable "kit_repo_url" {
  description = "Repository the Cloud Shell commands clone (your fork, if you use one)."
  type        = string
  default     = "https://github.com/nickprignano/nerdio-hcl"
}

variable "max_replicas" {
  description = "Most copies of the app to run. It scales to zero when nobody is chatting."
  type        = number
  default     = 2
}
