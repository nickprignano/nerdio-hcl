variable "tenant_id" {
  description = "Entra tenant that hosts Nerdio Manager. Pinning it stops a stray az login from deploying into the wrong tenant."
  type        = string
}

variable "subscription_id" {
  description = "Subscription that hosts Nerdio Manager and AVD."
  type        = string
}

variable "prefix" {
  description = "Short naming prefix, e.g. \"contoso-nme\"."
  type        = string
}

variable "location" {
  description = "Azure region close to the admin team and the primary AVD users."
  type        = string
  default     = "eastus2"
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}

variable "resource_groups" {
  description = "Resource group names keyed by role (nerdio, network, hostpools, storage, monitoring)."
  type        = map(string)
}

variable "network" {
  description = "AVD spoke network settings."
  type = object({
    address_space = list(string)
    subnets = object({
      session_hosts     = string
      private_endpoints = string
      app_integration   = string
    })
    dns_servers         = optional(list(string), [])
    hub_vnet_id         = optional(string)
    use_remote_gateways = optional(bool, false)
    create_nat_gateway  = optional(bool, true)
  })
}

variable "fslogix" {
  description = "FSLogix profile storage. Set to null to skip."
  type = object({
    storage_account_name   = string
    share_quota_gb         = optional(number, 1024)
    identity_source        = optional(string, "AADKERB")
    user_group_object_ids  = optional(list(string), [])
    admin_group_object_ids = optional(list(string), [])
  })
  default = null
}

variable "nerdio_template_file" {
  description = "Path to the Nerdio Manager ARM template exported from the Marketplace."
  type        = string
  default     = "../../templates/nerdio-manager/template.json"
}

variable "nerdio_template_parameters" {
  description = "Parameter values for the exported template."
  type        = any
  default     = {}
}

variable "create_entra_app" {
  description = "Pre-create the nerdio-nmw-app registration in Terraform (Nerdio's \"Use existing AD app\" install path). False leaves it to Nerdio's install script."
  type        = bool
  default     = true
}

variable "entra_app" {
  description = "Entra app settings when create_entra_app is true."
  type = object({
    display_name           = optional(string, "nerdio-nmw-app")
    owner_object_ids       = optional(list(string), [])
    wvd_admin_object_ids   = optional(list(string), [])
    grant_admin_consent    = optional(bool, false)
    enable_mail_send       = optional(bool, false)
    create_rest_api_client = optional(bool, false)
  })
  default = {}
}

variable "enable_hardening" {
  description = "Add private endpoints and VNet integration for the Nerdio core resources. Turn on in a second apply, once the Marketplace deployment exists."
  type        = bool
  default     = false
}

variable "hardening" {
  description = "Hardening options when enable_hardening is true."
  type = object({
    private_app_service   = optional(bool, false)
    disable_public_access = optional(bool, false)
  })
  default = {}
}

variable "image_gallery" {
  description = "Compute Gallery for Packer-built images. Set to null to skip and use Marketplace images in Nerdio."
  type = object({
    name                      = string
    build_resource_group_name = string
    packer_principal_id       = optional(string)
  })
  default = null
}
