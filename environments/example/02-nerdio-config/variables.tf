variable "nme_base_url" {
  description = "Nerdio Manager URL (https://<app service>.azurewebsites.net)."
  type        = string
}

variable "nme_tenant_id" {
  description = "Entra tenant ID."
  type        = string
}

variable "nme_client_id" {
  description = "REST API client app ID."
  type        = string
}

variable "nme_scope" {
  description = "OAuth scope, api://<nerdio app id>/.default."
  type        = string
}

variable "nme_secret_source" {
  description = "How to get the REST client secret, from 01-platform's nme_secret_store: key_vault, openbao, or output (read NME_CLIENT_SECRET)."
  type        = string
  default     = "output"
  validation {
    condition     = contains(["key_vault", "openbao", "output"], var.nme_secret_source)
    error_message = "nme_secret_source must be \"key_vault\", \"openbao\" or \"output\"."
  }
  validation {
    condition     = var.nme_secret_source != "key_vault" || var.nme_key_vault != null
    error_message = "The key_vault hand-off needs nme_key_vault from 01-platform's nerdio_config_inputs."
  }
  validation {
    condition     = var.nme_secret_source != "openbao" || var.openbao != null
    error_message = "The openbao hand-off needs openbao from 01-platform's nerdio_config_inputs."
  }
}

variable "nme_key_vault" {
  description = "Key Vault ID and secret name holding the REST client secret (from 01-platform). Not secret."
  type = object({
    id          = string
    secret_name = string
  })
  default = null
}

variable "openbao" {
  description = "OpenBao address, login role and Entra scope (from 01-platform). Not secret."
  type = object({
    address = string
    role    = string
    scope   = string
  })
  default = null
}

variable "openbao_auth_mount" {
  description = "OpenBao login method: entra (Cloud Shell, an Entra token) or github (a GitHub Actions OIDC token)."
  type        = string
  default     = "entra"
  validation {
    condition     = contains(["entra", "github"], var.openbao_auth_mount)
    error_message = "openbao_auth_mount must be \"entra\" or \"github\"."
  }
}

variable "openbao_jwt" {
  description = "Short-lived token to log in to OpenBao. Set TF_VAR_openbao_jwt from az account get-access-token or the GitHub OIDC token; never put it in a file."
  type        = string
  default     = null
  sensitive   = true
  ephemeral   = true
}

variable "subscription_id" {
  description = "Subscription linked in Nerdio."
  type        = string
}

variable "location" {
  description = "Azure region for the AVD workspace."
  type        = string
}

variable "hostpools_resource_group_name" {
  description = "Resource group for AVD objects and session hosts."
  type        = string
}

variable "network" {
  description = "Session host network."
  type = object({
    resource_group_name = string
    vnet_name           = string
    subnet_name         = string
  })
}

variable "fslogix_profile_share_unc" {
  description = "FSLogix profile share UNC from 01-platform. Null skips the FSLogix profile."
  type        = string
  default     = null
}

variable "fslogix_entra_kerberos" {
  description = "Use Entra Kerberos for the profile share (matches identity_source = AADKERB in 01-platform)."
  type        = bool
  default     = true
}

variable "workspace" {
  description = "AVD workspace."
  type = object({
    name          = string
    friendly_name = optional(string)
    description   = optional(string)
  })
  default = {
    name          = "ws-avd"
    friendly_name = "Virtual Desktops"
  }
}

variable "ad_config_friendly_name" {
  description = "Directory profile name from the Nerdio setup wizard. Null uses Nerdio's default."
  type        = string
  default     = null
}

variable "auto_scale" {
  description = "Auto-scale profile settings (see modules/nerdio-config)."
  type        = any
  default     = {}
}

variable "host_pools" {
  description = "Dynamic host pools keyed by name (see modules/nerdio-config)."
  type        = any
  default     = {}
}
