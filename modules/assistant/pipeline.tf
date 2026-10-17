# Optional link to the deploy pipeline (decision 0016). The app's identity gets exactly:
#   - write on the answers container (what the pipeline plans from; versioned)
#   - read on the plans container (the change summaries it explains)
#   - sign with one Key Vault key, the GitHub App's private key, which it can never read
# GitHub only lets the app start workflow runs; an apply still needs a person's approval.

data "azurerm_client_config" "current" {}

locals {
  pipeline_enabled = var.pipeline != null
  pipeline_storage = local.pipeline_enabled ? element(split("/", var.pipeline.storage_account_id), 8) : ""
  github_key_name  = "github-app"
  pipeline_env = local.pipeline_enabled ? {
    NERDIO_PIPELINE_STORAGE     = local.pipeline_storage
    NERDIO_PIPELINE_ENV         = var.pipeline.environment
    NERDIO_PIPELINE_BRANCH      = var.pipeline.github.branch
    NERDIO_GITHUB_REPO          = var.pipeline.github.repository
    NERDIO_GITHUB_APP_CLIENT_ID = var.pipeline.github.app_client_id
    NERDIO_GITHUB_KEY_URL       = "${azurerm_key_vault.github[0].vault_uri}keys/${local.github_key_name}"
  } : {}
}

resource "azurerm_key_vault" "github" {
  count                      = local.pipeline_enabled ? 1 : 0
  name                       = "kv${substr(replace(var.name, "-", ""), 0, 14)}${random_string.foundry.result}"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  tenant_id                  = var.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  soft_delete_retention_days = 7
  purge_protection_enabled   = true
  tags                       = var.tags
}

# You import the key once; the app only signs with it.
resource "azurerm_role_assignment" "deployer_imports_key" {
  count                = local.pipeline_enabled ? 1 : 0
  scope                = azurerm_key_vault.github[0].id
  role_definition_name = "Key Vault Crypto Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "app_signs" {
  count                = local.pipeline_enabled ? 1 : 0
  scope                = azurerm_key_vault.github[0].id
  role_definition_name = "Key Vault Crypto User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "app_writes_answers" {
  count                = local.pipeline_enabled ? 1 : 0
  scope                = "${var.pipeline.storage_account_id}/blobServices/default/containers/answers"
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "app_reads_plans" {
  count                = local.pipeline_enabled ? 1 : 0
  scope                = "${var.pipeline.storage_account_id}/blobServices/default/containers/plans"
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
  principal_type       = "ServicePrincipal"
}
