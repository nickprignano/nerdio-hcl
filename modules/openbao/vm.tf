locals {
  policy = <<-EOT
    path "azure/creds/${local.names.secret_role}" {
      capabilities = ["read"]
    }
  EOT

  openbao_hcl = templatefile("${path.module}/templates/openbao.hcl.tftpl", {
    address               = local.address
    tenant_id             = local.tenant_id
    subscription_id       = var.subscription_id
    key_vault_name        = azurerm_key_vault.this.name
    unseal_key_name       = azurerm_key_vault_key.unseal.name
    azure_plugin_image    = var.azure_plugin_image
    secret_role           = local.names.secret_role
    policy                = local.policy
    application_object_id = var.rest_client_application_object_id
    credential_ttl        = var.credential_ttl
    login_client_id       = azuread_application.login.client_id
    login_object_ids      = local.login_ids
    github_repository     = try(var.github_oidc.repository, null)
    github_environment    = try(var.github_oidc.environment, null)
  })

  cloud_init = templatefile("${path.module}/templates/cloud-init.yaml.tftpl", {
    openbao_hcl_b64    = base64encode(local.openbao_hcl)
    identity_client_id = var.identity.client_id
    key_vault_name     = azurerm_key_vault.this.name
    tls_cert_name      = azurerm_key_vault_certificate.tls.name
    openbao_version    = var.openbao_version.version
    openbao_sha256     = var.openbao_version.sha256
  })
}

# Azure requires an SSH key on a Linux VM. This one is never output and no rule lets SSH in;
# use Serial Console or Run Command for break-glass access.
resource "tls_private_key" "admin" {
  algorithm = "ED25519"
}

resource "azurerm_linux_virtual_machine" "this" {
  name                            = local.names.vm
  location                        = var.location
  resource_group_name             = var.resource_group_name
  size                            = var.vm_size
  admin_username                  = "azureadmin"
  disable_password_authentication = true
  network_interface_ids           = [azurerm_network_interface.this.id]
  secure_boot_enabled             = true
  vtpm_enabled                    = true
  # A config change replaces the VM, and the new one initializes itself from scratch.
  custom_data = base64encode(local.cloud_init)
  tags        = var.tags

  admin_ssh_key {
    username   = "azureadmin"
    public_key = tls_private_key.admin.public_key_openssh
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [var.identity.id]
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "StandardSSD_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }

  boot_diagnostics {}

  # The identity needs its Key Vault and Graph access before OpenBao first starts.
  depends_on = [
    azurerm_role_assignment.unseal,
    azurerm_role_assignment.tls,
    azuread_app_role_assignment.graph_owned_by,
    azurerm_subnet_network_security_group_association.this,
  ]
}
