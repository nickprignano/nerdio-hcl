# The deploy pipeline's footprint in Azure and GitHub (decision 0016).
#
# Terraform state lives in a storage account that only Entra identities can reach (no keys).
# Two user-assigned identities sign in from GitHub Actions with OIDC, so no Azure secret exists
# anywhere:
#   plan  - read-only on the subscription; any run from the deploy branch can use it.
#   apply - can change the subscription and Entra; GitHub only issues its token to a run a
#           named reviewer has approved, from the deploy branch.
# Whoever drives the pipeline (a person at the Actions tab, or later the setup chatbot) can
# start a plan, but only a reviewer's approval in GitHub turns it into an apply.

data "azurerm_client_config" "current" {}

locals {
  subscription_scope = "/subscriptions/${var.subscription_id}"
  repository         = "${var.github.owner}/${var.github.repository}"
  compact            = replace(var.name, "-", "")
  storage_name       = "st${local.compact}tf${substr(sha1(var.subscription_id), 0, 6)}"

  environments = {
    plan  = "${var.environment}-plan"
    apply = "${var.environment}-apply"
  }

  identities = {
    plan  = azurerm_user_assigned_identity.this["plan"]
    apply = azurerm_user_assigned_identity.this["apply"]
  }

  # IDs and names the workflow needs. None is a credential, but they're stored as environment
  # secrets so GitHub masks them: a public repository's Actions logs are public.
  shared_values = {
    AZURE_TENANT_ID           = var.tenant_id
    AZURE_SUBSCRIPTION_ID     = var.subscription_id
    TFSTATE_RESOURCE_GROUP    = azurerm_resource_group.this.name
    TFSTATE_STORAGE_ACCOUNT   = azurerm_storage_account.state.name
    NERDIO_PLAN_PRINCIPAL_ID  = local.identities.plan.principal_id
    NERDIO_APPLY_PRINCIPAL_ID = local.identities.apply.principal_id
  }

  github_secrets = merge(
    { for k, v in local.shared_values : "plan/${k}" => { env = "plan", name = k, value = v } },
    { for k, v in local.shared_values : "apply/${k}" => { env = "apply", name = k, value = v } },
    { for env in keys(local.environments) : "${env}/AZURE_CLIENT_ID" => { env = env, name = "AZURE_CLIENT_ID", value = local.identities[env].client_id } },
    var.answers_json == null ? {} : { "plan/NERDIO_ANSWERS" = { env = "plan", name = "NERDIO_ANSWERS", value = var.answers_json } },
  )

  graph_roles = merge(
    { for r in var.plan_graph_roles : "plan/${r}" => { env = "plan", role = r } },
    { for r in var.apply_graph_roles : "apply/${r}" => { env = "apply", role = r } },
  )
}

resource "azurerm_resource_group" "this" {
  name     = "rg-${var.name}-pipeline"
  location = var.location
  tags     = var.tags
}

# ---------------------------------------------------------------------------------------------
# Terraform state and saved plans

resource "azurerm_storage_account" "state" {
  name                            = local.storage_name
  resource_group_name             = azurerm_resource_group.this.name
  location                        = azurerm_resource_group.this.location
  account_tier                    = "Standard"
  account_replication_type        = "ZRS"
  min_tls_version                 = "TLS1_2"
  shared_access_key_enabled       = false
  default_to_oauth_authentication = true
  allow_nested_items_to_be_public = false
  tags                            = var.tags

  blob_properties {
    versioning_enabled = true
    delete_retention_policy {
      days = 30
    }
    container_delete_retention_policy {
      days = 30
    }
  }
}

resource "azurerm_storage_container" "this" {
  for_each              = toset(["tfstate", "plans"])
  name                  = each.key
  storage_account_id    = azurerm_storage_account.state.id
  container_access_type = "private"
}

resource "azurerm_storage_management_policy" "plans" {
  storage_account_id = azurerm_storage_account.state.id

  rule {
    name    = "expire-saved-plans"
    enabled = true
    filters {
      blob_types   = ["blockBlob"]
      prefix_match = ["plans/"]
    }
    actions {
      base_blob {
        delete_after_days_since_creation_greater_than = var.plan_retention_days
      }
      version {
        delete_after_days_since_creation = var.plan_retention_days
      }
    }
  }
}

# You keep data access too, so you can move state in from Cloud Shell and inspect it.
resource "azurerm_role_assignment" "state_data" {
  for_each = {
    deployer = data.azurerm_client_config.current.object_id
    plan     = local.identities.plan.principal_id
    apply    = local.identities.apply.principal_id
  }
  scope                = azurerm_storage_account.state.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = each.value
}

# ---------------------------------------------------------------------------------------------
# Identities GitHub Actions signs in as

resource "azurerm_user_assigned_identity" "this" {
  for_each            = local.environments
  name                = "id-${var.name}-${each.key}"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = var.tags
}

# Each identity trusts exactly one GitHub environment, so the token GitHub issues to the plan
# environment can never act as the apply identity.
resource "azurerm_federated_identity_credential" "this" {
  for_each                  = local.environments
  name                      = "github-${each.value}"
  user_assigned_identity_id = azurerm_user_assigned_identity.this[each.key].id
  issuer                    = "https://token.actions.githubusercontent.com"
  subject                   = "repo:${local.repository}:environment:${each.value}"
  audience                  = ["api://AzureADTokenExchange"]
}

resource "azurerm_role_assignment" "plan" {
  scope                = local.subscription_scope
  role_definition_name = "Reader"
  principal_id         = local.identities.plan.principal_id
}

resource "azurerm_role_assignment" "apply" {
  for_each             = toset(var.apply_roles)
  scope                = local.subscription_scope
  role_definition_name = each.key
  principal_id         = local.identities.apply.principal_id
}

data "azuread_service_principal" "msgraph" {
  client_id = "00000003-0000-0000-c000-000000000000" # Microsoft Graph, the same in every tenant
}

resource "azuread_app_role_assignment" "graph" {
  for_each            = local.graph_roles
  app_role_id         = data.azuread_service_principal.msgraph.app_role_ids[each.value.role]
  principal_object_id = local.identities[each.value.env].principal_id
  resource_object_id  = data.azuread_service_principal.msgraph.object_id
}

# ---------------------------------------------------------------------------------------------
# GitHub environments: the approval gate

data "github_user" "reviewer" {
  for_each = toset(var.github.reviewers)
  username = each.key
}

resource "github_repository_environment" "plan" {
  repository  = var.github.repository
  environment = local.environments.plan

  deployment_branch_policy {
    protected_branches     = false
    custom_branch_policies = true
  }
}

resource "github_repository_environment" "apply" {
  repository          = var.github.repository
  environment         = local.environments.apply
  prevent_self_review = false # a single maintainer must be able to approve their own run
  can_admins_bypass   = false

  reviewers {
    users = [for u in data.github_user.reviewer : tonumber(u.id)]
  }

  deployment_branch_policy {
    protected_branches     = false
    custom_branch_policies = true
  }
}

resource "github_repository_environment_deployment_policy" "this" {
  for_each = {
    plan  = github_repository_environment.plan.environment
    apply = github_repository_environment.apply.environment
  }
  repository     = var.github.repository
  environment    = each.value
  branch_pattern = var.github.branch
}

resource "github_actions_environment_secret" "this" {
  for_each        = local.github_secrets
  repository      = var.github.repository
  environment     = each.value.env == "plan" ? github_repository_environment.plan.environment : github_repository_environment.apply.environment
  secret_name     = each.value.name
  plaintext_value = each.value.value
}
