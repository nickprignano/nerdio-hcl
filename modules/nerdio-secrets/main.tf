# Hands the Nerdio REST API client secret from stage 1 to stage 2 (decision 0015).
#
# Stage 1 writes the secret here with a write-only attribute, so this module's resources never
# hold its value. Stage 2 reads it with the ephemeral azurerm_key_vault_secret resource and
# passes it straight to the nme provider, so it never lands in tfvars, the shell, logs or stage
# 2's state. Readers sign in with az (Cloud Shell) or GitHub OIDC; nobody handles the value.
#
# The secret still exists in stage 1's state, because azuread_application_password returns it.
# Keep that state in a protected backend. Removing the secret altogether needs federated sign-in
# in Nerdio's provider (docs/knowledge/nerdio/upstream-contributions.md).

data "azurerm_client_config" "current" {}

locals {
  deployer = coalesce(var.deployer_object_id, data.azurerm_client_config.current.object_id)
  # Static keys, so for_each works before the GitHub identity exists.
  readers = merge(
    { deployer = local.deployer },
    { for id in distinct(var.reader_object_ids) : id => id if id != local.deployer },
    var.github_oidc == null ? {} : { github = azurerm_user_assigned_identity.github[0].principal_id },
  )
}

resource "azurerm_key_vault" "this" {
  name                          = var.key_vault_name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  sku_name                      = "standard"
  rbac_authorization_enabled    = true
  soft_delete_retention_days    = 7
  purge_protection_enabled      = var.purge_protection_enabled
  public_network_access_enabled = var.public_network_access_enabled
  tags                          = var.tags

  network_acls {
    bypass         = "None"
    default_action = var.public_network_access_enabled ? "Allow" : "Deny"
  }
}

# The deployer writes the secret. Data-plane roles take a minute or two to apply.
resource "azurerm_role_assignment" "deployer" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = local.deployer
}

resource "time_sleep" "rbac" {
  create_duration = "90s"
  depends_on      = [azurerm_role_assignment.deployer]
}

resource "azurerm_key_vault_secret" "rest_client" {
  name             = var.secret_name
  key_vault_id     = azurerm_key_vault.this.id
  value_wo         = var.secret_value
  value_wo_version = var.secret_version
  content_type     = "Nerdio REST API client secret"
  expiration_date  = var.secret_expiration_date
  tags             = var.tags
  depends_on       = [time_sleep.rbac]
}

# Readers get the one secret, not the vault. Reader on the vault lets the azurerm provider look
# up the vault's URI; it grants no access to secret values.
resource "azurerm_role_assignment" "secret_reader" {
  for_each             = local.readers
  scope                = azurerm_key_vault_secret.rest_client.resource_versionless_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = each.value
}

resource "azurerm_role_assignment" "vault_reader" {
  for_each             = local.readers
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Reader"
  principal_id         = each.value
}

# GitHub Actions signs in as this identity with OIDC, so the pipeline stores no Azure secret.
resource "azurerm_user_assigned_identity" "github" {
  count               = var.github_oidc == null ? 0 : 1
  name                = "id-${var.key_vault_name}-github"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_federated_identity_credential" "github" {
  count                     = var.github_oidc == null ? 0 : 1
  name                      = "github-${var.github_oidc.environment}"
  user_assigned_identity_id = azurerm_user_assigned_identity.github[0].id
  issuer                    = "https://token.actions.githubusercontent.com"
  subject                   = "repo:${var.github_oidc.repository}:environment:${var.github_oidc.environment}"
  audience                  = ["api://AzureADTokenExchange"]
}
