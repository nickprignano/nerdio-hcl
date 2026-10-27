locals {
  base_private_dns_zones = var.cloud == "usgovernment" ? {
    sql   = "privatelink.database.usgovcloudapi.net"
    vault = "privatelink.vaultcore.usgovcloudapi.net"
    file  = "privatelink.file.core.usgovcloudapi.net"
    blob  = "privatelink.blob.core.usgovcloudapi.net"
    web   = "privatelink.azurewebsites.us"
    } : {
    sql   = "privatelink.database.windows.net"
    vault = "privatelink.vaultcore.azure.net"
    file  = "privatelink.file.core.windows.net"
    blob  = "privatelink.blob.core.windows.net"
    web   = "privatelink.azurewebsites.net"
  }

  optional_private_dns_zones = var.cloud == "usgovernment" ? {
    automation = "privatelink.azure-automation.us"
    wvd        = "privatelink.wvd.azure.us"
    } : {
    automation = "privatelink.azure-automation.net"
    wvd        = "privatelink.wvd.microsoft.com"
  }

  private_dns_zones = merge(
    local.base_private_dns_zones,
    { for k in var.extra_private_dns_zones : k => local.optional_private_dns_zones[k] }
  )
}

resource "azurerm_virtual_network" "avd" {
  name                = "vnet-${var.prefix}-avd"
  location            = var.location
  resource_group_name = var.resource_group_name
  address_space       = var.address_space
  dns_servers         = var.dns_servers
  tags                = var.tags
}

resource "azurerm_subnet" "session_hosts" {
  name                 = "snet-session-hosts"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.avd.name
  address_prefixes     = [var.subnets.session_hosts]

  dynamic "service_endpoint" {
    for_each = toset(["Microsoft.Storage", "Microsoft.KeyVault"])
    content {
      service = service_endpoint.value
    }
  }
}

resource "azurerm_subnet" "private_endpoints" {
  name                              = "snet-private-endpoints"
  resource_group_name               = var.resource_group_name
  virtual_network_name              = azurerm_virtual_network.avd.name
  address_prefixes                  = [var.subnets.private_endpoints]
  private_endpoint_network_policies = "Enabled"
}

resource "azurerm_subnet" "app_integration" {
  name                 = "snet-nerdio-app"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.avd.name
  address_prefixes     = [var.subnets.app_integration]

  dynamic "service_endpoint" {
    for_each = toset(["Microsoft.Sql", "Microsoft.KeyVault", "Microsoft.Storage"])
    content {
      service = service_endpoint.value
    }
  }

  delegation {
    name = "app-service"
    service_delegation {
      name    = "Microsoft.Web/serverFarms"
      actions = ["Microsoft.Network/virtualNetworks/subnets/action"]
    }
  }
}

# Session hosts only need outbound access to the AVD control plane; inbound stays closed.
resource "azurerm_network_security_group" "session_hosts" {
  name                = "nsg-${var.prefix}-session-hosts"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags

  security_rule {
    name                       = "allow-avd-service"
    priority                   = 100
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "WindowsVirtualDesktop"
  }

  security_rule {
    name                       = "allow-azure-cloud"
    priority                   = 110
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "AzureCloud"
  }

  security_rule {
    name                       = "allow-kms"
    priority                   = 120
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "1688"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "Internet"
  }
}

resource "azurerm_network_security_group" "private_endpoints" {
  name                = "nsg-${var.prefix}-private-endpoints"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags

  security_rule {
    name                       = "allow-vnet-inbound"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_ranges    = ["443", "445", "1433"]
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "VirtualNetwork"
  }
}

resource "azurerm_subnet_network_security_group_association" "session_hosts" {
  subnet_id                 = azurerm_subnet.session_hosts.id
  network_security_group_id = azurerm_network_security_group.session_hosts.id
}

resource "azurerm_subnet_network_security_group_association" "private_endpoints" {
  subnet_id                 = azurerm_subnet.private_endpoints.id
  network_security_group_id = azurerm_network_security_group.private_endpoints.id
}

