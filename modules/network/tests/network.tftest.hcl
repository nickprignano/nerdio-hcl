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
    condition     = length(azurerm_virtual_network_peering.to_hub) == 0
    error_message = "No peering without hub_vnet_id."
  }

  assert {
    condition     = one(azurerm_subnet.app_integration.delegation).service_delegation[0].name == "Microsoft.Web/serverFarms"
    error_message = "App integration subnet must be delegated to Microsoft.Web/serverFarms."
  }
}

run "hub_owns_dns_and_egress" {
  command = plan

  variables {
    hub_vnet_id              = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-hub/providers/Microsoft.Network/virtualNetworks/vnet-hub"
    create_private_dns_zones = false
    create_nat_gateway       = false
    existing_private_dns_zone_ids = {
      sql = "/zones/sql"
    }
  }

  assert {
    condition     = length(azurerm_private_dns_zone.this) == 0 && length(azurerm_nat_gateway.this) == 0
    error_message = "Zones and NAT gateway should be skipped."
  }

  assert {
    condition     = output.private_dns_zone_ids["sql"] == "/zones/sql"
    error_message = "Existing zone IDs should pass through."
  }
}
