variable "subscription_id" {
  description = "Azure subscription ID linked in Nerdio."
  type        = string
}

variable "hostpools_resource_group_name" {
  description = "Default resource group for host pools when an entry omits resource_group."
  type        = string
}

variable "host_pool_assignments" {
  description = "Per-host-pool user and group assignments via POST /api/v1/arm/hostpool/{subscriptionId}/{resourceGroup}/{hostPoolName}/assign."
  type = map(object({
    resource_group = optional(string)
    users          = optional(list(string), [])
    groups         = optional(list(string), [])
    app_groups     = optional(list(string), [])
  }))
  default = {}
}

variable "host_pool_rdp" {
  description = "Per-host-pool RDP profile and Shortpath settings via PATCH /api/v1/arm/hostpool/{subscriptionId}/{resourceGroup}/{hostPoolName}/rdp."
  type = map(object({
    resource_group     = optional(string)
    configuration_name = optional(string)
    rdp_properties     = optional(string)
    short_path = optional(object({
      managed_private_udp = optional(string, "Default")
      direct_udp          = optional(string, "Default")
      public_udp          = optional(string, "Default")
      relay_udp           = optional(string, "Default")
    }))
  }))
  default = {}
}

variable "uam_app_groups" {
  description = "Unified Application Management (UAM) app groups via /api/v1/app-management/app-group."
  type = map(object({
    name = string
    items = list(object({
      repo_id         = number
      external_id     = string
      version         = optional(string, "")
      cached_name     = optional(string, "")
      reboot          = optional(bool, false)
      on_upgrade_fail = optional(string, "Reinstall")
    }))
  }))
  default = {}
}

variable "azure_files_autoscale" {
  description = "Azure Files share linking and storage auto-scale via /api/v1/storage/azure-files/{subscriptionId}/{resourceGroup}/{accountName}/{shareName}."
  type = map(object({
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
  }))
  default = {}
}

variable "app_attach_packages" {
  description = "MSIX / App Attach packages registered in Nerdio Manager via /api/v1/msix-app-attach/package."
  type = map(object({
    name            = string
    image_path      = string
    package_name    = optional(string)
    version         = optional(string)
    certificate_id  = optional(string)
    host_pool_names = optional(list(string), [])
  }))
  default = {}
}

variable "desktop_images" {
  description = "Nerdio Manager desktop image pipeline schedules and ring-based host pool updates via /api/v1/desktop-image."
  type = map(object({
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
  }))
  default = {}
}

variable "remote_apps" {
  description = "Published RemoteApp definitions on AVD application groups via /api/v1/arm/hostpool/{subscriptionId}/{resourceGroup}/{hostPoolName}/remote-app."
  type = map(object({
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
  }))
  default = {}
}

variable "uam_repositories" {
  description = "Custom Unified Application Management (UAM) WinGet or NuGet repositories via /api/v1/app-management/repository."
  type = map(object({
    name            = string
    repository_type = optional(string, "WinGet")
    url             = string
    trust_level     = optional(string, "Trusted")
  }))
  default = {}
}

variable "host_pool_reimage_schedules" {
  description = "Recurring host pool re-image / update schedules via /api/v1/arm/hostpool/{subscriptionId}/{resourceGroup}/{hostPoolName}/schedule."
  type = map(object({
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
  }))
  default = {}
}
