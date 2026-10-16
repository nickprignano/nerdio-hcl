resource "azurerm_key_vault" "this" {
  name                          = local.names.key_vault
  location                      = var.location
  resource_group_name           = var.resource_group_name
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  sku_name                      = "standard"
  rbac_authorization_enabled    = true
  soft_delete_retention_days    = 90
  purge_protection_enabled      = false
  public_network_access_enabled = var.public_network_access_enabled
  tags                          = local.paas_tags

  network_acls {
    bypass         = "AzureServices"
    default_action = var.public_network_access_enabled ? "Allow" : "Deny"
  }
}

locals {
  key_vault_roles = {
    deployer_crypto  = { principal = data.azurerm_client_config.current.object_id, role = "Key Vault Crypto Officer" }
    deployer_secrets = { principal = data.azurerm_client_config.current.object_id, role = "Key Vault Secrets Officer" }
    deployer_certs   = { principal = data.azurerm_client_config.current.object_id, role = "Key Vault Certificates Officer" }
    web_secrets      = { principal = azurerm_windows_web_app.this.identity[0].principal_id, role = "Key Vault Secrets Officer" }
    web_crypto       = { principal = azurerm_windows_web_app.this.identity[0].principal_id, role = "Key Vault Crypto User" }
    web_certs        = { principal = azurerm_windows_web_app.this.identity[0].principal_id, role = "Key Vault Certificate User" }
    app_secrets      = { principal = var.entra_app.service_principal_object_id, role = "Key Vault Secrets User" }
    app_certs        = { principal = var.entra_app.service_principal_object_id, role = "Key Vault Certificates Officer" }
  }
}

resource "azurerm_role_assignment" "key_vault" {
  for_each             = local.key_vault_roles
  scope                = azurerm_key_vault.this.id
  role_definition_name = each.value.role
  principal_id         = each.value.principal
}

# Data-plane role assignments take a minute or two to apply.
resource "time_sleep" "key_vault_rbac" {
  create_duration = "90s"
  depends_on      = [azurerm_role_assignment.key_vault]
}

# Wraps the ASP.NET data protection keys (DataProtection:Protect:KeyIdentifier).
resource "azurerm_key_vault_key" "data_protection" {
  name         = local.names.data_protection
  key_vault_id = azurerm_key_vault.this.id
  key_type     = "RSA"
  key_size     = 2048
  key_opts     = ["wrapKey", "unwrapKey"]
  depends_on   = [time_sleep.key_vault_rbac]
}

# The Nerdio app signs in to Entra with this certificate (AzureAD:ClientCertificates).
resource "azurerm_key_vault_certificate" "app" {
  name         = local.names.app_cert
  key_vault_id = azurerm_key_vault.this.id
  depends_on   = [time_sleep.key_vault_rbac]

  certificate_policy {
    issuer_parameters {
      name = "Self"
    }
    key_properties {
      exportable = true
      key_type   = "RSA"
      key_size   = 2048
      reuse_key  = true
    }
    secret_properties {
      content_type = "application/x-pkcs12"
    }
    x509_certificate_properties {
      subject            = "CN=${local.names.app_cert}"
      validity_in_months = var.certificate_validity_months
      key_usage          = ["digitalSignature", "keyEncipherment"]
    }
    lifetime_action {
      action {
        action_type = "AutoRenew"
      }
      trigger {
        days_before_expiry = 30
      }
    }
  }
}

# Scripted actions run in the scripted-actions Automation account as the Nerdio app, using this certificate.
resource "azurerm_key_vault_certificate" "scripted_actions" {
  name         = local.names.scripted_cert
  key_vault_id = azurerm_key_vault.this.id
  depends_on   = [time_sleep.key_vault_rbac]

  certificate_policy {
    issuer_parameters {
      name = "Self"
    }
    key_properties {
      exportable = true
      key_type   = "RSA"
      key_size   = 2048
      reuse_key  = false
    }
    secret_properties {
      content_type = "application/x-pkcs12"
    }
    x509_certificate_properties {
      subject            = "CN=${local.names.scripted_cert}"
      validity_in_months = var.certificate_validity_months
      key_usage          = ["digitalSignature", "keyEncipherment"]
    }
    lifetime_action {
      action {
        action_type = "AutoRenew"
      }
      trigger {
        days_before_expiry = 30
      }
    }
  }
}

resource "azuread_application_certificate" "app" {
  application_id = var.entra_app.application_id
  type           = "AsymmetricX509Cert"
  value          = azurerm_key_vault_certificate.app.certificate_data_base64
  end_date       = azurerm_key_vault_certificate.app.certificate_attribute[0].expires
}

resource "azuread_application_certificate" "scripted_actions" {
  application_id = var.entra_app.application_id
  type           = "AsymmetricX509Cert"
  value          = azurerm_key_vault_certificate.scripted_actions.certificate_data_base64
  end_date       = azurerm_key_vault_certificate.scripted_actions.certificate_attribute[0].expires
}
