// Mirrors modules/image-gallery: the Azure Compute Gallery Packer publishes into, with Gen2 and
// Trusted Launch image definitions. The build resource group is created in main.bicep.

param galleryName string
param location string
param tags object
param packerPrincipalId string?

@description('Image definitions keyed by name, as in the Terraform module default.')
param imageDefinitions object = {
  'win11-avd-m365': { publisher: 'AVD', offer: 'Windows11-MultiSession', sku: 'm365', acceleratedNetwork: true, hibernation: false }
  'win11-avd-gpu': { publisher: 'AVD', offer: 'Windows11-MultiSession', sku: 'gpu', acceleratedNetwork: true, hibernation: false }
}

var contributor = 'b24988ac-6180-42a0-ab88-20f7382dd24c'

resource gallery 'Microsoft.Compute/galleries@2023-07-03' = {
  name: galleryName
  location: location
  tags: tags
  properties: {
    description: 'AVD golden images built by Packer and imported into Nerdio Manager'
  }
}

resource images 'Microsoft.Compute/galleries/images@2023-07-03' = [for d in items(imageDefinitions): {
  parent: gallery
  name: d.key
  location: location
  tags: tags
  properties: {
    osType: 'Windows'
    osState: 'Generalized'
    hyperVGeneration: 'V2'
    identifier: {
      publisher: d.value.publisher
      offer: d.value.offer
      sku: d.value.sku
    }
    features: [
      { name: 'SecurityType', value: 'TrustedLaunchSupported' }
      { name: 'IsAcceleratedNetworkSupported', value: string(d.value.acceleratedNetwork) }
      { name: 'IsHibernateSupported', value: string(d.value.hibernation) }
    ]
  }
}]

resource packerGallery 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (packerPrincipalId != null) {
  scope: gallery
  name: guid(gallery.id, packerPrincipalId ?? '', contributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', contributor)
    principalId: packerPrincipalId!
    principalType: 'ServicePrincipal'
  }
}

output galleryId string = gallery.id
output galleryName string = gallery.name
