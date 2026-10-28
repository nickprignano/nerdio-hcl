mock_provider "azurerm" {}

variables {
  prefix              = "test"
  location            = "eastus2"
  resource_group_name = "rg-test"
}

run "defaults" {
  command = plan

  assert {
    condition     = length(azurerm_private_dns_zone.this) == 5
    error_message = "Expected the five privatelink zones by default."
  }

  assert {
    condition     = length(azurerm_nat_gateway.this) == 1
    error_message = "Expected a NAT gateway by default."
  }

  assert {
    condition     = length(azurerm_virtual_network_peering.to_hub) == 0 && length(azurerm_virtual_hub_connection.to_vwan) == 0
    error_message = "No peering or vWAN connection without hub_vnet_id or virtual_hub_id."
  }

  assert {
    condition     = one(azurerm_subnet.app_integration.delegation).service_delegation[0].name == "Microsoft.Web/serverFarms"
    error_message = "App integration subnet must be delegated to Microsoft.Web/serverFarms."
  }
}

run "hub_owns_dns_and_egress" {
  command = plan

  variables {
    connectivity_mode        = "hub_peering"
    hub_vnet_id              = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-hub/providers/Microsoft.Network/virtualNetworks/vnet-hub"
    create_private_dns_zones = false
    create_nat_gateway       = false
    firewall_next_hop_ip     = "10.0.1.4"
    existing_private_dns_zone_ids = {
      sql = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-dns/providers/Microsoft.Network/privateDnsZones/privatelink.database.windows.net"
    }
    link_existing_private_dns_zones = true
  }

  assert {
    condition     = length(azurerm_private_dns_zone.this) == 0 && length(azurerm_nat_gateway.this) == 0
    error_message = "Zones and NAT gateway should be skipped."
  }

  assert {
    condition     = length(azurerm_private_dns_zone_virtual_network_link.existing) == 1
    error_message = "Existing Private DNS zone should be linked to the spoke VNet."
  }

  assert {
    condition     = length(azurerm_route_table.session_hosts) == 1 && length(azurerm_route_table.session_hosts[0].route) == 2
    error_message = "Expected a firewall UDR route table with 0.0.0.0/0 and WindowsVirtualDesktop bypass."
  }

  assert {
    condition     = output.private_dns_zone_ids["sql"] == "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-dns/providers/Microsoft.Network/privateDnsZones/privatelink.database.windows.net"
    error_message = "Existing zone IDs should pass through."
  }
}

run "vwan_spoke_and_extra_dns_zones" {
  command = plan

  variables {
    connectivity_mode       = "vwan"
    virtual_hub_id          = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-vwan/providers/Microsoft.Network/virtualHubs/vhub-eastus2"
    create_nat_gateway      = false
    extra_private_dns_zones = ["automation", "wvd"]
  }

  assert {
    condition     = length(azurerm_virtual_hub_connection.to_vwan) == 1
    error_message = "Expected Virtual WAN hub connection."
  }

  assert {
    condition     = length(azurerm_private_dns_zone.this) == 7
    error_message = "Expected 7 Private DNS zones when automation and wvd are enabled."
  }
}

run "vnet_runner_subnet_delegation" {
  command = plan

  variables {
    subnets = {
      session_hosts     = "10.50.0.0/22"
      private_endpoints = "10.50.4.0/27"
      app_integration   = "10.50.4.32/27"
      vnet_runner       = "10.50.4.96/27"
    }
  }

  assert {
    condition     = length(azurerm_subnet.vnet_runner) == 1 && one(azurerm_subnet.vnet_runner[0].delegation).service_delegation[0].name == "Microsoft.App/environments"
    error_message = "Expected snet-vnet-runner delegated to Microsoft.App/environments."
  }
}
