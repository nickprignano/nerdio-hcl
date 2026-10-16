data "azuread_client_config" "current" {}

data "azuread_application_published_app_ids" "well_known" {}

data "azuread_service_principal" "msgraph" {
  client_id = data.azuread_application_published_app_ids.well_known.result["MicrosoftGraph"]
}

data "azuread_service_principal" "azure_service_management" {
  client_id = data.azuread_application_published_app_ids.well_known.result["AzureServiceManagement"]
}

locals {
  owners = distinct(concat([data.azuread_client_config.current.object_id], var.owner_object_ids))
  base   = "https://${var.app_service_hostname}"

  # From Nerdio's "Advanced installation: Create Entra ID application". Directory.Read.All
  # is added because Nerdio's own install script requests it in place of several read scopes.
  graph_delegated = concat([
    "User.Read",
    "User.ReadBasic.All",
    "User.Read.All",
    "Group.Read.All",
    "GroupMember.Read.All",
    "Application.Read.All",
    "Application.ReadWrite.All",
    "Organization.Read.All",
    "AppRoleAssignment.ReadWrite.All",
    "Directory.Read.All",
    "offline_access",
    "openid",
    "profile",
  ], var.enable_mail_send ? ["Mail.Send"] : [])

  graph_application = [
    "Group.Read.All",
    "GroupMember.Read.All",
    "Organization.Read.All",
    "User.Read.All",
  ]

  # Role IDs are fixed by Nerdio; the app checks these exact values.
  app_roles = {
    WvdAdmin     = { id = "d1c2ade8-98f8-45fd-aa4a-6d06b947c66f", name = "WVD Admin", members = ["User"] }
    DesktopAdmin = { id = "ed0cdef0-4267-4470-bfff-5e0b6944f9e4", name = "Desktop Admin", members = ["User"] }
    HelpDesk     = { id = "a94e83da-b314-4232-b8c8-94508c5ed533", name = "Help Desk", members = ["User"] }
    Reviewer     = { id = "0a1b7425-f55a-44a6-9caa-b9a5cc9448da", name = "Reviewer", members = ["User"] }
    EndUser      = { id = "e856de81-1e53-486a-8668-7d564866ae39", name = "End-user", members = ["User"] }
    RestClient   = { id = "3807160f-e77a-4fcf-959a-df572bcc3767", name = "Rest client", members = ["Application"] }
  }
}

resource "azuread_application" "nerdio" {
  display_name     = var.display_name
  sign_in_audience = "AzureADMultipleOrgs"
  owners           = local.owners

  api {
    requested_access_token_version = 2
  }

  web {
    redirect_uris = ["${local.base}/", "${local.base}/signin-oidc"]
    logout_url    = "${local.base}/signout-oidc"

    implicit_grant {
      access_token_issuance_enabled = true
      id_token_issuance_enabled     = true
    }
  }

  dynamic "app_role" {
    for_each = local.app_roles
    content {
      id                   = app_role.value.id
      value                = app_role.key
      display_name         = app_role.value.name
      description          = app_role.value.name
      allowed_member_types = app_role.value.members
      enabled              = true
    }
  }

  required_resource_access {
    resource_app_id = data.azuread_service_principal.msgraph.client_id

    dynamic "resource_access" {
      for_each = local.graph_delegated
      content {
        id   = data.azuread_service_principal.msgraph.oauth2_permission_scope_ids[resource_access.value]
        type = "Scope"
      }
    }

    dynamic "resource_access" {
      for_each = local.graph_application
      content {
        id   = data.azuread_service_principal.msgraph.app_role_ids[resource_access.value]
        type = "Role"
      }
    }
  }

  required_resource_access {
    resource_app_id = data.azuread_service_principal.azure_service_management.client_id

    resource_access {
      id   = data.azuread_service_principal.azure_service_management.oauth2_permission_scope_ids["user_impersonation"]
      type = "Scope"
    }
  }
}

# The REST API needs api://<client_id>, which can't be set on the app in the same resource.
resource "azuread_application_identifier_uri" "nerdio" {
  application_id = azuread_application.nerdio.id
  identifier_uri = "api://${azuread_application.nerdio.client_id}"
}

resource "azuread_service_principal" "nerdio" {
  client_id                    = azuread_application.nerdio.client_id
  owners                       = local.owners
  app_role_assignment_required = false
  feature_tags {
    enterprise = true
  }
}

resource "time_rotating" "secret" {
  rotation_days = var.secret_rotation_days
}

resource "azuread_application_password" "nerdio" {
  application_id = azuread_application.nerdio.id
  display_name   = "terraform"
  end_date       = timeadd(time_rotating.secret.id, "${var.secret_rotation_days * 24 + 720}h")
  rotate_when_changed = {
    rotation = time_rotating.secret.id
  }
}

resource "azuread_app_role_assignment" "wvd_admin" {
  for_each            = toset(var.wvd_admin_object_ids)
  app_role_id         = local.app_roles.WvdAdmin.id
  principal_object_id = each.value
  resource_object_id  = azuread_service_principal.nerdio.object_id
}

# Admin consent: tenant-wide delegated grants plus application permission assignments.
resource "azuread_service_principal_delegated_permission_grant" "graph" {
  count                                = var.grant_admin_consent ? 1 : 0
  service_principal_object_id          = azuread_service_principal.nerdio.object_id
  resource_service_principal_object_id = data.azuread_service_principal.msgraph.object_id
  claim_values                         = local.graph_delegated
}

resource "azuread_service_principal_delegated_permission_grant" "azure_service_management" {
  count                                = var.grant_admin_consent ? 1 : 0
  service_principal_object_id          = azuread_service_principal.nerdio.object_id
  resource_service_principal_object_id = data.azuread_service_principal.azure_service_management.object_id
  claim_values                         = ["user_impersonation"]
}

resource "azuread_app_role_assignment" "graph" {
  for_each            = var.grant_admin_consent ? toset(local.graph_application) : toset([])
  app_role_id         = data.azuread_service_principal.msgraph.app_role_ids[each.value]
  principal_object_id = azuread_service_principal.nerdio.object_id
  resource_object_id  = data.azuread_service_principal.msgraph.object_id
}
