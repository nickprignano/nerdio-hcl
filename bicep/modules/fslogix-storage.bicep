// Mirrors modules/fslogix-storage: a premium Azure Files account for FSLogix profiles behind a
// private endpoint, with identity-based SMB access and share-level RBAC for groups.

import { fslogixType } from '../types.bicep'

param location string
param tags object
param fslogix fslogixType
param privateEndpointSubnetId string
param privateDnsZoneId string
param shareName string = 'profiles'
param lockAgainstDelete bool = false

var identitySource = fslogix.?identity_source ?? 'AADKERB'
var ad = fslogix.?active_directory

// Published built-in role definition IDs (the same in every tenant).
var smbShareContributor = '0c867c2a-1d8c-454a-a3db-ab2ea1bdc8bb'
var smbShareElevatedContributor = 'a7264617-510b-434b-a828-9731dc254ea7'

resource account 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: fslogix.storage_account_name
  location: location
  tags: tags
  kind: 'FileStorage'
  sku: { name: 'Premium_ZRS' }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowSharedKeyAccess: true // FSLogix setup and some Nerdio actions still use keys; turn off once you're on identity-only access.
    publicNetworkAccess: 'Disabled'
    allowBlobPublicAccess: false
    azureFilesIdentityBasedAuthentication: {
      directoryServiceOptions: identitySource
      defaultSharePermission: 'None'
      activeDirectoryProperties: identitySource == 'AD'
        ? {
            domainName: ad!.domain_name
            domainGuid: ad!.domain_guid
            domainSid: ad.?domain_sid
            forestName: ad.?forest_name
            netBiosDomainName: ad.?netbios_domain_name
            azureStorageSid: ad.?storage_sid
          }
        : null
    }
  }
}

resource files 'Microsoft.Storage/storageAccounts/fileServices@2023-05-01' = {
  parent: account
  name: 'default'
  properties: {
    protocolSettings: {
      smb: {
        versions: 'SMB3.1.1;'
        authenticationMethods: 'Kerberos;'
        kerberosTicketEncryption: 'AES-256;'
        channelEncryption: 'AES-256-GCM;'
      }
    }
  }
}

resource profiles 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = {
  parent: files
  name: shareName
  properties: {
    shareQuota: fslogix.?share_quota_gb ?? 1024
    enabledProtocols: 'SMB'
  }
}

resource appAttach 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = if (fslogix.?app_attach_share_quota_gb != null) {
  parent: files
  name: 'appattach'
  properties: {
    shareQuota: fslogix.?app_attach_share_quota_gb ?? 100
    enabledProtocols: 'SMB'
  }
}

resource endpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: 'pe-${account.name}-file'
  location: location
  tags: tags
  properties: {
    subnet: { id: privateEndpointSubnetId }
    privateLinkServiceConnections: [
      {
        name: 'file'
        properties: {
          privateLinkServiceId: account.id
          groupIds: ['file']
        }
      }
    ]
  }
}

resource endpointDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: endpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      { name: 'file', properties: { privateDnsZoneId: privateDnsZoneId } }
    ]
  }
}

resource users 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for id in (fslogix.?user_group_object_ids ?? []): {
  scope: account
  name: guid(account.id, id, smbShareContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', smbShareContributor)
    principalId: id
    principalType: 'Group'
  }
}]

resource admins 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for id in (fslogix.?admin_group_object_ids ?? []): {
  scope: account
  name: guid(account.id, id, smbShareElevatedContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', smbShareElevatedContributor)
    principalId: id
    principalType: 'Group'
  }
}]

// decision 0030: CanNotDelete locks on stateful resources (on by default for prod).
resource lock 'Microsoft.Authorization/locks@2020-05-01' = if (lockAgainstDelete) {
  scope: account
  name: 'lock-${account.name}'
  properties: {
    level: 'CanNotDelete'
    notes: 'FSLogix profiles. Remove the lock deliberately before deleting.'
  }
}

output storageAccountId string = account.id
output storageAccountName string = account.name
output shareName string = profiles.name
