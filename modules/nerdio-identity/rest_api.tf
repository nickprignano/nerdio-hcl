# Optional client app for the Nerdio REST API (System > Settings > Integrations).
# Mirrors Nerdio's "REST API Manual Configuration" article.

resource "azuread_application" "rest_client" {
  count            = var.create_rest_api_client ? 1 : 0
  display_name     = "${var.display_name}-rest-client"
  sign_in_audience = "AzureADMyOrg"
  owners           = local.owners
  tags             = ["NMW_REST_API_CLIENT:${azuread_application.nerdio.client_id}"]

  required_resource_access {
    resource_app_id = azuread_application.nerdio.client_id
    resource_access {
      id   = local.app_roles.RestClient.id
      type = "Role"
    }
  }
}

resource "azuread_service_principal" "rest_client" {
  count     = var.create_rest_api_client ? 1 : 0
  client_id = azuread_application.rest_client[0].client_id
  owners    = local.owners
}

resource "azuread_application_password" "rest_client" {
  count          = var.create_rest_api_client ? 1 : 0
  application_id = azuread_application.rest_client[0].id
  display_name   = "terraform"
  end_date       = timeadd(time_rotating.secret.id, "${var.secret_rotation_days * 24 + 720}h")
  rotate_when_changed = {
    rotation = time_rotating.secret.id
  }
}

resource "azuread_app_role_assignment" "rest_client" {
  count               = var.create_rest_api_client && var.grant_admin_consent ? 1 : 0
  app_role_id         = local.app_roles.RestClient.id
  principal_object_id = azuread_service_principal.rest_client[0].object_id
  resource_object_id  = azuread_service_principal.nerdio.object_id
}
