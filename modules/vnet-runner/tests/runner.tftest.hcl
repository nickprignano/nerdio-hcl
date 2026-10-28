mock_provider "azurerm" {}

variables {
  name_prefix                = "test"
  location                   = "eastus2"
  resource_group_name        = "rg-test-network"
  infrastructure_subnet_id   = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test-network/providers/Microsoft.Network/virtualNetworks/vnet-test/subnets/snet-vnet-runner"
  log_analytics_workspace_id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test-mon/providers/Microsoft.OperationalInsights/workspaces/log-test"
  github_repo_url            = "https://github.com/contoso/nerdio-hcl"
  key_vault_id               = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test-nerdio/providers/Microsoft.KeyVault/vaults/kv-test"
}

run "github_app_auth_and_consumption_profile" {
  command = plan

  variables {
    github_app = {
      application_id                  = "123456"
      installation_id                 = "789012"
      private_key_key_vault_secret_id = "https://kv-test.vault.azure.net/secrets/gh-app-key"
    }
  }

  assert {
    condition     = one(azurerm_container_app_environment.this.workload_profile).workload_profile_type == "Consumption" && azurerm_container_app_job.runner.workload_profile_name == "Consumption"
    error_message = "Expected Consumption workload profile on the Container Apps Environment and Job."
  }

  assert {
    condition     = one(azurerm_container_app_job.runner.event_trigger_config[0].scale[0].rules[0].authentication).trigger_parameter == "appKey"
    error_message = "Expected KEDA github-runner authentication to use appKey when github_app is configured."
  }
}

run "pat_auth_fallback" {
  command = plan

  variables {
    github_pat_key_vault_secret_id = "https://kv-test.vault.azure.net/secrets/gh-pat"
  }

  assert {
    condition     = one(azurerm_container_app_job.runner.event_trigger_config[0].scale[0].rules[0].authentication).trigger_parameter == "personalAccessToken"
    error_message = "Expected KEDA github-runner authentication to use personalAccessToken when github_pat_key_vault_secret_id is configured."
  }
}

run "requires_app_or_pat" {
  command = plan

  expect_failures = [var.github_pat_key_vault_secret_id]
}
