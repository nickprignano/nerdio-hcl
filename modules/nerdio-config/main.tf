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
  page_blobs        = false
  entra_id_kerberos = var.fslogix.entra_id_kerberos
  redirections_xml  = <<-XML
    <FrxProfileFolderRedirection ExcludeCommonFolders="0">
    </FrxProfileFolderRedirection>
  XML

  installer = {
    version      = ""
    force_update = false
  }

  profile_container = {
    locations = [var.fslogix.profile_share_unc]
    options   = ""
  }

  office_container = {
    locations = []
    options   = ""
  }

  exclusions = {
    exclusion_mode           = "None"
    excluded_domain_accounts = []
  }
}

resource "nme_auto_scale_profile" "this" {
  name        = var.auto_scale.name
  mode        = "Default"
  description = "Managed by Terraform"

  default = {
    avd_properties = {
      start_vm_on_connect   = true
      max_sessions_per_host = var.auto_scale.max_sessions_per_host
      load_balancing        = var.auto_scale.load_balancing
    }

    size = {
      active_host_type       = "Running"
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
      aggressiveness = "Medium"
      messaging = {
        minutes_before_remove = 10
        message               = "This session host is being shut down. Please save your work and sign out."
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
      enable = false
    }
  }
}

resource "nme_dynamic_host_pool" "this" {
  for_each = var.host_pools

  resource_group_id   = nme_linked_resource_group.hostpools.id
  name                = each.key
  friendly_name       = each.value.friendly_name
  description         = each.value.description
  host_pool_type      = "Pooled"
  app_group_type      = each.value.app_group_type
  load_balancer_type  = each.value.load_balancer
  max_session_limit   = each.value.max_session_limit
  validation_env      = each.value.validation_env
  start_vm_on_connect = true

  workspace = {
    id = nme_workspace.this.id
  }

  active_directory = var.ad_config_friendly_name == null ? null : {
    id = data.nme_ad_config.this[0].id
  }

  fslogix = var.fslogix == null ? { enabled = false, id = null } : {
    enabled = true
    id      = nme_fslogix_profile.this[0].id
  }

  auto_scale = {
    enabled     = true
    profile_id  = nme_auto_scale_profile.this.id
    timezone_id = each.value.timezone_id

    vm_template = {
      prefix            = each.value.vm_prefix
      size              = each.value.vm_size
      image             = each.value.image
      storage_type      = each.value.os_disk_type
      disk_size         = each.value.os_disk_size_gb
      resource_group_id = nme_linked_resource_group.hostpools.id
      linked_network_id = nme_linked_network.session_hosts.id
    }
  }

  session_timeout = {
    enabled                = true
    max_idle_time          = each.value.max_idle_minutes
    max_disconnection_time = each.value.max_disconnected
  }

  vm_deployment = {
    security_type          = "TrustedLaunch"
    secure_boot_enabled    = true
    vtpm_enabled           = true
    enable_vm_deallocation = true
    use_availability_zones = true
  }

  tags = merge({ "managed-by" = "terraform" }, each.value.tags)
}
