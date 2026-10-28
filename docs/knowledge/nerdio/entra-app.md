---
title: "Nerdio Entra app (`nerdio-nmw-app`)"
summary: "The nerdio-nmw-app registration, permissions, app roles and the REST API client"
topic: nerdio
status: verified
last_reviewed: 2026-10-28
---

# Nerdio Entra app (`nerdio-nmw-app`)

Nerdio's install script normally creates this app. Creating it yourself (in Terraform with the
`azuread` provider) lets tenants with strict app-registration policies review it as code.
Sources: [Advanced installation: Create Entra ID application](https://nmehelp.getnerdio.com/hc/en-us/articles/26124326326669),
[Manage Primary App Registration Secrets](https://nmehelp.getnerdio.com/hc/en-us/articles/42787725465229-Manage-Nerdio-Manager-Primary-App-Registration-Secrets),
[Direct Group Ownership Permissions](https://nmehelp.getnerdio.com/hc/en-us/articles/25499377856013-Direct-Group-Ownership-Permissions-for-Nerdio-Manager).

## Registration

- Sign-in audience: single-tenant (`AzureADMyOrg`) in Nerdio's updated advanced-install script
  (updated 2026-10-23; multitenant `AzureADMultipleOrgs` is only needed for multi-Entra scenarios).
- Redirect URIs: `https://<app>.azurewebsites.net/` and `https://<app>.azurewebsites.net/signin-oidc`.
- Logout URL: `https://<app>.azurewebsites.net/signout-oidc`. Nerdio's updated Graph PowerShell
  script leaves implicit grant access and ID tokens disabled (`EnableAccessTokenIssuance = $false`,
  `EnableIdTokenIssuance = $false`) and uses Microsoft Graph PowerShell (`Connect-MgGraph`), which
  is preinstalled in Azure Cloud Shell.
- The deploying user must be an **Owner** of the service principal.
- The portal may cap client secrets at 2 years; Nerdio's script sets 10 (`AddYears(10)`).

## App roles (published IDs, same in every tenant)

| Role | ID |
|---|---|
| WvdAdmin | `d1c2ade8-98f8-45fd-aa4a-6d06b947c66f` |
| DesktopAdmin | `ed0cdef0-4267-4470-bfff-5e0b6944f9e4` |
| HelpDesk | `a94e83da-b314-4232-b8c8-94508c5ed533` |
| Reviewer | `0a1b7425-f55a-44a6-9caa-b9a5cc9448da` |
| EndUser | `e856de81-1e53-486a-8668-7d564866ae39` |
| RestClient (Application) | `3807160f-e77a-4fcf-959a-df572bcc3767` |

## API permissions

- **Microsoft Graph, delegated:** User.Read, User.ReadBasic.All, User.Read.All, Group.Read.All,
  GroupMember.Read.All, Application.Read.All, Organization.Read.All,
  AppRoleAssignment.ReadWrite.All, Application.ReadWrite.All, offline_access, openid, profile,
  and optionally Mail.Send.
- **Microsoft Graph, application:** Group.Read.All, GroupMember.Read.All, Organization.Read.All, User.Read.All.
- **Azure Service Management, delegated:** user_impersonation.
- The install script uses `Directory.Read.All`. If you grant the individual scopes above instead,
  set the app setting `AzureAD:DefaultGraphScopes`.

## Trade-off of bringing your own app

No automation app is created, so later Nerdio updates run from Cloud Shell or PowerShell.

## REST API client

Source: https://nmehelp.getnerdio.com/hc/en-us/articles/27422824784269

1. On `nerdio-nmw-app`, set the identifier URI to `api://<app-id>` and
   `accessTokenAcceptedVersion` to 2.
2. Create a second app tagged `NMW_REST_API_CLIENT:<app-id>` (where `<app-id>` is the primary
   `nerdio-nmw-app` Application/client ID, the same `resourceAppId` used in `requiredResourceAccess`)
   with an application permission to the `RestClient` role, and grant admin consent.
3. The scope to use (`api://<nerdio-nmw-app-client-id>/.default`) is shown in Nerdio under
   **Settings > Integrations**.
4. PowerShell access: the `NerdioManagerPowerShell` module (`Connect-NME`, `Get-nmeworkspace`).

This REST client is also what the `nerdio/nme` Terraform provider authenticates as; see
[terraform-provider.md](terraform-provider.md).

## azuread 3.x patterns that worked

- Look up service principals by `client_id`.
- `azuread_application_published_app_ids` (keys `MicrosoftGraph`, `AzureServiceManagement`) plus
  `oauth2_permission_scope_ids[...]` / `app_role_ids[...]` to resolve permission IDs.
- `azuread_application_identifier_uri` as a separate resource, because `api://<client_id>` can't
  be set on the application in the same resource that creates it.
- `azuread_service_principal_delegated_permission_grant` for admin consent.
- `azuread_application_password` with `rotate_when_changed` driven by `time_rotating`. It always
  stores the secret in state, and azuread 3.x has no write-only arguments. Vault, or Key Vault with
  `value_wo` and ephemeral resources, keeps it out (see [../stack-options.md](../stack-options.md)).
