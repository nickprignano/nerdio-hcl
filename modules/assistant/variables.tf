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
    Where the chat gets its model. Unset (the default) picks by cloud: "claude-api" in commercial
    Azure, "azure-openai" in Azure Government.
    - "claude-api": the Claude API, signed in with the app's managed identity through workload
      identity federation; no API key (decision 0020).
    - "foundry": Claude on Microsoft Foundry in this subscription, which needs Microsoft to grant quota.
    - "azure-openai": an Azure OpenAI deployment in this tenant, called with the app's managed
      identity (decision 0036). The only choice in Azure Government, where Claude isn't offered
      and everything stays in the Government tenant.
    All three are keyless.
  EOT
  type        = string
  default     = null
  validation {
    condition     = var.model_provider == null || contains(["foundry", "claude-api", "azure-openai"], coalesce(var.model_provider, "unset"))
    error_message = "model_provider must be claude-api, foundry or azure-openai."
  }
  validation {
    condition     = var.cloud == "public" || var.model_provider == null || var.model_provider == "azure-openai"
    error_message = "In Azure Government the chat must use azure-openai: Claude isn't offered there, and a Government deployment keeps everything in the Government tenant (decision 0036). Leave model_provider unset."
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
    condition     = coalesce(var.model_provider, "unset") != "foundry" || var.foundry != null
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

variable "azure_openai" {
  description = <<-EOT
    Azure OpenAI for model_provider = "azure-openai" (decision 0036). location defaults to the app's
    region; in Azure Government it must be usgovvirginia or usgovarizona. The default model,
    gpt-4.1 (2025-04-14) on a regional Standard deployment, is offered in both Government regions.
    capacity is in thousands of tokens per minute. Set reasoning_effort (low, medium or high) only
    for a reasoning model such as o3-mini or gpt-5.1. With create_deployment = false, deploy the
    model yourself and set deployment_name to it.
  EOT
  type = object({
    location          = optional(string)
    create_deployment = optional(bool, true)
    deployment_name   = optional(string, "chat")
    model_name        = optional(string, "gpt-4.1")
    model_version     = optional(string, "2025-04-14")
    sku_name          = optional(string, "Standard")
    capacity          = optional(number, 50)
    api_version       = optional(string, "2024-10-21")
    reasoning_effort  = optional(string)
  })
  default  = {}
  nullable = false
  validation {
    condition     = var.azure_openai.reasoning_effort == null || contains(["minimal", "low", "medium", "high"], coalesce(var.azure_openai.reasoning_effort, "unset"))
    error_message = "azure_openai.reasoning_effort must be minimal, low, medium or high (or unset for a non-reasoning model)."
  }
  validation {
    condition     = contains(["Standard", "DataZoneStandard", "ProvisionedManaged", "DataZoneProvisionedManaged"], var.azure_openai.sku_name)
    error_message = "azure_openai.sku_name must be Standard, DataZoneStandard, ProvisionedManaged or DataZoneProvisionedManaged. Global deployments would leave the Government boundary."
  }
  validation {
    condition = var.cloud == "public" || contains(["usgovvirginia", "usgovarizona"],
    lower(replace(coalesce(var.azure_openai.location, var.location), " ", "")))
    error_message = "In Azure Government, Azure OpenAI runs in usgovvirginia or usgovarizona. Set azure_openai.location (or the app's location) to one of them."
  }
}

variable "effort" {
  description = "Model effort: low, medium, high, xhigh or max. Medium suits a guided interview (decision 0022); raise it before changing the model."
  type        = string
  default     = "medium"
  validation {
    condition     = contains(["low", "medium", "high", "xhigh", "max"], var.effort)
    error_message = "effort must be low, medium, high, xhigh or max."
  }
}

variable "kit_repo_url" {
  description = "Repository the Cloud Shell commands clone (your fork, if you use one)."
  type        = string
  default     = "https://github.com/nickprignano/nme-automation"
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

variable "cloud" {
  description = "Azure cloud environment: public (AzureCloud) or usgovernment (AzureUSGovernment, which GCC High tenants use). Decision 0034."
  type        = string
  default     = "public"

  validation {
    condition     = contains(["public", "usgovernment"], var.cloud)
    error_message = "cloud must be public or usgovernment."
  }
}
