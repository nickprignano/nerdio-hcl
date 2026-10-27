variable "gallery_name" {
  description = "Compute Gallery name (letters, digits, underscores and periods)."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group for the gallery."
  type        = string
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}

variable "image_definitions" {
  description = "Image definitions Packer publishes into, keyed by definition name."
  type = map(object({
    publisher                           = string
    offer                               = string
    sku                                 = string
    accelerated_network_support_enabled = optional(bool, true)
    hibernation_enabled                 = optional(bool, false)
  }))
  default = {
    "win11-avd-m365" = {
      publisher                           = "AVD"
      offer                               = "Windows11-MultiSession"
      sku                                 = "m365"
      accelerated_network_support_enabled = true
      hibernation_enabled                 = false
    }
    "win11-avd-gpu" = {
      publisher                           = "AVD"
      offer                               = "Windows11-MultiSession"
      sku                                 = "gpu"
      accelerated_network_support_enabled = true
      hibernation_enabled                 = false
    }
  }
}

variable "packer_principal_id" {
  description = "Object ID of the identity that runs Packer. Gets Contributor on the gallery and build resource group. Null skips the role assignments."
  type        = string
  default     = null
}

variable "build_resource_group_name" {
  description = "Resource group Packer builds temporary VMs in. Created here."
  type        = string
}
