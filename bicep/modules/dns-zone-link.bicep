// Links one VNet to an existing privatelink zone. Deployed into the zone's resource group, which
// can be the control-plane spoke (multi-region) or a hub (existing_private_dns_zone_ids).

param zoneName string
param vnetId string
param vnetName string
param tags object

resource zone 'Microsoft.Network/privateDnsZones@2024-06-01' existing = {
  name: zoneName
}

resource link 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: zone
  name: 'link-${vnetName}'
  location: 'global'
  tags: tags
  properties: {
    virtualNetwork: { id: vnetId }
    registrationEnabled: false
  }
}
