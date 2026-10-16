variable "name" {
  description = "Base name for the OpenBao resources, e.g. \"contoso-nme-bao\". Also the public DNS label, so keep it unique in the region."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,40}[a-z0-9]$", var.name))
    error_message = "name must be 3 to 42 lowercase letters, digits and dashes, starting with a letter."
  }
}

variable "key_vault_name" {
  description = "Name for OpenBao's own Key Vault (unseal key and TLS certificate). 3 to 24 characters, globally unique."
  type        = string
  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9-]{1,22}[a-zA-Z0-9]$", var.key_vault_name))
    error_message = "key_vault_name must be 3 to 24 letters, digits and dashes, start with a letter and not end with a dash."
  }
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group for OpenBao."
  type        = string
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}

variable "subscription_id" {
  description = "Subscription ID. The Azure secrets engine requires one in its config, even though it only manages app passwords here."
  type        = string
}

variable "virtual_network" {
  description = "Existing VNet to put OpenBao's subnet in."
  type = object({
    name                = string
    resource_group_name = string
  })
}

variable "subnet_cidr" {
  description = "CIDR for OpenBao's own small subnet, e.g. 10.50.4.64/28. Must be free inside the VNet."
  type        = string
  validation {
    condition     = can(cidrnetmask(var.subnet_cidr))
    error_message = "subnet_cidr must be a CIDR such as 10.50.4.64/28."
  }
}

variable "allowed_source_addresses" {
  description = <<-EOT
    Who may reach OpenBao's HTTPS port (8200): CIDRs, or the "Internet" service tag for
    GitHub-hosted runners and Cloud Shell, whose addresses change. Login still needs an Entra or
    GitHub token, and SSH is never opened. There's no default, so the choice is explicit.
  EOT
  type        = list(string)
  validation {
    condition     = length(var.allowed_source_addresses) > 0
    error_message = "List at least one address range, or [\"Internet\"]."
  }
}

variable "identity" {
  description = <<-EOT
    User-assigned identity for the VM, created by the caller so it can also be made an owner of
    the REST API client app (nerdio-identity's rest_api_client_extra_owner_object_ids) without a
    dependency cycle. It must be the VM's only identity: the Key Vault seal and the Azure plugin
    ask IMDS without naming one.
  EOT
  type = object({
    id           = string
    principal_id = string
    client_id    = string
  })
}

variable "rest_client_application_object_id" {
  description = "Object ID of the Nerdio REST API client app. OpenBao adds short-lived passwords to it; its identity must be an owner of the app (see nerdio-identity's rest_api_client_extra_owner_object_ids)."
  type        = string
}

variable "login_object_ids" {
  description = "Users or service principals (object IDs) allowed to sign in from Cloud Shell with an Entra token. The identity running Terraform is always included."
  type        = list(string)
  default     = []
}

variable "github_oidc" {
  description = "Optional. Lets GitHub Actions jobs in this repository and environment sign in with their OIDC token (audience \"openbao\"). repository is \"owner/name\"."
  type = object({
    repository  = string
    environment = optional(string, "sandbox")
  })
  default = null
  validation {
    condition     = var.github_oidc == null || can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_oidc.repository))
    error_message = "github_oidc.repository must look like owner/name."
  }
}

variable "credential_ttl" {
  description = "Lifetime of each minted Nerdio REST secret. It must outlast one plan or apply, because the nme provider refreshes its token with it."
  type        = string
  default     = "2h"
}

variable "vm_size" {
  description = "VM size. OpenBao needs little; the default is a 2 vCPU burstable size."
  type        = string
  default     = "Standard_B2als_v2"
}

variable "openbao_version" {
  description = "OpenBao release to install, with the SHA-256 of its linux_amd64 .deb from the release's checksums.txt. Update both together."
  type = object({
    version = string
    sha256  = string
  })
  default = {
    version = "2.7.1"
    sha256  = "aa5dd78f590a89256dffae7c7f8664b11e4380478da86454d8030020f6af0add"
  }
}

variable "azure_plugin_image" {
  description = "OCI image of OpenBao's Azure secrets plugin, pinned by digest so a moved tag can't change the binary."
  type        = string
  default     = "ghcr.io/openbao/openbao-plugin-secrets-azure:v0.23.0@sha256:14a7f04c4dc2379c9b90c2b4fc7c9c94e34eea10a69251df5f76be490a529566"
  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.azure_plugin_image))
    error_message = "Pin azure_plugin_image by digest (…@sha256:<64 hex characters>)."
  }
}

variable "certificate_validity_months" {
  description = "Validity of the self-signed TLS certificate. Key Vault renews it 30 days before expiry and the VM picks up the new one daily."
  type        = number
  default     = 12
}
