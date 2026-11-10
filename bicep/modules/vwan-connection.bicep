// Connects a spoke VNet to a Virtual WAN hub. Deployed into the hub's resource group
// (Terraform: azurerm_virtual_hub_connection in modules/network).

param virtualHubName string
param vnetId string
param vnetName string
param internetSecurityEnabled bool = true

resource hub 'Microsoft.Network/virtualHubs@2024-05-01' existing = {
  name: virtualHubName
}

resource connection 'Microsoft.Network/virtualHubs/hubVirtualNetworkConnections@2024-05-01' = {
  parent: hub
  name: 'vhc-${vnetName}'
  properties: {
    remoteVirtualNetwork: { id: vnetId }
    enableInternetSecurity: internetSecurityEnabled
  }
}
