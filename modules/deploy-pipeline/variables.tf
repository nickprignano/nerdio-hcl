variable "name" {
  description = "Short name used in every resource name, for example nme-sbx. One per environment."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,14}$", var.name))
    error_message = "Use 2 to 15 lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "location" {
  description = "Azure region for the state storage and the deploy identities."
  type        = string
}

variable "subscription_id" {
  description = "Subscription the pipeline deploys into. Its roles are scoped here."
  type        = string
}

variable "tenant_id" {
  description = "Entra tenant of the subscription."
  type        = string
}

variable "environment" {
  description = "Kit environment name, such as sandbox, dev or prod. The GitHub environments are <environment>-plan and <environment>-apply."
  type        = string
  default     = "sandbox"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,20}$", var.environment))
    error_message = "Use lowercase letters, digits or hyphens."
  }
}

variable "github" {
  description = <<-EOT
    The repository the pipeline runs from. reviewers are the GitHub logins allowed to approve an
    apply; at least one is required. branch is the only branch that can use either environment,
    so a pull request branch can never get a token for this subscription.
  EOT
  type = object({
    owner      = string
    repository = string
    reviewers  = list(string)
    branch     = optional(string, "main")
  })

  validation {
    condition     = length(var.github.reviewers) > 0
    error_message = "Name at least one reviewer; an apply must always need a person's approval."
  }
}

variable "plan_graph_roles" {
  description = "Microsoft Graph application roles for the plan identity. Read-only: Terraform refreshes Entra objects and the kit looks up groups by name."
  type        = list(string)
  default     = ["Directory.Read.All"]
}

variable "apply_graph_roles" {
  description = <<-EOT
    Microsoft Graph application roles for the apply identity: what stage 1 needs to create
    Nerdio's app registrations, the SQL admin group and the admin consent grants. These are
    tenant-wide and powerful, which is why only an approved run can use this identity. Drop
    AppRoleAssignment.ReadWrite.All and DelegatedPermissionGrant.ReadWrite.All if you grant
    consent yourself (grant_admin_consent = false).
  EOT
  type        = list(string)
  default = [
    "Application.ReadWrite.All",
    "AppRoleAssignment.ReadWrite.All",
    "DelegatedPermissionGrant.ReadWrite.All",
    "Group.ReadWrite.All",
    "Directory.Read.All",
  ]
}

variable "apply_roles" {
  description = "Azure roles for the apply identity on the subscription. The kit creates role assignments, so it needs one of the RBAC administrator roles alongside Contributor."
  type        = list(string)
  default     = ["Contributor", "Role Based Access Control Administrator"]
}

variable "plan_retention_days" {
  description = "Days to keep saved plans. They hold the values Terraform will apply, so they don't linger."
  type        = number
  default     = 7
}

variable "tags" {
  description = "Tags for every Azure resource."
  type        = map(string)
  default     = {}
}
