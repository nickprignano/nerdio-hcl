terraform {
  # Ephemeral resources in provider configuration need Terraform 1.10; the kit asks for 1.11.
  required_version = ">= 1.11"

  required_providers {
    # Installed from Nerdio's GitHub release into a local mirror (scripts/install-nme-provider.sh),
    # so plain `terraform init` works. The version is the release tag without the "v".
    nme = {
      source  = "nerdio/nme"
      version = "0.0.1-preview.1"
    }
    # Reads the REST client secret for the key_vault hand-off (decision 0015).
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.0"
    }
    # Talks to the optional OpenBao server for the openbao hand-off. Not configured otherwise.
    vault = {
      source  = "hashicorp/vault"
      version = "~> 5.0"
    }
  }

  # Use a separate state from 01-platform; see ../01-platform/backend.tf.example.
}

# Only the ephemeral Key Vault read uses azurerm, and only with the key_vault hand-off.
provider "azurerm" {
  features {}
  subscription_id                 = var.subscription_id
  tenant_id                       = var.nme_tenant_id
  resource_provider_registrations = "none"
}

# Only configured with the openbao hand-off. Login is a short-lived Entra token from
# `az account get-access-token` (Cloud Shell) or the job's GitHub OIDC token, in TF_VAR_openbao_jwt.
provider "vault" {
  address          = try(var.openbao.address, null)
  ca_cert_file     = var.openbao == null ? null : "${path.root}/openbao-ca.pem"
  skip_child_token = true

  dynamic "auth_login_jwt" {
    for_each = var.openbao == null ? [] : [var.openbao]
    content {
      mount = var.openbao_auth_mount
      role  = auth_login_jwt.value.role
      jwt   = var.openbao_jwt
    }
  }
}

# The REST client secret never sits in a file, the shell or state: it comes from the ephemeral
# resources in secrets.tf. With nme_secret_source = "output" (the old hand-off) it's null here,
# and the provider reads NME_CLIENT_SECRET instead.
provider "nme" {
  base_url      = var.nme_base_url
  tenant_id     = var.nme_tenant_id
  client_id     = var.nme_client_id
  scope         = var.nme_scope
  client_secret = local.nme_client_secret
}
