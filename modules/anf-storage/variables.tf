variable "prefix" {
  description = "Short naming prefix."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group for the Azure NetApp Files account, pool and volume."
  type        = string
}

variable "vnet_name" {
  description = "Virtual network name where the delegated ANF subnet is created."
  type        = string
}

variable "vnet_resource_group_name" {
  description = "Resource group of the virtual network."
  type        = string
}

variable "subnet_cidr" {
  description = "CIDR block for the Microsoft.Netapp/volumes delegated subnet (/28 or larger)."
  type        = string
}

variable "service_level" {
  description = "ANF capacity pool service level: Standard, Premium or Ultra."
  type        = string
  default     = "Premium"

  validation {
    condition     = contains(["Standard", "Premium", "Ultra"], var.service_level)
    error_message = "service_level must be Standard, Premium or Ultra."
  }
}

variable "pool_size_in_tb" {
  description = "Provisioned capacity pool size in TiB (minimum 1 TiB)."
  type        = number
  default     = 4
}

variable "volume_quota_in_gb" {
  description = "Volume quota in GiB (minimum 100 GiB)."
  type        = number
  default     = 1024
}

variable "volume_path" {
  description = "Unique file path for the SMB volume."
  type        = string
  default     = "fslogix-profiles"
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
