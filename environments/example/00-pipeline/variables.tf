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

variable "access" {
  description = <<-EOT
    What the pipeline's identities may do, for tenants with strict access rules. Leave a field
    out to keep the kit's default; docs/access.md lists each one and why the kit needs it.
      apply_roles            Azure roles for the apply identity on the subscription
      apply_assignable_roles the only roles it may assign (Azure enforces this with a condition)
      apply_graph_roles      Microsoft Graph roles for the apply identity
      plan_graph_roles       Microsoft Graph roles for the read-only plan identity
  EOT
  type = object({
    apply_roles            = optional(list(string))
    apply_assignable_roles = optional(list(string))
    apply_graph_roles      = optional(list(string))
    plan_graph_roles       = optional(list(string))
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
