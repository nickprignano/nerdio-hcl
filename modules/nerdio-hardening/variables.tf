variable "location" {
  description = "Azure region."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group for the private endpoints (usually the Nerdio core group)."
  type        = string
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}

variable "app_service_id" {
  description = "Nerdio Manager App Service ID."
  type        = string
}

variable "app_integration_subnet_id" {
  description = "Subnet delegated to Microsoft.Web/serverFarms for outbound VNet integration."
  type        = string
}

variable "private_endpoint_subnet_id" {
  description = "Subnet for private endpoints."
  type        = string
}

variable "private_dns_zone_ids" {
  description = "privatelink zone IDs keyed by sql, vault, web, blob (optional), automation (optional)."
  type        = map(string)
}

variable "sql_server_ids" {
  description = "Map of SQL server name to ID."
  type        = map(string)
}

variable "key_vault_ids" {
  description = "Map of Key Vault name to ID."
  type        = map(string)
}

variable "storage_account_ids" {
  description = "Map of Nerdio data-protection storage account name to ID for blob private endpoints."
  type        = map(string)
  default     = {}
}

variable "automation_account_ids" {
  description = "Map of Nerdio Automation account name to ID for DSCAndHybridWorker private endpoints."
  type        = map(string)
  default     = {}
}

variable "private_app_service" {
  description = "Also give the App Service an inbound private endpoint (Nerdio's MakeAppServicePrivate). Admins then need a route into the VNet to reach the console."
  type        = bool
  default     = false
}

variable "disable_public_access" {
  description = <<-EOT
    Turn off public network access on the SQL servers, Key Vaults, storage accounts and
    Automation accounts with the az CLI after the private endpoints exist. These resources
    belong to the Marketplace deployment, so Terraform changes only this one flag rather
    than taking them over. Requires az on the machine running Terraform.
  EOT
  type        = bool
  default     = false
}

variable "lockdown_with_cli" {
  description = "Turn off public access with az CLI calls. Needed only for resources Terraform doesn't own (the Marketplace install); modules/nerdio-core sets public access itself."
  type        = bool
  default     = true
}
