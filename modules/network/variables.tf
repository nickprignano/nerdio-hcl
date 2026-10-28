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
    private_endpoints holds PEs for SQL/Key Vault/storage, app_integration
    is delegated to Microsoft.Web for Nerdio Manager App Service VNet integration,
    and optional vnet_runner is delegated to Microsoft.App/environments for ephemeral self-hosted runners.
  EOT
  type = object({
    session_hosts     = string
    private_endpoints = string
    app_integration   = string
    vnet_runner       = optional(string)
  })
  default = {
    session_hosts     = "10.50.0.0/22"
    private_endpoints = "10.50.4.0/27"
    app_integration   = "10.50.4.32/27"
    vnet_runner       = null
  }
}

variable "dns_servers" {
  description = "Custom DNS servers (AD DS / Entra DS domain controllers or a DNS resolver). Empty uses Azure DNS."
  type        = list(string)
  default     = []
}

variable "connectivity_mode" {
  description = "Spoke connectivity mode: standalone (NAT gateway), hub_peering (standard VNet peering), or vwan (Azure Virtual WAN hub connection)."
  type        = string
  default     = "standalone"

  validation {
    condition     = contains(["standalone", "hub_peering", "vwan"], var.connectivity_mode)
    error_message = "connectivity_mode must be standalone, hub_peering or vwan."
  }
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

variable "virtual_hub_id" {
  description = "Optional Azure Virtual WAN Virtual Hub resource ID to connect this spoke VNet to. Used when connectivity_mode is vwan or virtual_hub_id is set."
  type        = string
  default     = null
}

variable "vwan_internet_security_enabled" {
  description = "Enable internet security (Secured Virtual Hub firewall routing) on the Virtual WAN hub connection."
  type        = bool
  default     = true
}

variable "firewall_next_hop_ip" {
  description = "Optional hub Azure Firewall or NVA private IP address for forced-tunneling 0.0.0.0/0 UDR on the session host subnet."
  type        = string
  default     = null
}

variable "bypass_avd_control_plane_on_internet" {
  description = "When firewall_next_hop_ip is set, add a route sending WindowsVirtualDesktop service-tag traffic directly to Internet per Microsoft CAF guidance."
  type        = bool
  default     = true
}

variable "create_private_dns_zones" {
  description = "Create privatelink DNS zones in this spoke. Set false when the control plane or hub owns them and pass existing_private_dns_zone_ids instead."
  type        = bool
  default     = true
}

variable "extra_private_dns_zones" {
  description = "Optional extra privatelink zones to create when create_private_dns_zones is true: automation (privatelink.azure-automation.net) and/or wvd (privatelink.wvd.microsoft.com)."
  type        = set(string)
  default     = []

  validation {
    condition     = alltrue([for k in var.extra_private_dns_zones : contains(["automation", "wvd"], k)])
    error_message = "extra_private_dns_zones entries must be automation or wvd."
  }
}

variable "existing_private_dns_zone_ids" {
  description = "Existing privatelink zone IDs keyed by sql, vault, file, blob, web (and optionally automation, wvd). Used when create_private_dns_zones is false."
  type        = map(string)
  default     = {}
}

variable "link_existing_private_dns_zones" {
  description = "When create_private_dns_zones is false, create VNet links from this spoke VNet to each zone in existing_private_dns_zone_ids where the zone is in the same subscription/resource group."
  type        = bool
  default     = false
}

variable "create_nat_gateway" {
  description = "Give session hosts outbound internet through a NAT gateway. Set false when a hub firewall or vWAN handles egress."
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
