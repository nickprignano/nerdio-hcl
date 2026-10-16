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
