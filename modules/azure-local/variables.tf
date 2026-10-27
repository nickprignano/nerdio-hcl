variable "name_prefix" {
  description = "Short prefix for the Azure Local AVD logical network."
  type        = string
}

variable "location" {
  description = "Azure region where the Azure Local cluster and Custom Location are registered."
  type        = string
}

variable "resource_group_id" {
  description = "ARM resource ID of the resource group holding the Azure Local resources."
  type        = string
}

variable "custom_location_id" {
  description = "ARM resource ID of the Azure Arc Custom Location representing the Azure Local cluster."
  type        = string
}

variable "vm_switch_name" {
  description = "Name of the Hyper-V converged virtual switch on the Azure Local cluster."
  type        = string
}

variable "vlan_id" {
  description = "VLAN ID for AVD session host traffic on the Azure Local logical network."
  type        = number
  default     = null
}

variable "address_prefix" {
  description = "CIDR address prefix for the Azure Local logical network when using static IP allocation."
  type        = string
  default     = null
}

variable "default_gateway" {
  description = "Default gateway IP for static IP allocation (null uses DHCP)."
  type        = string
  default     = null
}

variable "dns_servers" {
  description = "DNS server IPs for the Azure Local logical network."
  type        = list(string)
  default     = []
}

variable "nerdio_service_principal_object_id" {
  description = "Object ID of Nerdio Manager's service principal to grant Azure Stack HCI VM Contributor on the resource group."
  type        = string
}

variable "tags" {
  description = "Tags applied to all Azure Local resources."
  type        = map(string)
  default     = {}
}

variable "gallery_images" {
  description = "Optional Azure Local gallery images imported from Azure Compute Gallery or Marketplace onto CSV storage."
  type = map(object({
    container_id        = string
    image_version_id    = optional(string)
    os_type             = optional(string, "Windows")
    hyper_v_generation  = optional(string, "V2")
    cloud_init_data_src = optional(string, "Azure")
  }))
  default = {}
}
