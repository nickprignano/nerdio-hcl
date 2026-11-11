// Bicep variant of modules/nerdio-identity: Nerdio's Entra app, its app roles, admin consent and
// the REST API client app that stage 2 signs in with (decision 0032).
//
// Microsoft Graph resources aren't supported in deployment stacks or what-if, so this is its own
// plain deployment (az deployment sub create), with no preview. See bicep/README.md.
//
// Not ported: client secrets. The Graph extension can't create passwords, so the REST client's
// secret for stage 2 is a separate step (README, "REST API client secret").

targetScope = 'subscription'

extension microsoftGraphV1

@description('App registration name. Change it when running more than one Nerdio Manager in a tenant.')
param display_name string = 'nerdio-nmw-app'

@description('Create nerdio-nmw-app here. False when Nerdio\'s install script created it; then set existing_client_id.')
param create_entra_app bool = true

@description('Client ID of an existing nerdio-nmw-app, when create_entra_app is false.')
param existing_client_id string?

@description('Nerdio Manager App Service hostname, for the redirect URIs. Leave empty until Nerdio is installed, then deploy again with it.')
param app_service_hostname string?

param owner_object_ids string[] = []
param wvd_admin_object_ids string[] = []

@description('Tenant-wide admin consent. Needs Privileged Role Administrator or Global Administrator on whoever deploys.')
param grant_admin_consent bool = false

param enable_mail_send bool = false
param create_rest_api_client bool = true

@description('Federated credentials on the REST API client app, keyed by name.')
param rest_api_federated_credentials object = {}

param rest_api_additional_principal_object_ids string[] = []

// Published first-party app IDs, the same in every tenant.
var graphAppId = '00000003-0000-0000-c000-000000000000'
var asmAppId = '797f4846-ba00-4fd7-ba43-dac1f8f63013'
var restClientRoleId = '3807160f-e77a-4fcf-959a-df572bcc3767'
var wvdAdminRoleId = 'd1c2ade8-98f8-45fd-aa4a-6d06b947c66f'

var owners = union([deployer().objectId], owner_object_ids)

resource graphSp 'Microsoft.Graph/servicePrincipals@v1.0' existing = {
  appId: graphAppId
}

resource asmSp 'Microsoft.Graph/servicePrincipals@v1.0' existing = {
  appId: asmAppId
}

// Both passes take the same parameters; only identifierUris differs.
module appFirstPass 'modules/identity/nerdio-app.bicep' = if (create_entra_app) {
  name: 'nerdio-app-1'
  params: {
    uniqueName: display_name
    displayName: display_name
    ownerObjectIds: owners
    appServiceHostname: app_service_hostname
    enableMailSend: enable_mail_send
    graphAppId: graphAppId
    graphScopes: graphSp.oauth2PermissionScopes
    graphRoles: graphSp.appRoles
    asmAppId: asmAppId
    asmScopes: asmSp.oauth2PermissionScopes
  }
}

// The REST API needs api://<client_id>, which needs the appId from the first pass.
module app 'modules/identity/nerdio-app.bicep' = if (create_entra_app) {
  name: 'nerdio-app-2'
  params: {
    uniqueName: display_name
    displayName: display_name
    ownerObjectIds: owners
    appServiceHostname: app_service_hostname
    enableMailSend: enable_mail_send
    graphAppId: graphAppId
    graphScopes: graphSp.oauth2PermissionScopes
    graphRoles: graphSp.appRoles
    asmAppId: asmAppId
    asmScopes: asmSp.oauth2PermissionScopes
    identifierUris: ['api://${appFirstPass.?outputs.appId ?? ''}']
  }
}

resource sp 'Microsoft.Graph/servicePrincipals@v1.0' = if (create_entra_app) {
  appId: app.?outputs.appId ?? ''
  appRoleAssignmentRequired: false
  tags: ['WindowsAzureActiveDirectoryIntegratedApp'] // shows it under Enterprise applications
  owners: { relationships: owners }
}

