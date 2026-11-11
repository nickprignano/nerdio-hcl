# --- Azure OpenAI in this tenant (decision 0036) --------------------------------------------
#
# Claude isn't offered inside Azure Government, and a Government deployment keeps everything in the
# Government tenant. So with cloud = "usgovernment" the chat defaults to an Azure OpenAI account and
# model deployment in a Government region (usgovvirginia or usgovarizona), in the chat's own resource
# group. Keyless, like the other paths: key access is off and the app's managed identity holds only
# Cognitive Services OpenAI User on this one account. Commercial deployments keep the Claude API.

locals {
  use_azure_openai = local.model_provider == "azure-openai"
  aoai             = var.azure_openai
  # Entra scope for Cognitive Services in each cloud.
  aoai_token_scope = {
    public       = "https://cognitiveservices.azure.com/.default"
    usgovernment = "https://cognitiveservices.azure.us/.default"
  }[var.cloud]
  aoai_location = coalesce(local.aoai.location, var.location)
  azure_openai_env = local.use_azure_openai ? {
    for k, v in {
      NERDIO_AOAI_ENDPOINT         = azurerm_cognitive_account.openai[0].endpoint
      NERDIO_AOAI_TOKEN_SCOPE      = local.aoai_token_scope
      NERDIO_AOAI_API_VERSION      = local.aoai.api_version
      NERDIO_AOAI_REASONING_EFFORT = local.aoai.reasoning_effort
      NERDIO_MODEL                 = local.aoai.deployment_name
    } : k => v if v != null
  } : {}
}

resource "azurerm_cognitive_account" "openai" {
  count                 = local.use_azure_openai ? 1 : 0
  name                  = "oai-${var.name}-${random_string.foundry.result}"
  location              = local.aoai_location
  resource_group_name   = var.resource_group_name
  kind                  = "OpenAI"
  sku_name              = "S0"
  custom_subdomain_name = "oai-${var.name}-${random_string.foundry.result}"
  # Entra only: no keys exist to leak, and the chat can't be pointed at one.
  local_auth_enabled = false
  tags               = var.tags
}

resource "azurerm_cognitive_deployment" "openai" {
  count                = local.use_azure_openai && local.aoai.create_deployment ? 1 : 0
  name                 = local.aoai.deployment_name
  cognitive_account_id = azurerm_cognitive_account.openai[0].id

  model {
    format  = "OpenAI"
    name    = local.aoai.model_name
    version = local.aoai.model_version
  }

  sku {
    # "Standard" keeps processing in the account's region. "DataZoneStandard" in Government routes
    # within Azure Government's US data zone.
    name     = local.aoai.sku_name
    capacity = local.aoai.capacity
  }
}

resource "azurerm_role_assignment" "app_uses_openai" {
  count                = local.use_azure_openai ? 1 : 0
  scope                = azurerm_cognitive_account.openai[0].id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
  principal_type       = "ServicePrincipal"
}
