resource "azurerm_log_analytics_workspace" "this" {
  name                = "log-${var.name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

resource "azurerm_user_assigned_identity" "app" {
  name                = "id-${var.name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

# --- Claude on Microsoft Foundry ---------------------------------------------------------

resource "random_string" "foundry" {
  length  = 6
  special = false
  upper   = false
}

resource "azurerm_cognitive_account" "foundry" {
  name                  = "ais-${var.name}-${random_string.foundry.result}"
  location              = var.foundry.location
  resource_group_name   = var.resource_group_name
  kind                  = "AIServices"
  sku_name              = "S0"
  custom_subdomain_name = "ais-${var.name}-${random_string.foundry.result}"
  # Entra only: the app calls the model with its managed identity, so no keys exist to leak.
  local_auth_enabled = false
  tags               = var.tags
}

resource "azurerm_cognitive_deployment" "claude" {
  count                = var.foundry.create_deployment ? 1 : 0
  name                 = var.foundry.deployment_name
  cognitive_account_id = azurerm_cognitive_account.foundry.id

  model {
    format  = "Anthropic"
    name    = var.foundry.model_name
    version = var.foundry.model_version
  }

  sku {
    name     = var.foundry.sku_name
    capacity = var.foundry.capacity
  }
}

resource "azurerm_role_assignment" "app_uses_model" {
  scope                = azurerm_cognitive_account.foundry.id
  role_definition_name = "Cognitive Services User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
  principal_type       = "ServicePrincipal"
}

# --- The app ---------------------------------------------------------------------------

resource "azurerm_container_app_environment" "this" {
  name                       = "cae-${var.name}"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id
  tags                       = var.tags
}

resource "azurerm_container_app" "this" {
  name                         = "ca-${var.name}"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "auto"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 0
    max_replicas = var.max_replicas

    container {
      name   = "assistant"
      image  = var.image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.app.client_id
      }
      env {
        name  = "NERDIO_FOUNDRY_RESOURCE"
        value = azurerm_cognitive_account.foundry.custom_subdomain_name
      }
      env {
        name  = "NERDIO_MODEL"
        value = var.foundry.deployment_name
      }
      env {
        name  = "NERDIO_EFFORT"
        value = var.effort
      }
      env {
        name  = "NERDIO_KIT_REPO"
        value = var.kit_repo_url
      }

      liveness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/healthz"
      }
    }
  }

  depends_on = [azurerm_role_assignment.app_uses_model]
}

# --- Sign-in: Entra ID, admin group only -------------------------------------------------

locals {
  app_url = "https://${azurerm_container_app.this.ingress[0].fqdn}"
}

resource "azuread_application" "signin" {
  display_name     = "${var.name} sign-in"
  sign_in_audience = "AzureADMyOrg"

  web {
    homepage_url  = local.app_url
    redirect_uris = ["${local.app_url}/.auth/login/aad/callback"]
    # ID tokens only: the app needs to know who signed in, not to call APIs as them, so no client
    # secret is created.
    implicit_grant {
      id_token_issuance_enabled = true
    }
  }

  required_resource_access {
    resource_app_id = "00000003-0000-0000-c000-000000000000" # Microsoft Graph
    resource_access {
      id   = "e1fe6dd8-ba31-4d61-89e7-88639da4683d" # User.Read (delegated)
      type = "Scope"
    }
  }
}

resource "azuread_service_principal" "signin" {
  client_id = azuread_application.signin.client_id
  # Only users assigned to the app (through the admin group) can get a token for it.
  app_role_assignment_required = true
}

resource "azuread_app_role_assignment" "admins" {
  app_role_id         = "00000000-0000-0000-0000-000000000000" # default access
  principal_object_id = var.admin_group_object_id
  resource_object_id  = azuread_service_principal.signin.object_id
}

resource "azapi_resource" "auth" {
  type      = "Microsoft.App/containerApps/authConfigs@2024-03-01"
  name      = "current"
  parent_id = azurerm_container_app.this.id

  body = {
    properties = {
      platform = { enabled = true }
      globalValidation = {
        unauthenticatedClientAction = "RedirectToLoginPage"
        redirectToProvider          = "azureactivedirectory"
        excludedPaths               = ["/healthz"]
      }
      identityProviders = {
        azureActiveDirectory = {
          enabled = true
          registration = {
            clientId     = azuread_application.signin.client_id
            openIdIssuer = "https://login.microsoftonline.com/${var.tenant_id}/v2.0"
          }
          validation = {
            allowedAudiences = [azuread_application.signin.client_id]
          }
        }
      }
      login = {
        tokenStore = { enabled = false }
      }
    }
  }
}
