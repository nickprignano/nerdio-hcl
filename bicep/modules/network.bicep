// Mirrors modules/network: one regional spoke VNet with the kit's subnets, NSGs, optional NAT
// gateway, optional hub peering and firewall route table, and (in the control-plane region only)
// the privatelink DNS zones. Cross-resource-group pieces (vWAN hub connection, links to zones in
// another region or a hub) are separate modules called from main.bicep.

import { networkType } from '../types.bicep'

param prefix string
param location string
param tags object
param network networkType

@description('privatelink zones to create here and link to this VNet, keyed like the Terraform module (sql, vault, file, ...).')
param privateDnsZones object = {}

var vnetName = 'vnet-${prefix}-avd'
var createNat = network.?create_nat_gateway ?? true
var firewallIp = network.?firewall_next_hop_ip
var natId = resourceId('Microsoft.Network/natGateways', 'ng-${prefix}')
var routeTableId = resourceId('Microsoft.Network/routeTables', 'rt-${prefix}-session-hosts')

// Session hosts only need outbound access to the AVD control plane; inbound stays closed.
resource nsgSessionHosts 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: 'nsg-${prefix}-session-hosts'
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'allow-avd-service'
        properties: {
          priority: 100
          direction: 'Outbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '443'
          sourceAddressPrefix: 'VirtualNetwork'
          destinationAddressPrefix: 'WindowsVirtualDesktop'
        }
      }
      {
        name: 'allow-azure-cloud'
        properties: {
          priority: 110
          direction: 'Outbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '443'
          sourceAddressPrefix: 'VirtualNetwork'
          destinationAddressPrefix: 'AzureCloud'
        }
      }
      {
        name: 'allow-kms'
        properties: {
          priority: 120
          direction: 'Outbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '1688'
          sourceAddressPrefix: 'VirtualNetwork'
          destinationAddressPrefix: 'Internet'
        }
      }
    ]
  }
}

resource nsgPrivateEndpoints 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: 'nsg-${prefix}-private-endpoints'
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'allow-vnet-inbound'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRanges: ['443', '445', '1433']
          sourceAddressPrefix: 'VirtualNetwork'
          destinationAddressPrefix: 'VirtualNetwork'
        }
      }
    ]
  }
}

// New subnets get no default outbound internet access, so session hosts need an explicit path
// out. Use this NAT gateway, or route 0.0.0.0/0 to a hub firewall / vWAN and turn it off.
resource natIp 'Microsoft.Network/publicIPAddresses@2024-05-01' = if (createNat) {
  name: 'pip-${prefix}-nat'
  location: location
  tags: tags
  sku: { name: 'Standard' }
  zones: ['1', '2', '3']
  properties: { publicIPAllocationMethod: 'Static' }
}

resource nat 'Microsoft.Network/natGateways@2024-05-01' = if (createNat) {
  name: 'ng-${prefix}'
  location: location
  tags: tags
  sku: { name: 'Standard' }
  properties: {
    publicIpAddresses: [{ id: natIp.id }]
  }
}

resource routeTable 'Microsoft.Network/routeTables@2024-05-01' = if (firewallIp != null) {
  name: 'rt-${prefix}-session-hosts'
  location: location
  tags: tags
  properties: {
    disableBgpRoutePropagation: true
    routes: concat(
      [
        {
          name: 'default-to-firewall'
          properties: {
            addressPrefix: '0.0.0.0/0'
            nextHopType: 'VirtualAppliance'
            nextHopIpAddress: firewallIp
          }
        }
      ],
      (network.?bypass_avd_control_plane_on_internet ?? true)
        ? [
            {
              name: 'avd-control-plane-direct'
              properties: {
                addressPrefix: 'WindowsVirtualDesktop'
                nextHopType: 'Internet'
              }
            }
          ]
        : []
    )
  }
}

var baseSubnets = [
  {
    name: 'snet-session-hosts'
    properties: {
      addressPrefix: network.subnets.session_hosts
      serviceEndpoints: [{ service: 'Microsoft.Storage' }, { service: 'Microsoft.KeyVault' }]
      networkSecurityGroup: { id: nsgSessionHosts.id }
      natGateway: createNat ? { id: natId } : null
      routeTable: firewallIp != null ? { id: routeTableId } : null
    }
  }
  {
    name: 'snet-private-endpoints'
    properties: {
      addressPrefix: network.subnets.private_endpoints
      privateEndpointNetworkPolicies: 'Enabled'
      networkSecurityGroup: { id: nsgPrivateEndpoints.id }
    }
  }
  {
    name: 'snet-nerdio-app'
    properties: {
      addressPrefix: network.subnets.app_integration
      serviceEndpoints: [{ service: 'Microsoft.Sql' }, { service: 'Microsoft.KeyVault' }, { service: 'Microsoft.Storage' }]
      delegations: [{ name: 'app-service', properties: { serviceName: 'Microsoft.Web/serverFarms' } }]
    }
  }
]

var runnerSubnet = network.subnets.?vnet_runner == null
  ? []
  : [
      {
        name: 'snet-vnet-runner'
        properties: {
          addressPrefix: network.subnets.vnet_runner
          delegations: [{ name: 'container-apps', properties: { serviceName: 'Microsoft.App/environments' } }]
        }
      }
    ]

// Subnets are declared inline so a redeploy never tries to remove them.
resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: vnetName
  location: location
  tags: tags
  dependsOn: [nat, routeTable]
  properties: {
    addressSpace: { addressPrefixes: network.address_space }
    dhcpOptions: empty(network.?dns_servers ?? []) ? null : { dnsServers: network.dns_servers }
    subnets: concat(baseSubnets, runnerSubnet)
  }
}

resource hubPeering 'Microsoft.Network/virtualNetworks/virtualNetworkPeerings@2024-05-01' = if (network.?hub_vnet_id != null) {
  parent: vnet
  name: 'peer-to-hub'
  properties: {
    remoteVirtualNetwork: { id: network.hub_vnet_id! }
    allowForwardedTraffic: true
    allowVirtualNetworkAccess: true
    useRemoteGateways: network.?use_remote_gateways ?? false
  }
}

resource zones 'Microsoft.Network/privateDnsZones@2024-06-01' = [for z in items(privateDnsZones): {
  name: z.value
  location: 'global'
  tags: tags
}]

resource zoneLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = [for (z, i) in items(privateDnsZones): {
  parent: zones[i]
  name: 'link-${vnetName}'
  location: 'global'
  tags: tags
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}]

output vnetId string = vnet.id
output vnetName string = vnet.name
output subnetIds object = {
  session_hosts: resourceId('Microsoft.Network/virtualNetworks/subnets', vnetName, 'snet-session-hosts')
  private_endpoints: resourceId('Microsoft.Network/virtualNetworks/subnets', vnetName, 'snet-private-endpoints')
  app_integration: resourceId('Microsoft.Network/virtualNetworks/subnets', vnetName, 'snet-nerdio-app')
}
