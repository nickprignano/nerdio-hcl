# Nerdio Manager configuration through the official nerdio/nme provider (Nerdio REST API).
# Runs after Nerdio is installed, its setup wizard is finished and the REST API is enabled.

data "nme_linked_subscription" "this" {
  subscription_id = var.subscription_id
}

resource "nme_linked_resource_group" "hostpools" {
  subscription_id = data.nme_linked_subscription.this.id
  name            = var.hostpools_resource_group_name
  is_default      = true
}

resource "nme_linked_resource_group" "network" {
  count           = var.network.resource_group_name == var.hostpools_resource_group_name ? 0 : 1
  subscription_id = data.nme_linked_subscription.this.id
  name            = var.network.resource_group_name
  is_default      = false
}

locals {
  network_rg_id = try(nme_linked_resource_group.network[0].id, nme_linked_resource_group.hostpools.id)
}

resource "nme_linked_network" "session_hosts" {
  resource_group_id = local.network_rg_id
  name              = var.network.vnet_name
  subnet            = var.network.subnet_name
}

resource "nme_workspace" "this" {
  resource_group_id = nme_linked_resource_group.hostpools.id
  name              = var.workspace.name
  location          = var.location
  friendly_name     = coalesce(var.workspace.friendly_name, var.workspace.name)
  description       = var.workspace.description
}

data "nme_ad_config" "this" {
  count         = var.ad_config_friendly_name == null ? 0 : 1
  friendly_name = var.ad_config_friendly_name
}

resource "nme_fslogix_profile" "this" {
  count             = var.fslogix == null ? 0 : 1
  name              = var.fslogix.name
  cloud_cache       = var.fslogix.cloud_cache
  page_blobs        = var.fslogix.page_blobs
  entra_id_kerberos = var.fslogix.entra_id_kerberos
  redirections_xml = coalesce(var.fslogix.redirections_xml, <<-XML
    <FrxProfileFolderRedirection ExcludeCommonFolders="0">
    </FrxProfileFolderRedirection>
  XML
  )

  installer = {
    version      = ""
    force_update = false
  }

  profile_container = {
    locations = [var.fslogix.profile_share_unc]
    options   = var.fslogix.profile_options
  }

  office_container = {
    locations = var.fslogix.office_share_unc
    options   = var.fslogix.office_options
  }

  exclusions = {
    exclusion_mode           = var.fslogix.exclusion_mode
    excluded_domain_accounts = var.fslogix.excluded_domain_accounts
  }
}

resource "nme_fslogix_default_profile" "this" {
  count      = var.fslogix != null && try(var.fslogix.set_as_default, false) ? 1 : 0
  profile_id = nme_fslogix_profile.this[0].id
}

resource "nme_rdp_profile" "this" {
  for_each = var.rdp_profiles
  name     = each.value.name
  settings = each.value.settings
}

resource "nme_rdp_default_profile" "this" {
  count      = var.default_rdp_profile_key == null ? 0 : 1
  profile_id = nme_rdp_profile.this[var.default_rdp_profile_key].id
}