resource existingSp 'Microsoft.Graph/servicePrincipals@v1.0' existing = if (!create_entra_app) {
  appId: existing_client_id ?? ''
}

var clientId = create_entra_app ? (app.?outputs.appId ?? '') : (existing_client_id ?? '')
var spObjectId = create_entra_app ? sp.id : existingSp.id

resource wvdAdmins 'Microsoft.Graph/appRoleAssignedTo@v1.0' = [
  for id in wvd_admin_object_ids: {
    appRoleId: wvdAdminRoleId
    principalId: id
    resourceId: spObjectId
  }
]

// Admin consent: tenant-wide delegated grants plus application permission assignments.
resource graphGrant 'Microsoft.Graph/oauth2PermissionGrants@v1.0' = if (create_entra_app && grant_admin_consent) {
  clientId: sp.id
  consentType: 'AllPrincipals'
  resourceId: graphSp.id
  scope: join(app.?outputs.graphDelegated ?? [], ' ')
}

resource asmGrant 'Microsoft.Graph/oauth2PermissionGrants@v1.0' = if (create_entra_app && grant_admin_consent) {
  clientId: sp.id
  consentType: 'AllPrincipals'
  resourceId: asmSp.id
  scope: 'user_impersonation'
}

var graphApplication = ['Group.Read.All', 'GroupMember.Read.All', 'Organization.Read.All', 'User.Read.All']

resource graphRoles 'Microsoft.Graph/appRoleAssignedTo@v1.0' = [
  for role in graphApplication: if (create_entra_app && grant_admin_consent) {
    appRoleId: filter(graphSp.appRoles, r => r.value == role)[0].id
    principalId: sp.id
    resourceId: graphSp.id
  }
]

// ---- REST API client app (Terraform: rest_api.tf) ----

resource restApp 'Microsoft.Graph/applications@v1.0' = if (create_rest_api_client) {
  uniqueName: '${display_name}-rest-client'
  displayName: '${display_name}-rest-client'
  signInAudience: 'AzureADMyOrg'
  owners: { relationships: owners }
  tags: ['NMW_REST_API_CLIENT:${clientId}']
  requiredResourceAccess: [
    {
      resourceAppId: clientId
      resourceAccess: [{ id: restClientRoleId, type: 'Role' }]
    }
  ]

  resource fic 'federatedIdentityCredentials@v1.0' = [
    for c in items(rest_api_federated_credentials): {
      name: '${restApp.uniqueName}/${c.key}'
      issuer: c.value.issuer
      subject: c.value.subject
      description: c.value.?description ?? 'Federated identity credential for Nerdio REST API client'
      audiences: c.value.?audiences ?? ['api://AzureADTokenExchange']
    }
  ]
}

resource restSp 'Microsoft.Graph/servicePrincipals@v1.0' = if (create_rest_api_client) {
  appId: restApp.appId
  owners: { relationships: owners }
}

resource restRole 'Microsoft.Graph/appRoleAssignedTo@v1.0' = if (create_rest_api_client && grant_admin_consent) {
  appRoleId: restClientRoleId
  principalId: restSp.id
  resourceId: spObjectId
}

resource restRoleAdditional 'Microsoft.Graph/appRoleAssignedTo@v1.0' = [
  for id in rest_api_additional_principal_object_ids: if (grant_admin_consent) {
    appRoleId: restClientRoleId
    principalId: id
    resourceId: spObjectId
  }
]

// Same names as the Terraform outputs and nerdio_config_inputs, so the pipeline can merge them.
output client_id string = clientId
output service_principal_object_id string = spObjectId
output nme_client_id string = create_rest_api_client ? restApp.appId : ''
output nme_scope string = 'api://${clientId}/.default'
output rest_api_client_object_id string = create_rest_api_client ? restApp.id : ''
