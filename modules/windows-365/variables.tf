variable "name_prefix" {
  description = "Short prefix for Windows 365 policies and Azure Network Connection."
  type        = string
}

variable "subscription_id" {
  description = "Azure subscription ID used by the Windows 365 Azure Network Connection."
  type        = string
}

variable "resource_group_id" {
  description = "Azure resource group ARM ID where Cloud PC NICs are placed."
  type        = string
}

variable "virtual_network_id" {
  description = "Azure Virtual Network ARM ID for the Cloud PC Azure Network Connection."
  type        = string
}

variable "subnet_id" {
  description = "Subnet ARM ID inside the VNet for Cloud PC network interfaces."
  type        = string
}

variable "join_type" {
  description = "Cloud PC directory join type: azureADJoin (Entra join) or hybridAzureADJoin."
  type        = string
  default     = "azureADJoin"

  validation {
    condition     = contains(["azureADJoin", "hybridAzureADJoin"], var.join_type)
    error_message = "join_type must be azureADJoin or hybridAzureADJoin."
  }
}

variable "image_id" {
  description = "Gallery image ID for the Cloud PC provisioning policy (for example, microsoftwindowsdesktop_windows-ent-cpc_win11-24h2-ent-cpc-m365)."
  type        = string
  default     = "microsoftwindowsdesktop_windows-ent-cpc_win11-24h2-ent-cpc-m365"
}

variable "image_type" {
  description = "Cloud PC image type: gallery or custom."
  type        = string
  default     = "gallery"
}

variable "enable_single_sign_on" {
  description = "Enable Entra single sign-on on provisioned Cloud PCs."
  type        = bool
  default     = true
}

variable "local_admin_enabled" {
  description = "Grant end users local administrator rights on their Cloud PC via Windows 365 user settings."
  type        = bool
  default     = false
}

variable "restore_point_frequency_hours" {
  description = "Cloud PC restore point frequency in hours (4, 6, 12, 16, or 24)."
  type        = number
  default     = 12
}

variable "assigned_group_object_ids" {
  description = "Entra group Object IDs assigned to the Windows 365 provisioning policy and user settings."
  type        = list(string)
  default     = []
}
