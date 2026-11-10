// Bicep variant of stage 01 (environments/example/01-platform), landing-zone slice.
// Proposed in decision 0032. Same answers, same names, same layout as the Terraform root; the
// parity table in bicep/README.md lists what is ported and what is still Terraform-only.
//
// Plan (what-if) and deploy from Cloud Shell Bash; see bicep/README.md.

targetScope = 'subscription'

import { regionType, imageGalleryType } from 'types.bicep'

@description('Short naming prefix, e.g. "contoso-nme".')
param prefix string

@description('Azure region that hosts the Nerdio Manager control plane.')
param control_plane_location string = 'eastus2'

@description('Azure cloud: public or usgovernment.')
@allowed(['public', 'usgovernment'])
param cloud string = 'public'

@description('Tags applied to every resource.')
param tags object = {}

@description('Control-plane resource group names keyed by role (nerdio, monitoring).')
param resource_groups object

@description('Role keys in resource_groups that already exist in Azure.')
param existing_resource_groups string[] = []

@description('Existing hub privatelink zone IDs keyed by sql, vault, file, blob, web, automation, wvd. Empty: the kit creates them in the control-plane region.')
param existing_private_dns_zone_ids object = {}

@description('Extra privatelink zones to create (automation, wvd).')
param extra_private_dns_zones string[] = []

@description('Peer map of AVD workload regions keyed by region name.')
param regions { *: regionType }

@description('Azure Compute Gallery for Packer images, or null to skip it.')
param image_gallery imageGalleryType?

@description('CanNotDelete locks on stateful resources (decision 0030).')
param enable_resource_locks bool = false

// ---- Locals (same rules as main.tf) ----

var regionKeys = objectKeys(regions)
var multiRegion = length(regionKeys) > 1
var controlPlaneRegionKey = contains(regionKeys, control_plane_location) ? control_plane_location : regionKeys[0]
var hubOwnsDns = !empty(existing_private_dns_zone_ids)
var controlPlaneRgs = filter(items(resource_groups), rg => contains(['nerdio', 'monitoring'], rg.key))

var gov = cloud == 'usgovernment'
var baseZones = gov
  ? {
      sql: 'privatelink.database.usgovcloudapi.net'
      vault: 'privatelink.vaultcore.usgovcloudapi.net'
      file: 'privatelink.file.core.usgovcloudapi.net'
      blob: 'privatelink.blob.core.usgovcloudapi.net'
      web: 'privatelink.azurewebsites.us'
    }
  : {
      sql: 'privatelink.database.windows.net'
      vault: 'privatelink.vaultcore.azure.net'
      file: 'privatelink.file.core.windows.net'
      blob: 'privatelink.blob.core.windows.net'
      web: 'privatelink.azurewebsites.net'
    }
var optionalZones = gov
  ? { automation: 'privatelink.azure-automation.us', wvd: 'privatelink.wvd.azure.us' }
  : { automation: 'privatelink.azure-automation.net', wvd: 'privatelink.wvd.microsoft.com' }
var privateDnsZones = union(
  baseZones,
  toObject(extra_private_dns_zones, z => z, z => optionalZones[z])
)

var regionList = [
  for r in items(regions): {
    key: r.key
    location: r.value.?location ?? r.key
    prefix: multiRegion ? '${prefix}-${r.key}' : prefix
    rgs: r.value.resource_groups
    existingRgs: r.value.?existing_resource_groups ?? []
    network: r.value.network
    fslogix: r.value.?fslogix
  }
]
var controlPlaneNetworkRg = regions[controlPlaneRegionKey].resource_groups.network

// Where each privatelink zone lives: the hub (when given) or the control-plane spoke.
var zoneIds = hubOwnsDns
  ? existing_private_dns_zone_ids
  : toObject(
      items(privateDnsZones),
      z => z.key,
      z => resourceId(subscription().subscriptionId, controlPlaneNetworkRg, 'Microsoft.Network/privateDnsZones', z.value)
    )

// ---- Resource groups (modules/foundation) ----

resource controlPlaneGroups 'Microsoft.Resources/resourceGroups@2024-03-01' = [
  for rg in controlPlaneRgs: if (!contains(existing_resource_groups, rg.key)) {
    name: rg.value
    location: control_plane_location
    tags: union(tags, { 'nerdio-kit-role': rg.key })
  }
]

