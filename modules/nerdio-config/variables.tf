variable "subscription_id" {
  description = "Subscription linked to Nerdio Manager during the setup wizard."
  type        = string
}

variable "location" {
  description = "Azure region for the AVD workspace."
  type        = string
}

variable "hostpools_resource_group_name" {
  description = "Resource group for AVD objects and session hosts. Linked in Nerdio as the default group."
  type        = string
}

variable "network" {
  description = "Session host network to link in Nerdio."
  type = object({
    resource_group_name = string
    vnet_name           = string
    subnet_name         = string
  })
}

variable "workspace" {
  description = "AVD workspace created through Nerdio."
  type = object({
    name          = string
    friendly_name = optional(string)
    description   = optional(string)
  })
}

variable "ad_config_friendly_name" {
  description = "Friendly name of the directory profile created in the Nerdio setup wizard. Null uses Nerdio's default."
  type        = string
  default     = null
}

variable "fslogix" {
  description = "FSLogix profile pointing at the profile share. Null skips it."
  type = object({
    name              = optional(string, "Terraform FSLogix profile")
    profile_share_unc = string
    entra_id_kerberos = optional(bool, true)
    cloud_cache       = optional(bool, false)
  })
  default = null
}

variable "auto_scale" {
  description = "Default-mode auto-scale profile shared by the host pools."
  type = object({
    name                   = optional(string, "Terraform default scaling")
    max_sessions_per_host  = optional(number, 10)
    load_balancing         = optional(string, "BreadthFirst")
    host_pool_capacity     = optional(number, 4)
    min_active_hosts_count = optional(number, 1)
    burst_capacity         = optional(number, 2)
    scale_out_cpu_percent  = optional(number, 80)
    scale_in_cpu_percent   = optional(number, 20)
  })
  default = {}
}

variable "host_pools" {
  description = <<-EOT
    Pooled dynamic host pools, keyed by AVD host pool name. image is the identifier Nerdio
    shows for a desktop image, e.g. a Marketplace path like
    MicrosoftWindowsDesktop/office-365/win11-24h2-avd-m365/latest, or a gallery image
    after you add it under Desktop Images.
  EOT
  type = map(object({
    friendly_name     = string
    description       = optional(string, "Managed by Terraform")
    app_group_type    = optional(string, "Desktop")
    load_balancer     = optional(string, "BreadthFirst")
    max_session_limit = optional(number, 10)
    validation_env    = optional(bool, false)
    timezone_id       = optional(string, "Central Standard Time")
    vm_prefix         = string
    vm_size           = optional(string, "Standard_D4s_v5")
    image             = optional(string, "MicrosoftWindowsDesktop/office-365/win11-24h2-avd-m365/latest")
    os_disk_type      = optional(string, "StandardSSD_LRS")
    os_disk_size_gb   = optional(number, 128)
    max_idle_minutes  = optional(number, 60)
    max_disconnected  = optional(number, 120)
    tags              = optional(map(string), {})
  }))
  default = {}
}
