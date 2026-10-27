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
  description = "Default subscription linked in Nerdio."
  type        = string
}

variable "control_plane_location" {
  description = "Azure region where Nerdio Manager's control plane is deployed (from 01-platform)."
  type        = string
  default     = "eastus2"
}

variable "regions" {
  description = "Workload regions to link in Nerdio Manager, keyed by region key (from 01-platform's nerdio_config_inputs)."
  type = map(object({
    location                      = string
    subscription_id               = optional(string)
    hostpools_resource_group_name = string
    network = object({
      resource_group_name = string
      vnet_name           = string
      subnet_name         = string
    })
    fslogix_profile_share_unc = optional(string)
    app_attach_share_unc      = optional(string)
    disk_encryption_set_id    = optional(string)
  }))
  validation {
    condition     = length(var.regions) >= 1
    error_message = "At least one region must be defined in regions."
  }
}

variable "fslogix_entra_kerberos" {
  description = "Use Entra Kerberos for the profile share (matches identity_source = AADKERB in 01-platform)."
  type        = bool
  default     = true
}

variable "fslogix_options" {
  description = "Extra FSLogix profile settings when regional fslogix_profile_share_unc or locations are set (cloud_cache, office_share_unc, set_as_default, redirections_xml, etc.)."
  type = object({
    name                     = optional(string, "Terraform FSLogix profile")
    locations                = optional(list(string), [])
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

variable "workspaces" {
  description = "AVD workspaces keyed by workspace key. Each workspace is placed in region_key (or the first sorted region when omitted). user_assignments assigns Entra user/group/SP object IDs to that specific workspace."
  type = map(object({
    name             = string
    region_key       = optional(string)
    friendly_name    = optional(string)
    description      = optional(string)
    user_assignments = optional(list(string), [])
  }))
  default = {
    default = {
      name          = "ws-avd"
      friendly_name = "Virtual Desktops"
    }
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
  description = "Entra user, group, or service principal object IDs to assign to the AVD workspaces."
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
    app_attach_packages = optional(map(object({
      name            = string
      image_path      = string
      package_name    = optional(string)
      version         = optional(string)
      certificate_id  = optional(string)
      host_pool_names = optional(list(string), [])
    })), {})
    desktop_images = optional(map(object({
      name                  = string
      resource_group        = string
      source_image          = string
      vm_size               = optional(string, "Standard_D4s_v5")
      storage_type          = optional(string, "StandardSSD_LRS")
      gallery_resource_id   = optional(string)
      replica_regions       = optional(list(string), [])
      scripted_action_ids   = optional(list(number), [])
      schedule_cron         = optional(string)
      staged_host_pool_keys = optional(list(string), [])
    })), {})
    remote_apps = optional(map(object({
      host_pool_name        = string
      resource_group        = optional(string)
      app_group_name        = optional(string)
      name                  = string
      friendly_name         = optional(string)
      description           = optional(string, "Managed by Terraform")
      file_path             = string
      command_line_setting  = optional(string, "DoNotAllow")
      required_command_line = optional(string, "")
      icon_path             = optional(string)
      icon_index            = optional(number, 0)
      show_in_portal        = optional(bool, true)
    })), {})
    uam_repositories = optional(map(object({
      name            = string
      repository_type = optional(string, "WinGet")
      url             = string
      trust_level     = optional(string, "Trusted")
    })), {})
    host_pool_reimage_schedules = optional(map(object({
      resource_group          = optional(string)
      is_enabled              = optional(bool, true)
      desktop_image_id        = string
      vm_size                 = optional(string)
      storage_type            = optional(string)
      schedule_cron           = string
      timezone_id             = optional(string, "Central Standard Time")
      batch_size              = optional(number, 2)
      failure_policy          = optional(string, "Abort")
      drain_mode_on_start     = optional(bool, true)
      user_notification_mins  = optional(number, 15)
      notification_message    = optional(string, "This desktop is scheduled for maintenance and will restart shortly.")
      staged_ring_delay_hours = optional(number, 0)
    })), {})
  })
  default = {}
}
