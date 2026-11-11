# Offline plan tests with mocked providers: terraform init -backend=false && terraform test

mock_provider "azurerm" {
  mock_resource "azurerm_log_analytics_workspace" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-nme-assistant/providers/Microsoft.OperationalInsights/workspaces/log-nme-assistant"
    }
  }
  mock_resource "azurerm_user_assigned_identity" {
    defaults = {
      id           = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-nme-assistant/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-nme-assistant"
      principal_id = "66666666-6666-6666-6666-666666666666"
      client_id    = "77777777-7777-7777-7777-777777777777"
    }
  }
  mock_resource "azurerm_container_app_environment" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-nme-assistant/providers/Microsoft.App/managedEnvironments/cae-nme-assistant"
    }
  }
  mock_resource "azurerm_cognitive_account" {
    defaults = {
      id       = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-nme-assistant/providers/Microsoft.CognitiveServices/accounts/oai-nme-assistant-abc123"
      endpoint = "https://oai-nme-assistant-abc123.openai.azure.us/"
    }
  }
  mock_resource "azurerm_container_app" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-nme-assistant/providers/Microsoft.App/containerApps/ca-nme-assistant"
    }
  }
}
mock_provider "azuread" {
  mock_resource "azuread_application" {
    defaults = {
      id        = "/applications/88888888-8888-8888-8888-888888888888"
      client_id = "44444444-4444-4444-4444-444444444444"
    }
  }
  mock_resource "azuread_service_principal" {
    defaults = {
      object_id = "99999999-9999-9999-9999-999999999999"
    }
  }
}
mock_provider "random" {}
mock_provider "azapi" {}

variables {
  name                  = "nme-assistant"
  location              = "eastus2"
  resource_group_name   = "rg-nme-assistant"
  tenant_id             = "00000000-0000-0000-0000-000000000000"
  image                 = "ghcr.io/example/assistant:main"
  admin_group_object_id = "11111111-1111-1111-1111-111111111111"
}

run "claude_api_by_default" {
  command = plan

  assert {
    condition     = length(azurerm_cognitive_account.foundry) == 0 && length(azuread_application.claude_audience) == 1
    error_message = "The Claude API should be the default, with no Foundry resource."
  }
}

run "foundry_when_chosen" {
  command = plan

  variables {
    model_provider = "foundry"
    foundry        = { location = "eastus2" }
  }

  assert {
    condition     = length(azurerm_cognitive_account.foundry) == 1 && length(azuread_application.claude_audience) == 0
    error_message = "Foundry should create its resource and no Claude API audience app."
  }

  assert {
    condition     = output.claude_federation == null
    error_message = "claude_federation is only for the Claude API."
  }
}

run "claude_api_creates_no_foundry_and_no_secret" {
  command = apply

  variables {
    model_provider = "claude-api"
  }

  assert {
    condition     = length(azurerm_cognitive_account.foundry) == 0 && length(azurerm_role_assignment.app_uses_model) == 0
    error_message = "The Claude API path must not create Foundry or its role assignment."
  }

  assert {
    condition     = azuread_application_identifier_uri.claude_audience[0].identifier_uri == "api://44444444-4444-4444-4444-444444444444"
    error_message = "The audience app's identifier URI must be api://<its client ID>."
  }

  assert {
    condition     = azuread_application.claude_audience[0].api[0].requested_access_token_version == 2
    error_message = "The audience app must issue v2.0 tokens (issuer login.microsoftonline.com/<tenant>/v2.0)."
  }

  assert {
    condition     = output.claude_federation.issuer_url == "https://login.microsoftonline.com/00000000-0000-0000-0000-000000000000/v2.0" && !output.claude_federation.connected
    error_message = "claude_federation should name the tenant's v2.0 issuer and say it isn't connected yet."
  }

  assert {
    condition = !anytrue([for e in azurerm_container_app.this.template[0].container[0].env :
    contains(["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_FEDERATION_RULE_ID"], e.name)])
    error_message = "No API key or token may reach the app, and unset federation IDs must stay out of its environment."
  }
}

run "claude_api_ids_reach_the_app" {
  command = apply

  variables {
    model_provider = "claude-api"
    claude_api = {
      organization_id    = "55555555-5555-5555-5555-555555555555"
      federation_rule_id = "fdrl_test"
      service_account_id = "svac_test"
    }
  }

  assert {
    condition = contains([for e in azurerm_container_app.this.template[0].container[0].env : "${e.name}=${e.value}"],
    "ANTHROPIC_FEDERATION_RULE_ID=fdrl_test")
    error_message = "The federation rule ID should reach the app."
  }

  assert {
    condition     = output.claude_federation.connected
    error_message = "claude_federation.connected should be true once the IDs are set."
  }
}

run "bad_ids_are_rejected" {
  command = plan

  variables {
    model_provider = "claude-api"
    claude_api     = { federation_rule_id = "sk-ant-api03-not-a-rule" }
  }

  expect_failures = [var.claude_api]
}

