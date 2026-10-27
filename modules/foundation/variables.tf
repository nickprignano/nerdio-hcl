variable "prefix" {
  description = "Short naming prefix, e.g. \"contoso-nme\"."
  type        = string
}

variable "location" {
  description = "Azure region for all foundation resources."
  type        = string
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}

variable "resource_groups" {
  description = <<-EOT
    Resource groups to create, keyed by role. Nerdio recommends separating the
    Nerdio Manager core resources from host pools, storage and networking.
    The "nerdio" group must stay empty until the Marketplace template deploys into it.
  EOT
  type        = map(string)
  default = {
    nerdio     = "rg-nerdio-manager"
    network    = "rg-avd-network"
    hostpools  = "rg-avd-hostpools"
    storage    = "rg-avd-storage"
    monitoring = "rg-avd-monitoring"
  }
  validation {
    condition     = alltrue([for k in ["nerdio", "network", "hostpools", "storage", "monitoring"] : contains(keys(var.resource_groups), k)])
    error_message = "resource_groups must contain the keys nerdio, network, hostpools, storage and monitoring."
  }
}

variable "existing_resource_groups" {
  description = <<-EOT
    Role keys in resource_groups (for example ["nerdio"]) that already exist in Azure, such as a
    resource group created when deploying Nerdio Manager from the Azure portal Marketplace before
    running Terraform. Existing groups are read with a data source instead of created.
  EOT
  type        = set(string)
  default     = []
  validation {
    condition     = alltrue([for k in var.existing_resource_groups : contains(["nerdio", "network", "hostpools", "storage", "monitoring"], k)])
    error_message = "existing_resource_groups entries must be valid resource_groups role keys (nerdio, network, hostpools, storage, monitoring)."
  }
}

variable "log_analytics_retention_days" {
  description = "Retention for the AVD Log Analytics workspace."
  type        = number
  default     = 30
}

variable "create_log_analytics" {
  description = "Create a Log Analytics workspace for AVD Insights/host pool diagnostics. Nerdio can also create its own."
  type        = bool
  default     = true
}
