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

variable "model_provider" {
  description = <<-EOT
    Where the chat gets Claude: "claude-api" (the main path: the Claude API, signed in with the
    app's managed identity through workload identity federation; no API key) or "foundry"
    (Claude on Microsoft Foundry in this subscription, which needs Microsoft to grant quota).
    Both are keyless.
  EOT
  type        = string
  default     = "claude-api"
  validation {
    condition     = contains(["foundry", "claude-api"], var.model_provider)
    error_message = "model_provider must be foundry or claude-api."
  }
}

variable "foundry" {
  description = <<-EOT
    Microsoft Foundry resource that serves Claude, for model_provider = "foundry". location must be
    a region that offers Claude. With create_deployment = false, deploy the model in the Foundry
    portal and set deployment_name to it.
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
  default = null
  validation {
    condition     = var.model_provider != "foundry" || var.foundry != null
    error_message = "Set foundry (at least its location) when model_provider is foundry."
  }
}

variable "claude_api" {
  description = <<-EOT
    The Claude API, for model_provider = "claude-api". None of these are secrets: they name the
    Anthropic organization, the federation rule and the service account the app's identity is
    trusted as. `./nerdio assistant --connect-claude` creates them and fills them in; until then
    the app deploys but the chat says it isn't connected yet. workspace_id is needed only when the
    rule covers more than one workspace.
  EOT
  type = object({
    model              = optional(string, "claude-opus-5-5")
    organization_id    = optional(string)
    federation_rule_id = optional(string)
    service_account_id = optional(string)
    workspace_id       = optional(string)
  })
  default  = {}
  nullable = false
  validation {
    condition = (
      (var.claude_api.federation_rule_id == null || can(regex("^fdrl_[A-Za-z0-9]+$", var.claude_api.federation_rule_id))) &&
      (var.claude_api.service_account_id == null || can(regex("^svac_[A-Za-z0-9]+$", var.claude_api.service_account_id))) &&
      (var.claude_api.workspace_id == null || can(regex("^wrkspc_[A-Za-z0-9]+$", var.claude_api.workspace_id))) &&
      (var.claude_api.organization_id == null || can(regex("^[0-9a-fA-F-]{36}$", var.claude_api.organization_id)))
    )
    error_message = "claude_api IDs look like fdrl_..., svac_..., wrkspc_... and a UUID for the organization."
  }
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

variable "pipeline" {
  description = <<-EOT
    Connects the chat to the deploy pipeline (decision 0016, docs/pipeline.md), so it can save the
    answers, start a plan and read it back. storage_account_id and environment come from the
    00-pipeline stage; github.repository is owner/name. After deploying, open <url>/setup/github
    once to create the chat's GitHub App. Null keeps the chat paste-only.
  EOT
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