resource "nme_vm_deployment_profile" "this" {
  for_each    = var.vm_deployment_profiles
  name        = each.value.name
  description = each.value.description

  configuration = {
    apply_virtual_desktop_optimizations = each.value.apply_virtual_desktop_optimizations
    accelerated_networking_enabled      = each.value.accelerated_networking_enabled
    force_vm_restart                    = each.value.force_vm_restart
    enable_timezone_redirection         = each.value.enable_timezone_redirection
    vm_timezone                         = each.value.vm_timezone
    install_gpu_drivers                 = each.value.install_gpu_drivers
    hci_gpu_allocation_mode             = each.value.hci_gpu_allocation_mode
    use_availability_zones              = each.value.use_availability_zones
    availability_zones                  = each.value.availability_zones
    is_shadow_users_enabled             = each.value.is_shadow_users_enabled
    enable_vm_deallocation              = each.value.enable_vm_deallocation
    install_certificates                = each.value.install_certificates
    enable_appv_client_service          = each.value.enable_appv_client_service
    run_app_policies                    = each.value.run_app_policies
    always_prompt_for_password          = each.value.always_prompt_for_password
    security_type                       = each.value.security_type
    secure_boot_enabled                 = each.value.secure_boot_enabled
    vtpm_enabled                        = each.value.vtpm_enabled
    integrity_monitoring                = each.value.integrity_monitoring
    encryption_at_host                  = each.value.encryption_at_host
    confidential_disk_encryption        = each.value.confidential_disk_encryption
    disk_encryption_set_ids             = each.value.disk_encryption_set_ids
    use_dedicated_hosts                 = each.value.use_dedicated_hosts
    hibernation_mode                    = each.value.hibernation_mode
    boot_diagnostics_enabled            = each.value.boot_diagnostics_enabled
    boot_diagnostics_storage_ids        = each.value.boot_diagnostics_storage_ids
    entra_id_groups                     = each.value.entra_id_groups
    compliance_enforcement              = each.value.compliance_enforcement
    compliance_timeout                  = each.value.compliance_timeout
    entra_device_timeout_in_minutes     = each.value.entra_device_timeout_in_minutes
    capacity_reservation_group_ids      = each.value.capacity_reservation_group_ids
    preferred_disk_controller_type      = each.value.preferred_disk_controller_type
    proximity_placement_group_ids       = each.value.proximity_placement_group_ids
    patch_orchestration                 = each.value.patch_orchestration
    application_security_group_ids      = each.value.application_security_group_ids
    user_assigned_identity_ids          = each.value.user_assigned_identity_ids
    enable_hevc                         = each.value.enable_hevc
    watermarking = {
      enabled       = each.value.watermarking.enabled
      scale         = each.value.watermarking.scale
      opacity       = each.value.watermarking.opacity
      width_factor  = each.value.watermarking.width_factor
      height_factor = each.value.watermarking.height_factor
    }
  }
}

resource "nme_scripted_action" "this" {
  for_each              = var.scripted_actions
  name                  = each.value.name
  description           = each.value.description
  script                = each.value.script
  execution_mode        = each.value.execution_mode
  execution_environment = each.value.execution_environment
  execution_timeout     = each.value.execution_timeout
  tags                  = each.value.tags
}

resource "nme_scripted_action_group" "this" {
  for_each    = var.scripted_action_groups
  name        = each.value.name
  description = each.value.description
  tags        = each.value.tags

  scripted_actions = [
    for item in each.value.actions : {
      scripted_action_id = coalesce(item.scripted_action_id, tonumber(nme_scripted_action.this[item.action_key].id))
      default_params     = item.default_params
    }
  ]
}

locals {
  # Helper to resolve scripted action items inside each trigger of var.scripted_action_profiles.
  resolved_scripted_action_profiles = {
    for pk, prof in var.scripted_action_profiles : pk => {
      for trigger_name in ["on_vm_create", "on_host_create", "on_start", "on_stop", "on_remove"] :
      trigger_name => {
        enabled             = prof[trigger_name].enabled
        active_directory_id = prof[trigger_name].active_directory_id
        scripted_actions = [
          for item in prof[trigger_name].actions : {
            type = item.group_key != null ? "Group" : coalesce(item.type, "Action")
            id = coalesce(
              item.id,
              item.action_key != null ? tonumber(nme_scripted_action.this[item.action_key].id) : null,
              item.group_key != null ? tonumber(nme_scripted_action_group.this[item.group_key].id) : null
            )
            params = item.params
          }
        ]
      }
    }
  }
}

resource "nme_scripted_action_profile" "this" {
  for_each    = var.scripted_action_profiles
  name        = each.value.name
  description = each.value.description

  configurations = {
    on_vm_create   = local.resolved_scripted_action_profiles[each.key].on_vm_create
    on_host_create = local.resolved_scripted_action_profiles[each.key].on_host_create
    on_start       = local.resolved_scripted_action_profiles[each.key].on_start
    on_stop        = local.resolved_scripted_action_profiles[each.key].on_stop
    on_remove      = local.resolved_scripted_action_profiles[each.key].on_remove
  }
}

resource "nme_user_assignment" "workspace" {
  for_each  = toset(var.workspace_user_assignments)
  object_id = each.value

  avd_workspaces = [
    {
      workspace_id = nme_workspace.this.id
    }
  ]
}

