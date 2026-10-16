# Offline plan tests with mocked providers: terraform init -backend=false && terraform test

mock_provider "azurerm" {
  mock_data "azurerm_client_config" {
    defaults = {
      tenant_id = "00000000-0000-0000-0000-000000000000"
      object_id = "11111111-1111-1111-1111-111111111111"
    }
  }
}

mock_provider "azuread" {
  mock_data "azuread_client_config" {
    defaults = {
      object_id = "11111111-1111-1111-1111-111111111111"
    }
  }
  mock_data "azuread_application_published_app_ids" {
    defaults = {
      result = { MicrosoftGraph = "00000003-0000-0000-c000-000000000000" }
    }
  }
  mock_data "azuread_service_principal" {
    defaults = {
      object_id    = "33333333-3333-3333-3333-333333333333"
      app_role_ids = { "Application.ReadWrite.OwnedBy" = "44444444-4444-4444-4444-444444444444" }
    }
  }
}

# The login app's client ID is the only unknown input to the rendered OpenBao config.
override_resource {
  target          = azuread_application.login
  override_during = plan
  values = {
    client_id = "55555555-5555-5555-5555-555555555555"
    id        = "/applications/66666666-6666-6666-6666-666666666666"
  }
}

mock_provider "random" {}
mock_provider "time" {}
mock_provider "tls" {}

variables {
  name                              = "example-nme-bao"
  key_vault_name                    = "kv-example-bao"
  location                          = "eastus2"
  resource_group_name               = "rg-example"
  subscription_id                   = "00000000-0000-0000-0000-000000000001"
  virtual_network                   = { name = "vnet-example", resource_group_name = "rg-example-network" }
  subnet_cidr                       = "10.50.4.64/28"
  allowed_source_addresses          = ["Internet"]
  rest_client_application_object_id = "22222222-2222-2222-2222-222222222222"
  identity = {
    id           = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-example/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-example-nme-bao"
    principal_id = "77777777-7777-7777-7777-777777777777"
    client_id    = "88888888-8888-8888-8888-888888888888"
  }
}

run "least_privilege_and_no_ssh" {
  command = plan

  assert {
    condition     = keys(azurerm_network_security_rule.https) == ["Internet"] && azurerm_network_security_rule.https["Internet"].destination_port_range == "8200"
    error_message = "Only port 8200 should be opened, once per allowed source."
  }
  assert {
    condition     = azurerm_role_assignment.unseal.role_definition_name == "Key Vault Crypto Service Encryption User"
    error_message = "The VM identity should only wrap and unwrap with the unseal key."
  }
  assert {
    condition     = azuread_app_role_assignment.graph_owned_by.app_role_id == "44444444-4444-4444-4444-444444444444"
    error_message = "OpenBao should get Application.ReadWrite.OwnedBy, not Application.ReadWrite.All."
  }
  assert {
    condition     = azurerm_linux_virtual_machine.this.identity[0].type == "UserAssigned"
    error_message = "Exactly one user-assigned identity, so IMDS picks it without a client ID."
  }
}

run "config_has_no_github_auth_by_default" {
  command = plan

  assert {
    condition     = !strcontains(local.openbao_hcl, "auth/github") && strcontains(local.openbao_hcl, "auth/entra/role/nerdio-rest")
    error_message = "GitHub login should only be configured when github_oidc is set."
  }
  assert {
    condition     = strcontains(local.openbao_hcl, "application_object_id = \"22222222-2222-2222-2222-222222222222\"")
    error_message = "The Azure secrets role should target the REST API client app."
  }
}

run "github_auth_when_asked" {
  command = plan

  variables {
    github_oidc = { repository = "example/nerdio-hcl" }
  }

  assert {
    condition     = strcontains(local.openbao_hcl, "repository  = \"example/nerdio-hcl\"")
    error_message = "GitHub login should be bound to the repository."
  }
}

run "plugin_must_be_pinned" {
  command = plan

  variables {
    azure_plugin_image = "ghcr.io/openbao/openbao-plugin-secrets-azure:v0.23.0"
  }

  expect_failures = [var.azure_plugin_image]
}
