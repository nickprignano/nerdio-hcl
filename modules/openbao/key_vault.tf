resource "azurerm_key_vault" "this" {
  name                       = var.key_vault_name
  location                   = var.location
  resource_group_name        = var.resource_group_name
  tenant_id                  = local.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  soft_delete_retention_days = 7
  # The unseal key can't be recovered once purged, so purging is blocked.
  purge_protection_enabled = true
  tags                     = var.tags
}

resource "azurerm_role_assignment" "deployer" {
  for_each             = toset(["Key Vault Crypto Officer", "Key Vault Certificates Officer"])
  scope                = azurerm_key_vault.this.id
  role_definition_name = each.value
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "time_sleep" "rbac" {
  create_duration = "90s"
  depends_on      = [azurerm_role_assignment.deployer]
}

resource "azurerm_key_vault_key" "unseal" {
  name         = local.names.unseal_key
  key_vault_id = azurerm_key_vault.this.id
  key_type     = "RSA"
  key_size     = 2048
  key_opts     = ["wrapKey", "unwrapKey"]
  depends_on   = [time_sleep.rbac]
}

# Self-signed, generated inside Key Vault, so the private key never passes through Terraform.
# Clients trust this certificate itself (the openbao_ca_cert output).
resource "azurerm_key_vault_certificate" "tls" {
  name         = local.names.tls_cert
  key_vault_id = azurerm_key_vault.this.id
  depends_on   = [time_sleep.rbac]

  certificate_policy {
    issuer_parameters {
      name = "Self"
    }
    key_properties {
      exportable = true
      key_type   = "EC"
      curve      = "P-256"
      reuse_key  = false
    }
    secret_properties {
      content_type = "application/x-pem-file"
    }
    x509_certificate_properties {
      subject            = "CN=${local.fqdn}"
      validity_in_months = var.certificate_validity_months
      key_usage          = ["digitalSignature"]
      extended_key_usage = ["1.3.6.1.5.5.7.3.1"]
      subject_alternative_names {
        dns_names = [local.fqdn]
      }
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

# The VM's identity gets exactly two things: use of the unseal key, and read of its TLS secret.
resource "azurerm_role_assignment" "unseal" {
  scope                = azurerm_key_vault_key.unseal.resource_versionless_id
  role_definition_name = "Key Vault Crypto Service Encryption User"
  principal_id         = var.identity.principal_id
}

resource "azurerm_role_assignment" "tls" {
  scope                = "${azurerm_key_vault.this.id}/secrets/${local.names.tls_cert}"
  role_definition_name = "Key Vault Secrets User"
  principal_id         = var.identity.principal_id
  depends_on           = [azurerm_key_vault_certificate.tls]
}
