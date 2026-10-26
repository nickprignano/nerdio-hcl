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

variable "fslogix_options" {
  description = "Extra FSLogix profile settings when fslogix_profile_share_unc is set (cloud_cache, office_share_unc, set_as_default, redirections_xml, etc.)."
  type = object({
    name                     = optional(string, "Terraform FSLogix profile")
    office_share_unc         = optional(list(string), [])
    cloud_cache              = optional(bool, false)
    page_blobs               = optional(bool, false)
    profile_options          = optional(string, "")
    office_options           = optional(string, "")
    exclusion_mode           = optional(string, "None")
    excluded_domain_accounts = optional(list(string), [])
    set_as_default           = optional(bool, false)
    redirections_xml         = optional(string)
  })
  default = {}
}

variable "gallery_image_definition_ids" {
  description = "Compute Gallery image definition ARM IDs keyed by short name (from 01-platform)."
  type        = map(string)
  default     = {}
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
  description = "Dynamic host pools (Pooled or Personal) keyed by name (see modules/nerdio-config)."
  type        = any
  default     = {}
}

variable "static_host_pools" {
  description = "Static host pools (Pooled or Personal) keyed by name (see modules/nerdio-config)."
  type        = any
  default     = {}
}

variable "rdp_profiles" {
  description = "Host pool RDP profiles keyed by logical key (see modules/nerdio-config)."
  type        = any
  default     = {}
}

variable "default_rdp_profile_key" {
  description = "Logical key in rdp_profiles to set as Nerdio's default RDP profile."
  type        = string
  default     = null
}

variable "vm_deployment_profiles" {
  description = "Reusable VM deployment profiles keyed by logical key (see modules/nerdio-config)."
  type        = any
  default     = {}
}

variable "scripted_actions" {
  description = "Nerdio Windows scripted actions keyed by logical key (see modules/nerdio-config)."
  type        = any
  default     = {}
}

variable "scripted_action_groups" {
  description = "Nerdio scripted action groups keyed by logical key (see modules/nerdio-config)."
  type        = any
  default     = {}
}

variable "scripted_action_profiles" {
  description = "Host pool scripted action profiles keyed by logical key (see modules/nerdio-config)."
  type        = any
  default     = {}
}

variable "workspace_user_assignments" {
  description = "Entra user, group, or service principal object IDs to assign to the AVD workspace."
  type        = list(string)
  default     = []
}

variable "rest_gaps" {
  description = <<-EOT
    Optional Nerdio REST API configurations for endpoints not yet covered by the nerdio/nme
    provider (host pool user/group assignments, per-pool RDP profile & Shortpath overrides,
    Unified Application Management app groups, and Azure Files storage auto-scale).
    Leave empty to skip the REST gap-filler module.
  EOT
  type = object({
    host_pool_assignments = optional(map(object({
      resource_group = optional(string)
      users          = optional(list(string), [])
      groups         = optional(list(string), [])
      app_groups     = optional(list(string), [])
    })), {})
    host_pool_rdp = optional(map(object({
      resource_group     = optional(string)
      configuration_name = optional(string)
      rdp_properties     = optional(string)
      short_path = optional(object({
        managed_private_udp = optional(string, "Default")
        direct_udp          = optional(string, "Default")
        public_udp          = optional(string, "Default")
        relay_udp           = optional(string, "Default")
      }))
    })), {})
    uam_app_groups = optional(map(object({
      name = string
      items = list(object({
        repo_id         = number
        external_id     = string
        version         = optional(string, "")
        cached_name     = optional(string, "")
        reboot          = optional(bool, false)
        on_upgrade_fail = optional(string, "Reinstall")
      }))
    })), {})
    azure_files_autoscale = optional(map(object({
      resource_group     = string
      account_name       = string
      share_name         = string
      link_share         = optional(bool, true)
      is_enabled         = optional(bool, true)
      unit               = optional(string, "SizeGb")
      min_quota_buffer   = optional(number, 10)
      max_quota_buffer   = optional(number, 100)
      max_quota_limit_gb = optional(number, 102400)
      scaling = optional(object({
        trigger               = optional(string, "AvgSuccessServerLatency")
        scale_out_by          = optional(number, 10)
        scale_out_high_lat    = optional(number, 20)
        scale_out_interval    = optional(number, 5)
        scale_in_by           = optional(number, 20)
        scale_in_low_lat      = optional(number, 10)
        scale_in_interval     = optional(number, 15)
        transaction_threshold = optional(number, 100)
      }), {})
    })), {})
  })
  default = {}
}
