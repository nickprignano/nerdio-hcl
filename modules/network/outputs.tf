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
  value = merge(
    {
      session_hosts     = azurerm_subnet.session_hosts.id
      private_endpoints = azurerm_subnet.private_endpoints.id
      app_integration   = azurerm_subnet.app_integration.id
    },
    var.subnets.vnet_runner != null ? { vnet_runner = azurerm_subnet.vnet_runner[0].id } : {}
  )
}

output "private_dns_zone_ids" {
  description = "privatelink zone IDs keyed by sql, vault, file, blob, web (and optional automation, wvd)."
  value = var.create_private_dns_zones ? {
    for k, z in azurerm_private_dns_zone.this : k => z.id
  } : var.existing_private_dns_zone_ids
}

output "session_host_subnet_name" {
  description = "Session host subnet name, linked in Nerdio as the AVD network."
  value       = azurerm_subnet.session_hosts.name
}

output "route_table_id" {
  description = "Session host route table ID when firewall_next_hop_ip is configured, or null."
  value       = try(azurerm_route_table.session_hosts[0].id, null)
}

output "vwan_connection_id" {
  description = "Virtual WAN hub connection ID when virtual_hub_id is configured, or null."
  value       = try(azurerm_virtual_hub_connection.to_vwan[0].id, null)
}
