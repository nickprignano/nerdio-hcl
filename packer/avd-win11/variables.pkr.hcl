variable "subscription_id" {
  type        = string
  description = "Subscription that holds the build resource group and the Compute Gallery."
}

variable "tenant_id" {
  type        = string
  description = "Entra tenant for the build."
}

variable "use_azure_cli_auth" {
  type        = bool
  default     = true
  description = "Authenticate with the current az login. Set false and export ARM_CLIENT_ID / ARM_CLIENT_SECRET (or OIDC) for CI."
}

variable "location" {
  type    = string
  default = "eastus2"
}

variable "build_resource_group" {
  type        = string
  description = "Existing resource group Packer builds the temporary VM in. Keeps Packer from needing subscription-wide create rights."
}

variable "build_subnet" {
  type = object({
    resource_group = string
    vnet           = string
    subnet         = string
  })
  default     = null
  description = "Build inside an existing subnet (no public IP). Null lets Packer create a temporary network with a public IP."
}

variable "vm_size" {
  type    = string
  default = "Standard_D4s_v5"
}

variable "source_image" {
  type = object({
    publisher = string
    offer     = string
    sku       = string
    version   = string
  })
  default = {
    publisher = "MicrosoftWindowsDesktop"
    offer     = "office-365"
    sku       = "win11-24h2-avd-m365"
    version   = "latest"
  }
  description = "Marketplace base image. The default is Windows 11 Enterprise multi-session with Microsoft 365 Apps."
}

variable "gallery" {
  type = object({
    resource_group   = string
    name             = string
    image_definition = string
    replica_regions  = list(string)
  })
  description = "Compute Gallery destination. Create it with modules/image-gallery."
}

variable "image_version" {
  type        = string
  default     = ""
  description = "Gallery image version (major.minor.patch). Empty uses YYYY.MMDD.HHmm."
}

variable "timezone" {
  type    = string
  default = "Central Standard Time"
}

variable "run_windows_update" {
  type    = bool
  default = true
}

variable "run_vdot" {
  type        = bool
  default     = true
  description = "Apply the Virtual Desktop Optimization Tool (VDOT) defaults."
}

variable "tags" {
  type    = map(string)
  default = {}
}
