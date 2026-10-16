# Offline plan tests with mocked providers: terraform init -backend=false && terraform test

mock_provider "azurerm" {
  mock_data "azurerm_client_config" {
    defaults = {
      tenant_id = "00000000-0000-0000-0000-000000000000"
      object_id = "11111111-1111-1111-1111-111111111111"
    }
  }
}

mock_provider "time" {}

variables {
  key_vault_name      = "kv-example-nme"
  location            = "eastus2"
  resource_group_name = "rg-example"
  secret_value        = "not-a-real-secret"
  secret_version      = 20261016000000
}

run "deployer_reads_by_default" {
  command = plan

  assert {
    condition     = keys(azurerm_role_assignment.secret_reader) == ["deployer"]
    error_message = "Only the deployer should read the secret by default."
  }
  assert {
    condition     = length(azurerm_user_assigned_identity.github) == 0
    error_message = "No GitHub identity without github_oidc."
  }
  assert {
    condition     = azurerm_key_vault.this.rbac_authorization_enabled
    error_message = "The vault must use RBAC."
  }
}

run "github_oidc_and_extra_readers" {
  command = plan

  variables {
    reader_object_ids = ["11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"]
    github_oidc       = { repository = "example/nerdio-hcl" }
  }

  assert {
    condition     = length(azurerm_role_assignment.secret_reader) == 3
    error_message = "Expected the deployer (deduplicated), one extra reader and the GitHub identity."
  }
  assert {
    condition     = azurerm_federated_identity_credential.github[0].subject == "repo:example/nerdio-hcl:environment:sandbox"
    error_message = "The federated credential should trust the sandbox environment of the repo."
  }
}

run "rejects_bad_repository" {
  command = plan

  variables {
    github_oidc = { repository = "not a repo" }
  }

  expect_failures = [var.github_oidc]
}