var spokeGroups = flatten(map(regionList, r => map(
  filter(items(r.rgs), g => !contains(r.existingRgs, g.key)),
  g => { name: g.value, role: g.key, location: r.location }
)))

resource spokeResourceGroups 'Microsoft.Resources/resourceGroups@2024-03-01' = [
  for g in spokeGroups: {
    name: g.name
    location: g.location
    tags: union(tags, { 'nerdio-kit-role': g.role })
  }
]

module logAnalytics 'modules/log-analytics.bicep' = {
  name: 'nerdio-log-analytics'
  scope: resourceGroup(resource_groups.monitoring)
  dependsOn: [controlPlaneGroups]
  params: {
    prefix: prefix
    location: control_plane_location
    tags: tags
  }
}

// ---- Networks (modules/network) ----

module network 'modules/network.bicep' = [
  for r in regionList: {
    name: 'nerdio-network-${r.key}'
    scope: resourceGroup(r.rgs.network)
    dependsOn: [spokeResourceGroups]
    params: {
      prefix: r.prefix
      location: r.location
      tags: tags
      network: r.network
      privateDnsZones: (!hubOwnsDns && r.key == controlPlaneRegionKey) ? privateDnsZones : {}
    }
  }
]

// Links every VNet that doesn't own the zones: other regions to the control-plane zones, or all
// regions to the hub's zones. Zone IDs name their own subscription and resource group.
var dnsLinks = flatten(map(
  range(0, length(regionList)),
  i => (hubOwnsDns || regionList[i].key != controlPlaneRegionKey)
    ? map(items(zoneIds), z => { regionIndex: i, zoneId: z.value })
    : []
))

module dnsLink 'modules/dns-zone-link.bicep' = [
  for (l, n) in dnsLinks: {
    name: 'nerdio-dns-link-${n}'
    scope: resourceGroup(split(l.zoneId, '/')[2], split(l.zoneId, '/')[4])
    params: {
      zoneName: last(split(l.zoneId, '/'))
      vnetId: network[l.regionIndex].outputs.vnetId
      vnetName: network[l.regionIndex].outputs.vnetName
      tags: tags
    }
  }
]

// Only used to keep the expressions valid for regions without a vWAN hub (the module is skipped).
var hubPlaceholder = '/subscriptions/${subscription().subscriptionId}/resourceGroups/${controlPlaneNetworkRg}/providers/Microsoft.Network/virtualHubs/none'

module vwan 'modules/vwan-connection.bicep' = [
  for (r, i) in regionList: if (r.network.?virtual_hub_id != null) {
    name: 'nerdio-vwan-${r.key}'
    scope: resourceGroup(split(r.network.?virtual_hub_id ?? hubPlaceholder, '/')[2], split(r.network.?virtual_hub_id ?? hubPlaceholder, '/')[4])
    params: {
      virtualHubName: last(split(r.network.?virtual_hub_id ?? hubPlaceholder, '/'))
      vnetId: network[i].outputs.vnetId
      vnetName: network[i].outputs.vnetName
      internetSecurityEnabled: r.network.?vwan_internet_security_enabled ?? true
    }
  }
]

// ---- FSLogix storage (modules/fslogix-storage) ----

module fslogix 'modules/fslogix-storage.bicep' = [
  for (r, i) in regionList: if (r.fslogix != null) {
    name: 'nerdio-fslogix-${r.key}'
    scope: resourceGroup(r.rgs.storage)
    dependsOn: [spokeResourceGroups, network, dnsLink]
    params: {
      location: r.location
      tags: tags
      fslogix: r.fslogix!
      privateEndpointSubnetId: network[i].outputs.subnetIds.private_endpoints
      privateDnsZoneId: any(zoneIds).?file ?? ''
      lockAgainstDelete: enable_resource_locks
    }
  }
]

// ---- Image gallery (modules/image-gallery) ----

resource buildGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = if (image_gallery != null) {
  name: image_gallery.?build_resource_group_name ?? 'unused'
  location: control_plane_location
  tags: tags
}