resource "nme_auto_scale_profile" "this" {
  name        = var.auto_scale.name
  mode        = "Default"
  description = "Managed by Terraform"

  default = {
    avd_properties = {
      start_vm_on_connect   = var.auto_scale.start_vm_on_connect
      max_sessions_per_host = var.auto_scale.max_sessions_per_host
      load_balancing        = var.auto_scale.load_balancing
    }

    size = {
      active_host_type       = var.auto_scale.active_host_type
      host_pool_capacity     = var.auto_scale.host_pool_capacity
      min_active_hosts_count = var.auto_scale.min_active_hosts_count
      burst_capacity         = var.auto_scale.burst_capacity
    }

    triggers = [
      {
        trigger_type = "CPUUsage"
        cpu = {
          scale_out = {
            host_change_count             = 1
            value                         = var.auto_scale.scale_out_cpu_percent
            average_time_range_in_minutes = 5
          }
          scale_in = {
            host_change_count             = 1
            value                         = var.auto_scale.scale_in_cpu_percent
            average_time_range_in_minutes = 15
          }
        }
      }
    ]

    scale_in_policy = {
      restriction = {
        enable            = false
        put_to_drain_mode = false
      }
      aggressiveness = var.auto_scale.scale_in_aggressiveness
      messaging = {
        minutes_before_remove = var.auto_scale.minutes_before_remove
        message               = var.auto_scale.scale_in_message
      }
    }

    rolling_drain_mode = {
      is_enabled = false
      windows    = []
    }

    pre_stage = {
      enable = false
    }

    auto_heal = {
      enable = var.auto_scale.auto_heal_enabled
    }
  }
}

resource "nme_dynamic_host_pool" "this" {
  for_each = var.host_pools

  resource_group_id   = nme_linked_resource_group.hostpools.id
  name                = each.key
  friendly_name       = each.value.friendly_name
  description         = each.value.description
  host_pool_type      = each.value.host_pool_type
  app_group_type      = each.value.host_pool_type == "Personal" ? "Desktop" : each.value.app_group_type
  app_group_name      = each.value.app_group_name
  load_balancer_type  = coalesce(each.value.load_balancer, each.value.host_pool_type == "Personal" ? "Persistent" : "BreadthFirst")
  assignment_type     = each.value.host_pool_type == "Personal" ? each.value.assignment_type : null
  max_session_limit   = each.value.host_pool_type == "Personal" ? null : each.value.max_session_limit
  validation_env      = each.value.validation_env
  start_vm_on_connect = each.value.start_vm_on_connect

  workspace = {
    id = nme_workspace.this.id
  }

  active_directory = var.ad_config_friendly_name == null ? null : {
    id = data.nme_ad_config.this[0].id
  }

  fslogix = coalesce(each.value.fslogix_enabled, var.fslogix != null) ? {
    enabled = true
    id      = coalesce(each.value.fslogix_profile_id, try(nme_fslogix_profile.this[0].id, null))
  } : { enabled = false, id = null }

  scripted_actions = (each.value.scripted_action_profile_id != null || each.value.scripted_action_profile_key != null) ? {
    profile_id = coalesce(
      each.value.scripted_action_profile_id,
      try(nme_scripted_action_profile.this[each.value.scripted_action_profile_key].id, null)
    )
  } : null

  auto_scale = {
    enabled     = each.value.auto_scale_enabled
    profile_id  = coalesce(each.value.auto_scale_profile_id, nme_auto_scale_profile.this.id)
    timezone_id = each.value.timezone_id

    vm_template = {
      prefix                      = each.value.vm_prefix
      size                        = each.value.vm_size
      image                       = lookup(var.gallery_image_definition_ids, each.value.image, each.value.image)
      storage_type                = each.value.os_disk_type
      disk_size                   = each.value.os_disk_size_gb
      disk_performance_tier       = each.value.disk_performance_tier
      has_ephemeral_os_disk       = each.value.has_ephemeral_os_disk
      ephemeral_os_disk_placement = each.value.ephemeral_os_disk_placement
      resource_group_id           = nme_linked_resource_group.hostpools.id
      linked_network_id           = nme_linked_network.session_hosts.id
    }
  }

  session_timeout = {
    enabled                      = true
    max_idle_time                = each.value.max_idle_minutes
    max_disconnection_time       = each.value.max_disconnected
    max_connection_time          = each.value.max_connection_minutes
    remote_app_logoff_time_limit = each.value.remote_app_logoff_minutes
  }

  backup          = each.value.backup
  console_connect = each.value.console_connect
  tracking        = each.value.tracking
  agent_update    = each.value.agent_update

  vm_deployment = {
    security_type                  = each.value.security_type
    secure_boot_enabled            = each.value.secure_boot_enabled
    vtpm_enabled                   = each.value.vtpm_enabled
    encryption_at_host             = each.value.encryption_at_host
    confidential_disk_encryption   = each.value.confidential_disk_encryption
    disk_encryption_set_ids        = each.value.disk_encryption_set_ids
    enable_vm_deallocation         = each.value.enable_vm_deallocation
    use_availability_zones         = each.value.use_availability_zones
    accelerated_networking_enabled = each.value.accelerated_networking
    install_gpu_drivers            = each.value.install_gpu_drivers
    rdp_shortpath                  = each.value.rdp_shortpath
    compliance_enforcement         = each.value.compliance_enforcement
    compliance_timeout             = each.value.compliance_timeout
    entra_id_groups                = each.value.entra_id_groups
    enable_timezone_redirection    = each.value.enable_timezone_redirection
    vm_timezone                    = each.value.vm_timezone
    patch_orchestration            = each.value.patch_orchestration
    preferred_disk_controller_type = each.value.preferred_disk_controller
    user_assigned_identity_ids     = each.value.user_assigned_identity_ids
    application_security_group_ids = each.value.application_security_groups
    enable_hevc                    = each.value.enable_hevc
    enable_appv_client_service     = each.value.enable_appv_client_service
    run_app_policies               = each.value.run_app_policies
    install_certificates           = each.value.install_certificates
    watermarking                   = each.value.watermarking
  }

  tags = merge({ "managed-by" = "terraform" }, each.value.tags)
}

