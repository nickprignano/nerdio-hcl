# Where the Nerdio REST API client secret comes from (decision 0015). Ephemeral resources are
# read during plan and apply and never saved, so the secret stays out of this stage's state.

ephemeral "azurerm_key_vault_secret" "nme" {
  count        = var.nme_secret_source == "key_vault" ? 1 : 0
  name         = var.nme_key_vault.secret_name
  key_vault_id = var.nme_key_vault.id
}

# OpenBao adds a password to the REST client app for this run; it expires on its own.
ephemeral "vault_azure_access_credentials" "nme" {
  count   = var.nme_secret_source == "openbao" ? 1 : 0
  backend = "azure"
  role    = var.openbao.role
}

locals {
  nme_client_secret = one(concat(
    ephemeral.azurerm_key_vault_secret.nme[*].value,
    ephemeral.vault_azure_access_credentials.nme[*].client_secret,
  ))
}
