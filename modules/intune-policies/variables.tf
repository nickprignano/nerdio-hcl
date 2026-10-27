variable "name_prefix" {
  description = "Short prefix for Intune AVD session host configuration policies."
  type        = string
}

variable "fslogix_vhd_locations" {
  description = "SMB UNC path(s) for FSLogix profile containers when managed via Intune Settings Catalog."
  type        = string
  default     = null
}

variable "defender_excluded_extensions" {
  description = "File extensions excluded from Microsoft Defender real-time scanning on AVD session hosts (per Microsoft FSLogix & App Attach guidance)."
  type        = list(string)
  default     = ["vhd", "vhdx", "cim"]
}

variable "wufb_feature_deferral_days" {
  description = "Windows Update for Business feature update deferral period in days."
  type        = number
  default     = 30
}

variable "wufb_quality_deferral_days" {
  description = "Windows Update for Business quality update deferral period in days."
  type        = number
  default     = 7
}

variable "assigned_device_group_ids" {
  description = "Entra dynamic or assigned device group Object IDs for AVD session hosts."
  type        = list(string)
  default     = []
}

variable "conditional_access" {
  description = "Optional Entra Conditional Access policy for AVD and Windows 365 Cloud Login."
  type = object({
    enabled           = optional(bool, false)
    state             = optional(string, "enabledForReportingButNotEnforced")
    include_group_ids = optional(list(string), [])
    exclude_group_ids = optional(list(string), [])
    built_in_controls = optional(list(string), ["mfa"])
    sign_in_max_hours = optional(number, 12)
  })
  default = {}
}
