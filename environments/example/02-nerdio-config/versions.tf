terraform {
  required_version = ">= 1.9"

  required_providers {
    nme = {
      source  = "nerdio/nme"
      version = "~> 0.1"
    }
  }

  # Use a separate state from 01-platform; see ../01-platform/backend.tf.example.
}

# The client secret comes from the NME_CLIENT_SECRET environment variable so it never lands
# in a tfvars file: export NME_CLIENT_SECRET="$(terraform -chdir=../01-platform output -raw nme_client_secret)"
provider "nme" {
  base_url  = var.nme_base_url
  tenant_id = var.nme_tenant_id
  client_id = var.nme_client_id
  scope     = var.nme_scope
}
