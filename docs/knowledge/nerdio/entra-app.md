# Nerdio Entra app (`nerdio-nmw-app`)

Nerdio's install script normally creates this app. Creating it yourself (in Terraform with the
`azuread` provider) lets tenants with strict app-registration policies review it as code.
Source: https://nmehelp.getnerdio.com/hc/en-us/articles/26124326326669

## Registration

- Sign-in audience: multitenant (`AzureADMultipleOrgs`).
- Redirect URIs: `https://<app>.azurewebsites.net/` and `https://<app>.azurewebsites.net/signin-oidc`.
- Logout URL: `/signout-oidc`. Implicit grant for access and ID tokens enabled.
- The deploying user must be an **Owner** of the service principal.
- The portal may cap client secrets at 2 years; Nerdio's script sets 10.

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
2. Create a second app tagged `NMW_REST_API_CLIENT:<app-id>` with an application permission to
   the RestClient role, and grant consent.
3. The scope to use is shown in Nerdio under **Settings > Integrations**.
4. PowerShell access: the `NerdioManagerPowerShell` module (`Connect-NME`, `Get-nmeworkspace`).

*Unverified:* which app ID goes in the tag. Nerdio's article is ambiguous; confirm under
**Settings > Integrations** after enabling.

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

_Last reviewed: 2026-10-16_
