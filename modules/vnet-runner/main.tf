# Ephemeral self-hosted GitHub Actions runner inside the AVD VNet using Azure Container Apps Jobs.
# Scales 0 -> N on queued workflow runs and terminates after a single job (--ephemeral), so
# hardened deployments (enable_hardening = true) can reach private Key Vault, SQL, and Nerdio REST API.

resource "azurerm_user_assigned_identity" "runner" {
  name                = "id-${var.name_prefix}-vnet-runner"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_role_assignment" "kv_secret_user" {
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.runner.principal_id
}

resource "azurerm_container_app_environment" "this" {
  name                           = "cae-${var.name_prefix}-runner"
  location                       = var.location
  resource_group_name            = var.resource_group_name
  log_analytics_workspace_id     = var.log_analytics_workspace_id
  infrastructure_subnet_id       = var.infrastructure_subnet_id
  internal_load_balancer_enabled = true
  tags                           = var.tags
}

resource "azurerm_container_app_job" "runner" {
  name                         = "caj-${var.name_prefix}-gh-runner"
  location                     = var.location
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.this.id
  replica_timeout_in_seconds   = 3600
  replica_retry_limit          = 0
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.runner.id]
  }

  secret {
    name                = "github-token"
    identity            = azurerm_user_assigned_identity.runner.id
    key_vault_secret_id = var.github_pat_key_vault_secret_id
  }

  event_trigger_config {
    parallelism              = 1
    replica_completion_count = 1

    scale {
      min_executions              = 0
      max_executions              = var.max_executions
      polling_interval_in_seconds = 30

      rules {
        name             = "github-runner"
        custom_rule_type = "github-runner"
        metadata = {
          githubAPIURL              = "https://api.github.com"
          runnerScope               = "repo"
          targetWorkflowQueueLength = "1"
          labels                    = join(",", var.runner_labels)
        }
        authentication {
          secret_name       = "github-token"
          trigger_parameter = "personalAccessToken"
        }
      }
    }
  }

  template {
    container {
      name   = "gh-runner"
      image  = var.runner_image
      cpu    = 2.0
      memory = "4Gi"

      env {
        name  = "REPO_URL"
        value = var.github_repo_url
      }
      env {
        name  = "RUNNER_SCOPE"
        value = "repo"
      }
      env {
        name  = "EPHEMERAL"
        value = "1"
      }
      env {
        name  = "LABELS"
        value = join(",", var.runner_labels)
      }
      env {
        name        = "ACCESS_token"
        secret_name = "github-token"
      }
    }
  }

  depends_on = [azurerm_role_assignment.kv_secret_user]
}
