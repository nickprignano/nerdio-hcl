// Key Vault that hands the Nerdio REST API client secret to stage 2 (decision 0015). Bicep side of
// modules/nerdio-secrets.
//
// The Microsoft Graph Bicep extension can't create client secrets, so this template only builds the
// vault and its access. bicep/rest-client-secret.sh, run by the tenant owner, creates the secret on
// the REST API client app and writes it here without printing it. Stage 2 reads it ephemerally,
// exactly as after a Terraform stage 1. Unlike Terraform, no deployment holds the value.
//
// Differences from the Terraform module: the secret doesn't exist when this deploys, so readers get
// Key Vault Secrets User on the vault rather than on the one secret. The vault is single-purpose
// (it holds only this secret), so the reach is the same; don't put other secrets in it.

param keyVaultName string
param location string
param tags object = {}

@description('Name of the secret that holds the REST API client secret.')
param secretName string = 'nme-rest-client-secret'

@description('Principal that writes the secret (Key Vault Secrets Officer): whoever runs rest-client-secret.sh.')
param writerObjectId string

@description('Principals that may read the secret in stage 2 (users, groups or service principals).')
param readerObjectIds string[] = []

@description('Optional GitHub Actions OIDC identity for "owner/name" and its environment.')
param githubOidc { repository: string, environment: string? }?

param publicNetworkAccess bool = true
param purgeProtection bool = false

// Built-in role definition IDs (public, the same in every tenant).
var officerRole = 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'  // Key Vault Secrets Officer
var userRole = '4633458b-17de-408a-b874-0445c86b69e6'  // Key Vault Secrets User
var readerRole = 'acdd72a7-3385-48ef-bd42-f606fba81ae7'  // Reader
var readers = union([writerObjectId], readerObjectIds)
var githubEnvironment = githubOidc.?environment ?? 'sandbox'

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    tenantId: tenant().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    // Purge protection can't be switched off once on, and ARM rejects an explicit false.
    enablePurgeProtection: purgeProtection ? true : null
    publicNetworkAccess: publicNetworkAccess ? 'Enabled' : 'Disabled'
    networkAcls: {
      bypass: 'None'
      defaultAction: publicNetworkAccess ? 'Allow' : 'Deny'
    }
  }
}

resource writer 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, writerObjectId, officerRole)
  scope: vault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', officerRole)
    principalId: writerObjectId
  }
}

resource secretReaders 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for id in readers: {
    name: guid(vault.id, id, userRole)
    scope: vault
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', userRole)
      principalId: id
    }
  }
]

// Reader lets the azurerm provider look up the vault's URI; it grants no access to secret values.
resource vaultReaders 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for id in readers: {
    name: guid(vault.id, id, readerRole)
    scope: vault
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', readerRole)
      principalId: id
    }
  }
]

// GitHub Actions signs in as this identity with OIDC, so the pipeline stores no Azure secret.
resource github 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (githubOidc != null) {
  name: 'id-${keyVaultName}-github'
  location: location
  tags: tags
}

resource githubCredential 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = if (githubOidc != null) {
  parent: github
  name: 'github-${githubEnvironment}'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: 'repo:${githubOidc.?repository ?? ''}:environment:${githubEnvironment}'
    audiences: ['api://AzureADTokenExchange']
  }
}

resource githubSecretReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (githubOidc != null) {
  name: guid(vault.id, 'github', userRole)
  scope: vault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', userRole)
    principalId: github.?properties.principalId ?? ''
    principalType: 'ServicePrincipal'
  }
}

resource githubVaultReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (githubOidc != null) {
  name: guid(vault.id, 'github', readerRole)
  scope: vault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', readerRole)
    principalId: github.?properties.principalId ?? ''
    principalType: 'ServicePrincipal'
  }
}

output keyVaultId string = vault.id
output keyVaultName string = vault.name
output secretName string = secretName
output githubClientId string = github.?properties.clientId ?? ''
