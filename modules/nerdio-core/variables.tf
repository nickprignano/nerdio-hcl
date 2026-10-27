variable "resource_group_name" {
  description = "Resource group for the Nerdio Manager core resources. Nerdio expects it to hold only its own resources."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}

variable "app_name" {
  description = "Name stem. Nerdio's own update script derives resource names from nmw-app-<suffix> and nmw-app-kv-<suffix>, so keep the default unless you know you don't need it."
  type        = string
  default     = "nmw-app"
}

variable "name_suffix" {
  description = "Suffix for globally unique names. Null derives one from the subscription and resource group, the way Nerdio's template does."
  type        = string
  default     = null
  validation {
    condition     = var.name_suffix == null || can(regex("^[a-z0-9]{4,13}$", var.name_suffix))
    error_message = "name_suffix must be 4 to 13 lowercase letters or digits."
  }
}

variable "azure_tag_prefix" {
  description = "Prefix Nerdio uses for the tags it writes (NMW by default)."
  type        = string
  default     = "NMW"
}

variable "app_service_plan_sku" {
  description = "App Service plan SKU. Nerdio's template uses B3."
  type        = string
  default     = "B3"
}

variable "database_sku" {
  description = "Azure SQL database SKU. Nerdio's template uses S1."
  type        = string
  default     = "S1"
}

variable "database_max_size_gb" {
  description = "Maximum database size."
  type        = number
  default     = 250
}

variable "entra_app" {
  description = "The Nerdio Entra app from modules/nerdio-identity: application (object path) ID, client ID and service principal object ID."
  type = object({
    application_id              = string
    client_id                   = string
    service_principal_object_id = string
  })
}

variable "managed_resource_group_ids" {
  description = "Resource groups Nerdio manages (host pools, network, storage), keyed by role. Nerdio's service principal gets Contributor on each, instead of on the whole subscription."
  type        = map(string)
  default     = {}
}

variable "assign_builtin_rbac" {
  description = "Grant Nerdio's service principal built-in Contributor on its resource groups plus Reader and Backup Reader on the subscription. Set false when modules/nerdio-rbac assigns a custom least-privilege role instead."
  type        = bool
  default     = true
}

variable "grant_admin_consent" {
  description = "Grant the SQL server's identity the Graph read roles it needs to resolve the Entra admin group. Needs Global Administrator or Privileged Role Administrator."
  type        = bool
  default     = false
}

variable "package_version" {
  description = "Nerdio Manager version to install, or \"latest\". Changing it later runs the install job again (an upgrade); Nerdio also updates itself."
  type        = string
  default     = "latest"
}

variable "maintenance_service_url" {
  description = "Nerdio's package service."
  type        = string
  default     = "https://nwp-web-app.azurewebsites.net"
}

variable "certificate_validity_months" {
  description = "Lifetime of the self-signed certificates the Nerdio app signs in with. Key Vault renews them 30 days before expiry."
  type        = number
  default     = 12
}

variable "public_network_access_enabled" {
  description = "Public access to SQL, Key Vault and storage. Turn off only after private endpoints exist (modules/nerdio-hardening)."
  type        = bool
  default     = true
}

variable "web_app_public_network_access_enabled" {
  description = "Public access to the Nerdio console. Turn off only with a private endpoint and a route into the VNet."
  type        = bool
  default     = true
}

variable "deployer_object_id" {
  description = "Object ID of the identity that applies this configuration. Null means whoever runs Terraform. The deploy pipeline sets it, because it plans as a read-only identity and applies as another."
  type        = string
  default     = null
}

variable "cloud" {
  description = "Azure cloud environment: public (AzureCloud) or usgovernment (AzureUSGovernment)."
  type        = string
  default     = "public"

  validation {
    condition     = contains(["public", "usgovernment"], var.cloud)
    error_message = "cloud must be public or usgovernment."
  }
}

variable "dr_location" {
  description = "Optional paired Azure region for Azure SQL geo-replication and automatic failover group (null skips)."
  type        = string
  default     = null
}

variable "purge_protection_enabled" {
  description = "Enable Key Vault purge protection (recommended true for production; false allows clean teardown in sandbox/dev)."
  type        = bool
  default     = false
}

variable "enable_staging_slot" {
  description = "Create a staging deployment slot on the Nerdio Manager App Service for blue/green version upgrades."
  type        = bool
  default     = false
}

variable "autoscale" {
  description = "Optional CPU-based autoscale settings for the Nerdio Manager App Service Plan (null keeps a fixed instance count)."
  type = object({
    min_capacity          = optional(number, 1)
    default_capacity      = optional(number, 1)
    max_capacity          = optional(number, 3)
    scale_out_cpu_percent = optional(number, 75)
    scale_in_cpu_percent  = optional(number, 25)
  })
  default = null
}