run "foundry_needs_its_settings" {
  command = plan

  variables {
    model_provider = "foundry"
  }

  expect_failures = [var.foundry]
}

# Decision 0034 moves sign-in to login.microsoftonline.us in Azure Government; decision 0036 keeps
# the chat's model in the Government tenant: Azure OpenAI in a Government region, keyless.
run "usgovernment_uses_azure_openai_in_the_tenant" {
  command = apply

  variables {
    cloud    = "usgovernment"
    location = "usgovvirginia"
  }

  assert {
    condition     = output.model_provider == "azure-openai"
    error_message = "Azure Government should default to Azure OpenAI."
  }

  assert {
    condition     = length(azuread_application.claude_audience) == 0 && length(azurerm_cognitive_account.foundry) == 0 && output.claude_federation == null
    error_message = "No Claude path (audience app, Foundry) may be created in Azure Government."
  }

  assert {
    condition = (azurerm_cognitive_account.openai[0].kind == "OpenAI" && !azurerm_cognitive_account.openai[0].local_auth_enabled
    && azurerm_cognitive_account.openai[0].location == "usgovvirginia")
    error_message = "The Azure OpenAI account must be in the Government region with key access off."
  }

  assert {
    condition = (azurerm_cognitive_deployment.openai[0].model[0].format == "OpenAI" && azurerm_cognitive_deployment.openai[0].model[0].name == "gpt-4.1"
    && azurerm_cognitive_deployment.openai[0].sku[0].name == "Standard")
    error_message = "The default deployment is gpt-4.1 on a regional Standard SKU."
  }

  assert {
    condition     = azurerm_role_assignment.app_uses_openai[0].role_definition_name == "Cognitive Services OpenAI User" && azurerm_role_assignment.app_uses_openai[0].principal_id == "66666666-6666-6666-6666-666666666666"
    error_message = "The app's identity gets only Cognitive Services OpenAI User on the account."
  }

  assert {
    condition = alltrue([for want in [
      "NERDIO_MODEL_PROVIDER=azure-openai",
      "NERDIO_CLOUD=usgovernment",
      "AZURE_AUTHORITY_HOST=https://login.microsoftonline.us",
      "NERDIO_AOAI_ENDPOINT=https://oai-nme-assistant-abc123.openai.azure.us/",
      "NERDIO_AOAI_TOKEN_SCOPE=https://cognitiveservices.azure.us/.default",
      "NERDIO_MODEL=chat",
    ] : contains([for e in azurerm_container_app.this.template[0].container[0].env : "${e.name}=${e.value}"], want)])
    error_message = "The app must get the Government endpoint, token scope, authority and deployment name."
  }

  assert {
    condition = !anytrue([for e in azurerm_container_app.this.template[0].container[0].env :
    startswith(e.name, "ANTHROPIC_") || e.name == "AZURE_OPENAI_API_KEY" || e.name == "NERDIO_AOAI_REASONING_EFFORT"])
    error_message = "No key, no Claude settings, and no reasoning effort for a non-reasoning model."
  }

  assert {
    condition     = azapi_resource.auth.body.properties.identityProviders.azureActiveDirectory.registration.openIdIssuer == "https://login.microsoftonline.us/00000000-0000-0000-0000-000000000000/v2.0"
    error_message = "In Azure Government the sign-in issuer must be login.microsoftonline.us/<tenant>/v2.0."
  }
}

run "usgovernment_refuses_claude" {
  command = plan

  variables {
    cloud          = "usgovernment"
    location       = "usgovvirginia"
    model_provider = "claude-api"
  }

  expect_failures = [var.model_provider]
}

run "usgovernment_needs_a_government_region" {
  command = plan

  variables {
    cloud = "usgovernment"
  }

  expect_failures = [var.azure_openai]
}

run "usgovernment_refuses_global_deployments" {
  command = plan

  variables {
    cloud        = "usgovernment"
    location     = "usgovvirginia"
    azure_openai = { sku_name = "GlobalStandard" }
  }

  expect_failures = [var.azure_openai]
}

run "azure_openai_reasoning_model" {
  command = apply

  variables {
    cloud        = "usgovernment"
    location     = "usgovarizona"
    azure_openai = { model_name = "o3-mini", model_version = "2025-01-31", sku_name = "DataZoneStandard", reasoning_effort = "medium" }
  }

  assert {
    condition = contains([for e in azurerm_container_app.this.template[0].container[0].env : "${e.name}=${e.value}"],
    "NERDIO_AOAI_REASONING_EFFORT=medium")
    error_message = "A reasoning model's effort should reach the app."
  }
}

# Commercial behavior doesn't change: no Azure OpenAI unless asked for.
run "commercial_creates_no_azure_openai" {
  command = plan

  assert {
    condition     = length(azurerm_cognitive_account.openai) == 0 && length(azurerm_role_assignment.app_uses_openai) == 0 && output.model_provider == "claude-api"
    error_message = "Commercial Azure keeps the Claude API and creates no Azure OpenAI account."
  }
}
