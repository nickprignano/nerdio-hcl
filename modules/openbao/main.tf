# Optional OpenBao server that mints a short-lived Nerdio REST API secret per run (decision 0015).
#
# One small Linux VM, configured entirely from this module:
# - Auto-unseal with a Key Vault key and self-initialization from its config file, so nobody
#   handles an unseal key or a root token (OpenBao revokes the root token after setup).
# - The Azure secrets plugin, pulled from OpenBao's registry pinned by digest, adds passwords to
#   the existing REST API client app. Its managed identity owns that app and has Graph
#   Application.ReadWrite.OwnedBy, not tenant-wide Application.ReadWrite.All.
# - Login only with an Entra token (Cloud Shell) or a GitHub OIDC token; no passwords, no SSH.
#
# The VM is disposable: its state is the declarative config, so replacing it rebuilds the same
# server. Minted secrets expire on their own (credential_ttl).
#
# OpenBao is MPL-2.0. The kit downloads its release and plugin at boot and verifies both by
# digest; nothing is vendored here.

data "azurerm_client_config" "current" {}

data "azuread_client_config" "current" {}

data "azuread_application_published_app_ids" "well_known" {}

data "azuread_service_principal" "msgraph" {
  client_id = data.azuread_application_published_app_ids.well_known.result["MicrosoftGraph"]
}

locals {
  tenant_id = data.azurerm_client_config.current.tenant_id
  fqdn      = "${var.name}.${replace(lower(var.location), " ", "")}.cloudapp.azure.com"
  address   = "https://${local.fqdn}:8200"
  login_ids = distinct(concat([data.azuread_client_config.current.object_id], var.login_object_ids))

  names = {
    unseal_key  = "openbao-unseal"
    tls_cert    = "openbao-tls"
    login_app   = "${var.name}-login"
    subnet      = "snet-${var.name}"
    nsg         = "nsg-${var.name}"
    public_ip   = "pip-${var.name}"
    nic         = "nic-${var.name}"
    vm          = "vm-${var.name}"
    secret_role = "nerdio-rest"
  }

  # Azure CLI's well-known client ID. Pre-authorizing it lets `az account get-access-token`
  # get a token for the login app without a consent prompt.
  azure_cli_client_id = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
}

resource "azuread_app_role_assignment" "graph_owned_by" {
  app_role_id         = data.azuread_service_principal.msgraph.app_role_ids["Application.ReadWrite.OwnedBy"]
  principal_object_id = var.identity.principal_id
  resource_object_id  = data.azuread_service_principal.msgraph.object_id
}

# Cloud Shell users sign in to OpenBao with a token for this app, so OpenBao never sees a token
# that works anywhere else (an Azure management token could be replayed against Azure).
resource "random_uuid" "login_scope" {}

resource "azuread_application" "login" {
  display_name     = local.names.login_app
  sign_in_audience = "AzureADMyOrg"
  owners           = [data.azuread_client_config.current.object_id]

  api {
    requested_access_token_version = 2

    oauth2_permission_scope {
      id                         = random_uuid.login_scope.result
      value                      = "login"
      type                       = "User"
      enabled                    = true
      admin_consent_display_name = "Sign in to OpenBao"
      admin_consent_description  = "Lets the signed-in user get a token to log in to the kit's OpenBao server."
      user_consent_display_name  = "Sign in to OpenBao"
      user_consent_description   = "Lets you log in to the kit's OpenBao server."
    }
  }
}

resource "azuread_application_identifier_uri" "login" {
  application_id = azuread_application.login.id
  identifier_uri = "api://${azuread_application.login.client_id}"
}

resource "azuread_service_principal" "login" {
  client_id = azuread_application.login.client_id
  owners    = [data.azuread_client_config.current.object_id]
}

resource "azuread_application_pre_authorized" "azure_cli" {
  application_id       = azuread_application.login.id
  authorized_client_id = local.azure_cli_client_id
  permission_ids       = [random_uuid.login_scope.result]
}