resource "nme_static_host_pool" "this" {
  for_each = var.static_host_pools

  resource_group_id   = nme_linked_resource_group.hostpools.id
  name                = each.key
  friendly_name       = each.value.friendly_name
  description         = each.value.description
  host_pool_type      = each.value.host_pool_type
  app_group_type      = each.value.host_pool_type == "Personal" ? "Desktop" : each.value.app_group_type
  app_group_name      = each.value.app_group_name
  load_balancer_type  = coalesce(each.value.load_balancer, each.value.host_pool_type == "Personal" ? "Persistent" : "BreadthFirst")
  assignment_type     = each.value.host_pool_type == "Personal" ? each.value.assignment_type : null
  max_session_limit   = each.value.host_pool_type == "Personal" ? null : each.value.max_session_limit
  validation_env      = each.value.validation_env
  start_vm_on_connect = each.value.start_vm_on_connect

  workspace = {
    id = nme_workspace.this.id
  }

  active_directory = var.ad_config_friendly_name == null ? null : {
    id = data.nme_ad_config.this[0].id
  }

  fslogix = coalesce(each.value.fslogix_enabled, var.fslogix != null) ? {
    enabled = true
    id      = coalesce(each.value.fslogix_profile_id, try(nme_fslogix_profile.this[0].id, null))
  } : { enabled = false, id = null }

  scripted_actions = (each.value.scripted_action_profile_id != null || each.value.scripted_action_profile_key != null) ? {
    profile_id = coalesce(
      each.value.scripted_action_profile_id,
      try(nme_scripted_action_profile.this[each.value.scripted_action_profile_key].id, null)
    )
  } : null

  session_timeout = {
    enabled                = true
    max_idle_time          = each.value.max_idle_minutes
    max_disconnection_time = each.value.max_disconnected
    max_connection_time    = each.value.max_connection_minutes
  }

  backup          = each.value.backup
  console_connect = each.value.console_connect
  tracking        = each.value.tracking
  agent_update    = each.value.agent_update

  vm_deployment = {
    security_type                  = each.value.security_type
    secure_boot_enabled            = each.value.secure_boot_enabled
    vtpm_enabled                   = each.value.vtpm_enabled
    encryption_at_host             = each.value.encryption_at_host
    enable_vm_deallocation         = each.value.enable_vm_deallocation
    use_availability_zones         = each.value.use_availability_zones
    accelerated_networking_enabled = each.value.accelerated_networking
    rdp_shortpath                  = each.value.rdp_shortpath
    compliance_enforcement         = each.value.compliance_enforcement
    compliance_timeout             = each.value.compliance_timeout
    entra_id_groups                = each.value.entra_id_groups
    enable_timezone_redirection    = each.value.enable_timezone_redirection
    vm_timezone                    = each.value.vm_timezone
    patch_orchestration            = each.value.patch_orchestration
    preferred_disk_controller_type = each.value.preferred_disk_controller
    enable_hevc                    = each.value.enable_hevc
  }

  tags = merge({ "managed-by" = "terraform" }, each.value.tags)
}
