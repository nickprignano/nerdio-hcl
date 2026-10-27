variable "subscription_id" {
  description = "Default subscription linked to Nerdio Manager during the setup wizard."
  type        = string
}

variable "regions" {
  description = "Workload regions to link in Nerdio Manager, keyed by region key (e.g. eastus2, westeurope)."
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

variable "workspaces" {
  description = "AVD workspaces created through Nerdio, keyed by workspace key. Each workspace is placed in region_key (or the first sorted region when omitted). user_assignments assigns Entra user/group/SP object IDs to that specific workspace."
  type = map(object({
    name             = string
    region_key       = optional(string)
    friendly_name    = optional(string)
    description      = optional(string)
    user_assignments = optional(list(string), [])
  }))
  validation {
    condition     = length(var.workspaces) >= 1
    error_message = "At least one workspace must be defined in workspaces."
  }
}

variable "ad_config_friendly_name" {
  description = "Friendly name of the directory profile created in the Nerdio setup wizard. Null uses Nerdio's default."
  type        = string
  default     = null
}

variable "fslogix" {
  description = "FSLogix profile configuration. Null skips it. Supports single-share, per-region shares, or multi-share Cloud Cache across regions."
  type = object({
    name                     = optional(string, "Terraform FSLogix profile")
    profile_share_unc        = optional(string)
    locations                = optional(list(string), [])
    office_share_unc         = optional(list(string), [])
    entra_id_kerberos        = optional(bool, true)
    cloud_cache              = optional(bool, false)
    page_blobs               = optional(bool, false)
    profile_options          = optional(string, "")
    office_options           = optional(string, "")
    exclusion_mode           = optional(string, "None")
    excluded_domain_accounts = optional(list(string), [])
    set_as_default           = optional(bool, false)
    redirections_xml         = optional(string)
  })
  default = null
}

variable "auto_scale" {
  description = "Default-mode auto-scale profile shared by the host pools unless a pool sets auto_scale_profile_id. Supports CPU, RAM, and AvailableUserSessions triggers plus rolling drain mode windows."
  type = object({
    name                   = optional(string, "Terraform default scaling")
    max_sessions_per_host  = optional(number, 10)
    load_balancing         = optional(string, "BreadthFirst")
    host_pool_capacity     = optional(number, 4)
    min_active_hosts_count = optional(number, 1)
    burst_capacity         = optional(number, 2)
    scale_out_cpu_percent  = optional(number, 80)
    scale_in_cpu_percent   = optional(number, 20)
    scale_out_ram_percent  = optional(number)
    scale_in_ram_percent   = optional(number)
    available_sessions = optional(object({
      min_available_user_sessions   = number
      max_available_user_sessions   = number
      available_session_restriction = optional(string, "Always")
      outside_work_hours_sessions   = optional(number)
      end_work_hours                = optional(string)
    }))
    rolling_drain_mode = optional(object({
      is_enabled = optional(bool, false)
      windows = optional(list(object({
        name                    = string
        start_time              = string
        percent                 = number
        load_balancing          = optional(string, "DepthFirst")
        scale_in_aggressiveness = optional(string, "High")
      })), [])
    }), {})
    start_vm_on_connect     = optional(bool, true)
    active_host_type        = optional(string, "Running")
    scale_in_aggressiveness = optional(string, "Medium")
    minutes_before_remove   = optional(number, 10)
    scale_in_message        = optional(string, "This session host is being shut down. Please save your work and sign out.")
    auto_heal_enabled       = optional(bool, false)
  })
  default = {}
}

variable "gallery_image_definition_ids" {
  description = "Compute Gallery image definition ARM IDs keyed by short name (from 01-platform). Host pools can set image to a key here or to a full Marketplace/Gallery ID."
  type        = map(string)
  default     = {}
}

variable "host_pools" {
  description = <<-EOT
    Dynamic host pools (Pooled or Personal), keyed by AVD host pool name.
    region_key selects the entry in var.regions (defaults to the first sorted region key).
    workspace_key selects the entry in var.workspaces (defaults to the first sorted workspace key).
    image may be a key in gallery_image_definition_ids, a Compute Gallery image definition ARM ID
    (/subscriptions/.../galleries/<gal>/images/<def>), or a Marketplace path like
    MicrosoftWindowsDesktop/office-365/win11-24h2-avd-m365/latest.
  EOT
  type = map(object({
    friendly_name                = string
    description                  = optional(string, "Managed by Terraform")
    region_key                   = optional(string)
    workspace_key                = optional(string)
    host_pool_type               = optional(string, "Pooled")
    assignment_type              = optional(string, "Automatic")
    app_group_type               = optional(string, "Desktop")
    app_group_name               = optional(string)
    load_balancer                = optional(string)
    max_session_limit            = optional(number, 10)
    validation_env               = optional(bool, false)
    start_vm_on_connect          = optional(bool, true)
    timezone_id                  = optional(string, "Central Standard Time")
    auto_scale_enabled           = optional(bool, true)
    auto_scale_profile_id        = optional(string)
    vm_prefix                    = string
    vm_size                      = optional(string, "Standard_D4s_v5")
    image                        = optional(string, "MicrosoftWindowsDesktop/office-365/win11-24h2-avd-m365/latest")
    os_disk_type                 = optional(string, "StandardSSD_LRS")
    os_disk_size_gb              = optional(number, 128)
    disk_performance_tier        = optional(string)
    has_ephemeral_os_disk        = optional(bool, false)
    ephemeral_os_disk_placement  = optional(string)
    max_idle_minutes             = optional(number, 60)
    max_disconnected             = optional(number, 120)
    max_connection_minutes       = optional(number)
    remote_app_logoff_minutes    = optional(number)
    fslogix_enabled              = optional(bool)
    fslogix_profile_id           = optional(string)
    scripted_action_profile_id   = optional(string)
    scripted_action_profile_key  = optional(string)
    security_type                = optional(string, "TrustedLaunch")
    secure_boot_enabled          = optional(bool, true)
    vtpm_enabled                 = optional(bool, true)
    encryption_at_host           = optional(bool, false)
    confidential_disk_encryption = optional(bool)
    disk_encryption_set_ids      = optional(list(string))
    enable_vm_deallocation       = optional(bool, true)
    use_availability_zones       = optional(bool, true)
    accelerated_networking       = optional(bool, true)
    gpu_preset                   = optional(bool, false)
    install_gpu_drivers          = optional(bool)
    rdp_shortpath                = optional(string)
    compliance_enforcement       = optional(string)
    compliance_timeout           = optional(number)
    entra_id_groups              = optional(list(string))
    enable_timezone_redirection  = optional(bool)
    vm_timezone                  = optional(string)
    patch_orchestration          = optional(string)
    preferred_disk_controller    = optional(string)
    user_assigned_identity_ids   = optional(list(string))
    application_security_groups  = optional(list(string))
    enable_hevc                  = optional(bool)
    enable_appv_client_service   = optional(bool)
    run_app_policies             = optional(bool)
    install_certificates         = optional(bool)
    watermarking = optional(object({
      enabled       = bool
      scale         = optional(number, 1)
      opacity       = optional(number, 0)
      width_factor  = optional(number, 0)
      height_factor = optional(number, 0)
    }))
    backup = optional(object({
      mode      = string
      policy_id = optional(string)
    }))
    console_connect = optional(object({
      enabled = bool
      region  = optional(string)
    }))
    tracking = optional(object({
      cpu_usage               = optional(bool, true)
      ram_usage               = optional(bool, true)
      average_active_sessions = optional(bool, true)
      usage_via_log_analytics = optional(bool)
    }))
    agent_update = optional(object({
      type                                 = string
      time_zone                            = optional(string)
      use_session_host_local_time          = optional(bool)
      exclude_drain_mode_hosts             = optional(bool)
      power_on_hosts_in_maintenance_window = optional(bool)
      primary_window = optional(object({
        day_of_week = number
        hour        = number
      }))
      secondary_window = optional(object({
        day_of_week = number
        hour        = number
      }))
    }))
    tags = optional(map(string), {})
  }))
  default = {}
}

variable "static_host_pools" {
  description = "Static host pools (Pooled or Personal without dynamic auto-scale), keyed by AVD host pool name."
  type = map(object({
    friendly_name               = string
    description                 = optional(string, "Managed by Terraform")
    region_key                  = optional(string)
    workspace_key               = optional(string)
    host_pool_type              = optional(string, "Personal")
    assignment_type             = optional(string, "Automatic")
    app_group_type              = optional(string, "Desktop")
    app_group_name              = optional(string)
    load_balancer               = optional(string)
    max_session_limit           = optional(number, 10)
    validation_env              = optional(bool, false)
    start_vm_on_connect         = optional(bool, true)
    max_idle_minutes            = optional(number, 60)
    max_disconnected            = optional(number, 120)
    max_connection_minutes      = optional(number)
    fslogix_enabled             = optional(bool)
    fslogix_profile_id          = optional(string)
    scripted_action_profile_id  = optional(string)
    scripted_action_profile_key = optional(string)
    security_type               = optional(string, "TrustedLaunch")
    secure_boot_enabled         = optional(bool, true)
    vtpm_enabled                = optional(bool, true)
    encryption_at_host          = optional(bool, false)
    enable_vm_deallocation      = optional(bool, true)
    use_availability_zones      = optional(bool, true)
    accelerated_networking      = optional(bool, true)
    rdp_shortpath               = optional(string)
    compliance_enforcement      = optional(string)
    compliance_timeout          = optional(number)
    entra_id_groups             = optional(list(string))
    enable_timezone_redirection = optional(bool)
    vm_timezone                 = optional(string)
    patch_orchestration         = optional(string)
    preferred_disk_controller   = optional(string)
    enable_hevc                 = optional(bool)
    backup = optional(object({
      mode      = string
      policy_id = optional(string)
    }))
    console_connect = optional(object({
      enabled = bool
      region  = optional(string)
    }))
    tracking = optional(object({
      cpu_usage               = optional(bool, true)
      ram_usage               = optional(bool, true)
      average_active_sessions = optional(bool, true)
      usage_via_log_analytics = optional(bool)
    }))
    agent_update = optional(object({
      type                                 = string
      time_zone                            = optional(string)
      use_session_host_local_time          = optional(bool)
      exclude_drain_mode_hosts             = optional(bool)
      power_on_hosts_in_maintenance_window = optional(bool)
      primary_window = optional(object({
        day_of_week = number
        hour        = number
      }))
      secondary_window = optional(object({
        day_of_week = number
        hour        = number
      }))
    }))
    tags = optional(map(string), {})
  }))
  default = {}
}

variable "rdp_profiles" {
  description = "Host pool RDP profiles, keyed by a logical key."
  type = map(object({
    name     = string
    settings = optional(string, "drivestoredirect:s:;audiomode:i:0;videoplaybackmode:i:1;redirectclipboard:i:1;redirectprinters:i:0;devicestoredirect:s:;redirectcomports:i:0;redirectsmartcards:i:1;usbdevicestoredirect:s:;enablecredsspsupport:i:1;use multimon:i:1")
  }))
  default = {}
}

variable "default_rdp_profile_key" {
  description = "Key in rdp_profiles to set as the global default RDP profile in Nerdio (null skips)."
  type        = string
  default     = null
}

variable "vm_deployment_profiles" {
  description = "Reusable host pool VM deployment profiles, keyed by a logical key."
  type = map(object({
    name                                = string
    description                         = optional(string, "Managed by Terraform")
    apply_virtual_desktop_optimizations = optional(bool, true)
    accelerated_networking_enabled      = optional(bool, true)
    force_vm_restart                    = optional(bool, true)
    enable_timezone_redirection         = optional(bool, true)
    vm_timezone                         = optional(string, "UTC")
    install_gpu_drivers                 = optional(bool, false)
    hci_gpu_allocation_mode             = optional(string, "None")
    use_availability_zones              = optional(bool, true)
    availability_zones                  = optional(list(string), [])
    is_shadow_users_enabled             = optional(bool, false)
    enable_vm_deallocation              = optional(bool, true)
    install_certificates                = optional(bool, false)
    enable_appv_client_service          = optional(bool, false)
    run_app_policies                    = optional(bool, false)
    always_prompt_for_password          = optional(bool, false)
    security_type                       = optional(string, "TrustedLaunch")
    secure_boot_enabled                 = optional(bool, true)
    vtpm_enabled                        = optional(bool, true)
    integrity_monitoring                = optional(bool, false)
    encryption_at_host                  = optional(bool, false)
    confidential_disk_encryption        = optional(bool, false)
    disk_encryption_set_ids             = optional(list(string), [])
    use_dedicated_hosts                 = optional(bool, false)
    hibernation_mode                    = optional(string, "Disabled")
    boot_diagnostics_enabled            = optional(bool, true)
    boot_diagnostics_storage_ids        = optional(list(string), [])
    entra_id_groups                     = optional(list(string), [])
    compliance_enforcement              = optional(string, "None")
    compliance_timeout                  = optional(number)
    entra_device_timeout_in_minutes     = optional(number, 30)
    capacity_reservation_group_ids      = optional(list(string), [])
    preferred_disk_controller_type      = optional(string, "SCSI")
    proximity_placement_group_ids       = optional(list(string), [])
    patch_orchestration                 = optional(string, "Default")
    application_security_group_ids      = optional(list(string), [])
    user_assigned_identity_ids          = optional(list(string), [])
    enable_hevc                         = optional(bool, false)
    watermarking = optional(object({
      enabled       = optional(bool, false)
      scale         = optional(number, 1)
      opacity       = optional(number, 0)
      width_factor  = optional(number, 0)
      height_factor = optional(number, 0)
    }), {})
  }))
  default = {}
}

variable "scripted_actions" {
  description = "Nerdio Windows scripted actions, keyed by a logical key."
  type = map(object({
    name                  = string
    description           = optional(string, "Managed by Terraform")
    script                = string
    execution_mode        = optional(string, "Combined")
    execution_environment = optional(string, "CustomScript")
    execution_timeout     = optional(number, 30)
    tags                  = optional(list(string), ["terraform"])
  }))
  default = {}
}

variable "scripted_action_groups" {
  description = "Nerdio scripted action groups, keyed by a logical key. Actions can reference scripted_action_id (number) or action_key (key in var.scripted_actions)."
  type = map(object({
    name        = string
    description = optional(string, "Managed by Terraform")
    tags        = optional(list(string), ["terraform"])
    actions = list(object({
      scripted_action_id = optional(number)
      action_key         = optional(string)
      default_params = optional(map(object({
        value = optional(string)
        array = optional(list(string))
      })))
    }))
  }))
  default = {}
}

variable "scripted_action_profiles" {
  description = "Host pool scripted action profiles, keyed by a logical key. Items in each trigger can reference id (number), action_key (in var.scripted_actions), or group_key (in var.scripted_action_groups)."
  type = map(object({
    name        = string
    description = optional(string, "Managed by Terraform")
    on_vm_create = optional(object({
      enabled             = optional(bool, false)
      active_directory_id = optional(number)
      actions = optional(list(object({
        type       = optional(string, "Action")
        id         = optional(number)
        action_key = optional(string)
        group_key  = optional(string)
        params = optional(map(object({
          value = optional(string)
          array = optional(list(string))
        })))
      })), [])
    }), {})
    on_host_create = optional(object({
      enabled             = optional(bool, false)
      active_directory_id = optional(number)
      actions = optional(list(object({
        type       = optional(string, "Action")
        id         = optional(number)
        action_key = optional(string)
        group_key  = optional(string)
        params = optional(map(object({
          value = optional(string)
          array = optional(list(string))
        })))
      })), [])
    }), {})
    on_start = optional(object({
      enabled             = optional(bool, false)
      active_directory_id = optional(number)
      actions = optional(list(object({
        type       = optional(string, "Action")
        id         = optional(number)
        action_key = optional(string)
        group_key  = optional(string)
        params = optional(map(object({
          value = optional(string)
          array = optional(list(string))
        })))
      })), [])
    }), {})
    on_stop = optional(object({
      enabled             = optional(bool, false)
      active_directory_id = optional(number)
      actions = optional(list(object({
        type       = optional(string, "Action")
        id         = optional(number)
        action_key = optional(string)
        group_key  = optional(string)
        params = optional(map(object({
          value = optional(string)
          array = optional(list(string))
        })))
      })), [])
    }), {})
    on_remove = optional(object({
      enabled             = optional(bool, false)
      active_directory_id = optional(number)
      actions = optional(list(object({
        type       = optional(string, "Action")
        id         = optional(number)
        action_key = optional(string)
        group_key  = optional(string)
        params = optional(map(object({
          value = optional(string)
          array = optional(list(string))
        })))
      })), [])
    }), {})
  }))
  default = {}
}

variable "workspace_user_assignments" {
  description = "Entra user, group, or service principal object IDs to assign to all AVD workspaces in var.workspaces via nme_user_assignment."
  type        = list(string)
  default     = []
}
