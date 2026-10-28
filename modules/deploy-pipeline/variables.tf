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
    owner          = string
    repository     = string
    reviewers      = list(string)
    branch         = optional(string, "main")
    allow_pr_plans = optional(bool, false)
    runner_labels  = optional(list(string), ["ubuntu-latest"])
  })

  validation {
    condition     = length(var.github.reviewers) > 0
    error_message = "Name at least one reviewer; an apply must always need a person's approval."
  }
}

variable "plan_graph_roles" {
  description = "Microsoft Graph application roles for the plan identity. Read-only: Terraform refreshes Entra objects and the kit looks up groups by name."
  type        = list(string)
  nullable    = false # null (from the stage) means this default
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
  nullable    = false # null (from the stage) means this default
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
  nullable    = false # null (from the stage) means this default
  default     = ["Contributor", "Role Based Access Control Administrator"]
}

variable "apply_assignable_roles" {
  description = <<-EOT
    The only roles the apply identity may assign or remove, when apply_roles includes Role Based
    Access Control Administrator or User Access Administrator. Azure enforces it with a role
    assignment condition, so the identity can't grant Owner, User Access Administrator or any role
    the kit doesn't use. These are the roles the kit's stages assign. Add one here if you add a
    role assignment to the kit; an empty list removes the condition (not recommended).
  EOT
  type        = list(string)
  nullable    = false # null (from the stage) means this default
  default = [
    "Contributor",
    "Reader",
    "Backup Reader",
    "Website Contributor",
    "Cognitive Services User",
    "Key Vault Crypto Officer",
    "Key Vault Crypto User",
    "Key Vault Crypto Service Encryption User",
    "Key Vault Secrets Officer",
    "Key Vault Secrets User",
    "Key Vault Certificates Officer",
    "Key Vault Certificate User",
    "Storage Blob Data Contributor",
    "Storage Blob Data Reader",
    "Storage File Data SMB Share Contributor",
    "Storage File Data SMB Share Elevated Contributor",
  ]

  validation {
    condition     = length(setintersection(var.apply_assignable_roles, ["Owner", "User Access Administrator", "Role Based Access Control Administrator"])) == 0
    error_message = "The apply identity must not be able to hand out Owner or the role-assignment administrator roles."
  }
}

variable "plan_retention_days" {
  description = "Days to keep saved plans. They hold the values Terraform will apply, so they don't linger."
  type        = number
  default     = 7
}

variable "enable_resource_lock" {
  description = "Create a CanNotDelete management lock on the Terraform state storage account."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags for every Azure resource."
  type        = map(string)
  default     = {}
}