// Same definitions as the Terraform module's default.
var imageDefinitions = {
  'win11-avd-m365': { publisher: 'AVD', offer: 'Windows11-MultiSession', sku: 'm365', acceleratedNetwork: true, hibernation: false }
  'win11-avd-gpu': { publisher: 'AVD', offer: 'Windows11-MultiSession', sku: 'gpu', acceleratedNetwork: true, hibernation: false }
}

module gallery 'modules/image-gallery.bicep' = if (image_gallery != null) {
  name: 'nerdio-image-gallery'
  scope: resourceGroup(regions[controlPlaneRegionKey].resource_groups.hostpools)
  dependsOn: [spokeResourceGroups]
  params: {
    galleryName: image_gallery.?name ?? 'unused'
    location: control_plane_location
    tags: tags
    packerPrincipalId: image_gallery.?packer_principal_id
    imageDefinitions: imageDefinitions
  }
}

module packerBuild 'modules/rg-role.bicep' = if (image_gallery.?packer_principal_id != null) {
  name: 'nerdio-packer-build-role'
  scope: resourceGroup(image_gallery.?build_resource_group_name ?? 'unused')
  dependsOn: [buildGroup]
  params: {
    principalId: image_gallery.?packer_principal_id ?? ''
    roleDefinitionGuid: 'b24988ac-6180-42a0-ab88-20f7382dd24c' // Contributor, as in the Terraform module
  }
}

// ---- Outputs (named like outputs.tf where they overlap) ----

output resource_group_names object = union(
  toObject(controlPlaneRgs, rg => rg.key, rg => rg.value),
  toObject(regionList, r => r.key, r => r.rgs)
)
// Lists of { region, ... } rather than maps: Bicep can only loop over module outputs in an output for-expression.
output vnet_ids array = [for (r, i) in regionList: { region: r.key, id: network[i].outputs.vnetId }]
output subnet_ids array = [for (r, i) in regionList: { region: r.key, ids: network[i].outputs.subnetIds }]
output private_dns_zone_ids object = zoneIds
output log_analytics_workspace_id string = logAnalytics.outputs.id
output image_gallery_id string = gallery.?outputs.galleryId ?? ''

// What the Terraform config stage (02-nerdio-config) needs, in the same shape as the Terraform
// output of this name, so the pipeline can run stage 2 after the stack. Every value is derived
// from inputs and the kit's naming, not read back from Azure. The nme_* values come from the
// identity and Nerdio install slices, which aren't ported yet, so they are null for now and
// stage 2 can't run against a Bicep-only platform until they are.
var fileSuffix = 'file.${environment().suffixes.storage}'
output nerdio_config_inputs object = {
  nme_base_url: null
  nme_tenant_id: tenant().tenantId
  nme_client_id: null
  nme_scope: null
  subscription_id: subscription().subscriptionId
  control_plane_location: control_plane_location
  regions: toObject(regionList, r => r.key, r => {
    location: r.location
    subscription_id: subscription().subscriptionId
    hostpools_resource_group_name: r.rgs.hostpools
    network: {
      resource_group_name: r.rgs.network
      vnet_name: 'vnet-${r.prefix}-avd'
      subnet_name: 'snet-session-hosts'
    }
    fslogix_profile_share_unc: r.fslogix == null ? null : '\\\\${r.fslogix!.storage_account_name}.${fileSuffix}\\profiles'
    app_attach_share_unc: r.fslogix.?app_attach_share_quota_gb == null ? null : '\\\\${r.fslogix!.storage_account_name}.${fileSuffix}\\appattach'
    disk_encryption_set_id: null
  })
  gallery_image_definition_ids: image_gallery == null ? {} : toObject(
    objectKeys(imageDefinitions),
    d => d,
    d => resourceId(regions[controlPlaneRegionKey].resource_groups.hostpools, 'Microsoft.Compute/galleries/images', image_gallery.?name ?? '', d)
  )
  nme_secret_source: null
  nme_key_vault: null
  openbao: null
}

output nerdio_url string = '' // set once the Nerdio install slice is ported
output avd_vnet_names object = toObject(regionList, r => r.key, r => 'vnet-${r.prefix}-avd')
