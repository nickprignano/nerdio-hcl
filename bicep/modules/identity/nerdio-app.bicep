// The nerdio-nmw-app registration (Terraform: azuread_application.nerdio in modules/nerdio-identity).
// identity.bicep deploys this module twice with the same uniqueName: first without identifier
// URIs, then with api://<appId>, because an app can't refer to its own appId in one resource.
// Both passes send the full definition, so the second never reverts the first.

targetScope = 'subscription'

extension microsoftGraphV1

param uniqueName string
param displayName string
param ownerObjectIds string[]
param appServiceHostname string?
param enableMailSend bool = false
param identifierUris string[] = []

@description('Microsoft Graph app ID (published, the same in every tenant).')
param graphAppId string
param graphScopes array
param graphRoles array
param asmAppId string
param asmScopes array

// From Nerdio's "Advanced installation: Create Entra ID application". Directory.Read.All is added
// because Nerdio's own install script requests it in place of several read scopes.
var graphDelegated = concat(
  [
    'User.Read'
    'User.ReadBasic.All'
    'User.Read.All'
    'Group.Read.All'
    'GroupMember.Read.All'
    'Application.Read.All'
    'Application.ReadWrite.All'
    'Organization.Read.All'
    'AppRoleAssignment.ReadWrite.All'
    'Directory.Read.All'
    'offline_access'
    'openid'
    'profile'
  ],
  enableMailSend ? ['Mail.Send'] : []
)
var graphApplication = ['Group.Read.All', 'GroupMember.Read.All', 'Organization.Read.All', 'User.Read.All']

// Role IDs are fixed by Nerdio; the app checks these exact values.
var appRoles = [
  { id: 'd1c2ade8-98f8-45fd-aa4a-6d06b947c66f', value: 'WvdAdmin', name: 'WVD Admin', members: ['User'] }
  { id: 'ed0cdef0-4267-4470-bfff-5e0b6944f9e4', value: 'DesktopAdmin', name: 'Desktop Admin', members: ['User'] }
  { id: 'a94e83da-b314-4232-b8c8-94508c5ed533', value: 'HelpDesk', name: 'Help Desk', members: ['User'] }
  { id: '0a1b7425-f55a-44a6-9caa-b9a5cc9448da', value: 'Reviewer', name: 'Reviewer', members: ['User'] }
  { id: 'e856de81-1e53-486a-8668-7d564866ae39', value: 'EndUser', name: 'End-user', members: ['User'] }
  { id: '3807160f-e77a-4fcf-959a-df572bcc3767', value: 'RestClient', name: 'Rest client', members: ['Application'] }
]

var base = appServiceHostname == null ? null : 'https://${appServiceHostname}'

resource app 'Microsoft.Graph/applications@v1.0' = {
  uniqueName: uniqueName
  displayName: displayName
  signInAudience: 'AzureADMultipleOrgs'
  identifierUris: identifierUris
  owners: { relationships: ownerObjectIds }
  api: { requestedAccessTokenVersion: 2 }
  web: {
    redirectUris: base == null ? [] : ['${base}/', '${base}/signin-oidc']
    logoutUrl: base == null ? null : '${base}/signout-oidc'
    implicitGrantSettings: {
      enableAccessTokenIssuance: true
      enableIdTokenIssuance: true
    }
  }
  appRoles: [
    for r in appRoles: {
      id: r.id
      value: r.value
      displayName: r.name
      description: r.name
      allowedMemberTypes: r.members
      isEnabled: true
    }
  ]
  requiredResourceAccess: [
    {
      resourceAppId: graphAppId
      resourceAccess: concat(
        map(graphDelegated, n => { id: filter(graphScopes, s => s.value == n)[0].id, type: 'Scope' }),
        map(graphApplication, n => { id: filter(graphRoles, r => r.value == n)[0].id, type: 'Role' })
      )
    }
    {
      resourceAppId: asmAppId
      resourceAccess: [
        { id: filter(asmScopes, s => s.value == 'user_impersonation')[0].id, type: 'Scope' }
      ]
    }
  ]
}

output appId string = app.appId
output graphDelegated string[] = graphDelegated
output graphApplication string[] = graphApplication
