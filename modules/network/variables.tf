variable "prefix" {
  description = "Short naming prefix."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group for the AVD virtual network."
  type        = string
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}

variable "address_space" {
  description = "Address space for the AVD spoke VNet."
  type        = list(string)
  default     = ["10.50.0.0/20"]
}

variable "subnets" {
  description = <<-EOT
    Subnet CIDRs. session_hosts is where Nerdio places host pool VMs,
    private_endpoints holds PEs for SQL/Key Vault/storage, and app_integration
    is delegated to Microsoft.Web for Nerdio Manager App Service VNet integration.
  EOT
  type = object({
    session_hosts     = string
    private_endpoints = string
    app_integration   = string
  })
  default = {
    session_hosts     = "10.50.0.0/22"
    private_endpoints = "10.50.4.0/27"
    app_integration   = "10.50.4.32/27"
  }
}

variable "dns_servers" {
  description = "Custom DNS servers (AD DS / Entra DS domain controllers or a DNS resolver). Empty uses Azure DNS."
  type        = list(string)
  default     = []
}

variable "hub_vnet_id" {
  description = "Optional hub VNet ID to peer with (domain connectivity, firewall, on-prem). Null skips peering."
  type        = string
  default     = null
}

variable "use_remote_gateways" {
  description = "Use the hub's VPN/ExpressRoute gateway from the spoke. Only valid with hub_vnet_id."
  type        = bool
  default     = false
}

variable "create_private_dns_zones" {
  description = "Create privatelink DNS zones in this spoke. Set false when the hub owns them and pass existing_private_dns_zone_ids instead."
  type        = bool
  default     = true
}

variable "existing_private_dns_zone_ids" {
  description = "Existing privatelink zone IDs keyed by sql, vault, file, blob, web. Used when create_private_dns_zones is false."
  type        = map(string)
  default     = {}
}

variable "create_nat_gateway" {
  description = "Give session hosts outbound internet through a NAT gateway. Set false when a hub firewall handles egress."
  type        = bool
  default     = true
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