resource "azurerm_private_dns_zone" "this" {
  for_each            = var.create_private_dns_zones ? local.private_dns_zones : {}
  name                = each.value
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "this" {
  for_each            = azurerm_private_dns_zone.this
  name                = "link-${azurerm_virtual_network.avd.name}"
  private_dns_zone_id = each.value.id
  virtual_network_id  = azurerm_virtual_network.avd.id
  tags                = var.tags
}

locals {
  # Parse zone name and resource group from ARM IDs when linking existing central Private DNS zones.
  linkable_existing_zones = (!var.create_private_dns_zones && var.link_existing_private_dns_zones) ? {
    for k, id in var.existing_private_dns_zone_ids : k => {
      id                  = id
      name                = element(split("/", id), length(split("/", id)) - 1)
      resource_group_name = element(split("/", id), index(split("/", id), "resourceGroups") + 1)
    } if length(split("/", id)) >= 9 && contains(split("/", id), "resourceGroups")
  } : {}
}

resource "azurerm_private_dns_zone_virtual_network_link" "existing" {
  for_each              = local.linkable_existing_zones
  name                  = "link-${azurerm_virtual_network.avd.name}"
  resource_group_name   = each.value.resource_group_name
  private_dns_zone_name = each.value.name
  virtual_network_id    = azurerm_virtual_network.avd.id
  tags                  = var.tags
}

resource "azurerm_virtual_network_peering" "to_hub" {
  count                     = var.hub_vnet_id == null ? 0 : 1
  name                      = "peer-to-hub"
  resource_group_name       = var.resource_group_name
  virtual_network_name      = azurerm_virtual_network.avd.name
  remote_virtual_network_id = var.hub_vnet_id
  allow_forwarded_traffic   = true
  use_remote_gateways       = var.use_remote_gateways
}

resource "azurerm_virtual_hub_connection" "to_vwan" {
  count                     = var.virtual_hub_id == null ? 0 : 1
  name                      = "vhc-${azurerm_virtual_network.avd.name}"
  virtual_hub_id            = var.virtual_hub_id
  remote_virtual_network_id = azurerm_virtual_network.avd.id
  internet_security_enabled = var.vwan_internet_security_enabled
}

resource "azurerm_route_table" "session_hosts" {
  count                         = var.firewall_next_hop_ip == null ? 0 : 1
  name                          = "rt-${var.prefix}-session-hosts"
  location                      = var.location
  resource_group_name           = var.resource_group_name
  bgp_route_propagation_enabled = false
  tags                          = var.tags

  route {
    name                   = "default-to-firewall"
    address_prefix         = "0.0.0.0/0"
    next_hop_type          = "VirtualAppliance"
    next_hop_in_ip_address = var.firewall_next_hop_ip
  }

  dynamic "route" {
    for_each = var.bypass_avd_control_plane_on_internet ? [1] : []
    content {
      name           = "avd-control-plane-direct"
      address_prefix = "WindowsVirtualDesktop"
      next_hop_type  = "Internet"
    }
  }
}

resource "azurerm_subnet_route_table_association" "session_hosts" {
  count          = var.firewall_next_hop_ip == null ? 0 : 1
  subnet_id      = azurerm_subnet.session_hosts.id
  route_table_id = azurerm_route_table.session_hosts[0].id
}

# New subnets get no default outbound internet access, so session hosts need an explicit path
# out. Use this NAT gateway, or route 0.0.0.0/0 to a hub firewall / vWAN and disable it.
resource "azurerm_public_ip" "nat" {
  count               = var.create_nat_gateway ? 1 : 0
  name                = "pip-${var.prefix}-nat"
  location            = var.location
  resource_group_name = var.resource_group_name
  allocation_method   = "Static"
  sku                 = "Standard"
  zones               = ["1", "2", "3"]
  tags                = var.tags
}

resource "azurerm_nat_gateway" "this" {
  count               = var.create_nat_gateway ? 1 : 0
  name                = "ng-${var.prefix}"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku_name            = "Standard"
  tags                = var.tags
}

resource "azurerm_nat_gateway_public_ip_association" "this" {
  count                = var.create_nat_gateway ? 1 : 0
  nat_gateway_id       = azurerm_nat_gateway.this[0].id
  public_ip_address_id = azurerm_public_ip.nat[0].id
}

resource "azurerm_subnet_nat_gateway_association" "session_hosts" {
  count          = var.create_nat_gateway ? 1 : 0
  subnet_id      = azurerm_subnet.session_hosts.id
  nat_gateway_id = azurerm_nat_gateway.this[0].id
}
