output "vnet_id" {
  description = "AVD spoke VNet ID. Peer the hub back to this (the hub side is not managed here)."
  value       = azurerm_virtual_network.avd.id
}

output "vnet_name" {
  description = "AVD spoke VNet name, selected as the AVD network in the Nerdio setup wizard."
  value       = azurerm_virtual_network.avd.name
}

output "subnet_ids" {
  description = "Subnet IDs keyed by role."
  value = {
    session_hosts     = azurerm_subnet.session_hosts.id
    private_endpoints = azurerm_subnet.private_endpoints.id
    app_integration   = azurerm_subnet.app_integration.id
  }
}

output "private_dns_zone_ids" {
  description = "privatelink zone IDs keyed by sql, vault, file, blob, web."
  value = var.create_private_dns_zones ? {
    for k, z in azurerm_private_dns_zone.this : k => z.id
  } : var.existing_private_dns_zone_ids
}
