# Ephemeral self-hosted GitHub Actions runner inside the AVD VNet using Azure Container Apps Jobs.
# Scales 0 -> N on queued workflow runs and terminates after a single job (--ephemeral), so
# hardened deployments (enable_hardening = true) can reach private Key Vault, SQL, and Nerdio REST API.
# Uses a Consumption Workload Profile so the Container Apps Environment requires only a /27 subnet.

locals {
  use_github_app     = var.github_app != null
  kv_secret_id       = local.use_github_app ? var.github_app.private_key_key_vault_secret_id : var.github_pat_key_vault_secret_id
  auth_trigger_param = local.use_github_app ? "appKey" : "personalAccessToken"
  rule_metadata = merge(
    {
      githubAPIURL              = "https://api.github.com"
      runnerScope               = "repo"
      targetWorkflowQueueLength = "1"
      labels                    = join(",", var.runner_labels)
    },
    local.use_github_app ? {
      applicationID  = var.github_app.application_id
      installationID = var.github_app.installation_id
    } : {}
  )
}

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

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }
}

resource "azurerm_container_app_job" "runner" {
  name                         = "caj-${var.name_prefix}-gh-runner"
  location                     = var.location
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.this.id
  workload_profile_name        = "Consumption"
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
    key_vault_secret_id = local.kv_secret_id
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
        metadata         = local.rule_metadata
        authentication {
          secret_name       = "github-token"
          trigger_parameter = local.auth_trigger_param
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
      dynamic "env" {
        for_each = local.use_github_app ? [1] : []
        content {
          name  = "APP_ID"
          value = var.github_app.application_id
        }
      }
      dynamic "env" {
        for_each = local.use_github_app ? [1] : []
        content {
          name  = "APP_INSTALLATION_ID"
          value = var.github_app.installation_id
        }
      }
      dynamic "env" {
        for_each = local.use_github_app ? [1] : []
        content {
          name        = "APP_PRIVATE_KEY"
          secret_name = "github-token"
        }
      }
      dynamic "env" {
        for_each = local.use_github_app ? [] : [1]
        content {
          name        = "ACCESS_TOKEN"
          secret_name = "github-token"
        }
      }
    }
  }

  depends_on = [azurerm_role_assignment.kv_secret_user]
}
