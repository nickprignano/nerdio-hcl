output "nerdio_url" {
  description = "Nerdio Manager console. Open it for the setup wizard (and, for the marketplace install, the install step first). Null before a portal Marketplace deployment exists in the resource group."
  value       = local.nerdio_hostname != null ? "https://${local.nerdio_hostname}" : null
}

output "avd_vnet_name" {
  description = "Select this network in the Nerdio setup wizard."
  value       = module.network.vnet_name
}

output "resource_group_names" {
  description = "Resource groups to link in Nerdio (host pools, storage)."
  value       = module.foundation.resource_group_names
}

output "fslogix_share_unc" {
  description = "FSLogix VHDLocations value for the Nerdio FSLogix profile."
  value       = try(module.fslogix[0].profile_share_unc, null)
}

output "entra_app_client_id" {
  description = "Nerdio Entra app ID (also the App ID for the marketplace install's \"Use existing AD app\" option)."
  value       = try(module.nerdio_identity[0].client_id, null)
}

output "entra_app_service_principal_id" {
  description = "Service Principal ID for Nerdio's \"Use existing AD app\" option."
  value       = try(module.nerdio_identity[0].service_principal_object_id, null)
}

output "entra_app_client_secret" {
  description = "App Secret for Nerdio's \"Use existing AD app\" option. Read with terraform output -raw."
  value       = try(module.nerdio_identity[0].client_secret, null)
  sensitive   = true
}

output "packer_gallery" {
  description = "Values for the Packer gallery variable and Compute Gallery image definition IDs."
  value = try({
    resource_group       = module.foundation.resource_group_names["hostpools"]
    name                 = module.image_gallery[0].gallery_name
    image_definition     = keys(module.image_gallery[0].image_definition_ids)[0]
    image_definition_ids = module.image_gallery[0].image_definition_ids
    build_rg             = module.image_gallery[0].build_resource_group_name
  }, null)
}

output "nerdio_config_inputs" {
  description = <<-EOT
    Inputs for 02-nerdio-config, keyed by its variable names. Write them out with
    terraform output -json nerdio_config_inputs > ../02-nerdio-config/platform.auto.tfvars.json
  EOT
  value = {
    nme_base_url                  = local.nerdio_hostname != null ? "https://${local.nerdio_hostname}" : null
    nme_tenant_id                 = var.tenant_id
    nme_client_id                 = try(module.nerdio_identity[0].rest_api_client_id, null)
    nme_scope                     = try("api://${module.nerdio_identity[0].client_id}/.default", null)
    subscription_id               = var.subscription_id
    location                      = var.location
    hostpools_resource_group_name = module.foundation.resource_group_names["hostpools"]
    network = {
      resource_group_name = module.foundation.resource_group_names["network"]
      vnet_name           = module.network.vnet_name
      subnet_name         = module.network.session_host_subnet_name
    }
    fslogix_profile_share_unc    = try(module.fslogix[0].profile_share_unc, null)
    gallery_image_definition_ids = try(module.image_gallery[0].image_definition_ids, {})
    # How stage 2 gets the REST client secret (decision 0015). None of these are secrets.
    nme_secret_source = local.nme_secret_store
    nme_key_vault = try({
      id          = module.nerdio_secrets[0].key_vault_id
      secret_name = module.nerdio_secrets[0].secret_name
    }, null)
    openbao = try({
      address = module.openbao[0].address
      role    = module.openbao[0].secret_role
      scope   = module.openbao[0].login_scope
    }, null)
  }
}

output "nme_client_secret" {
  description = "Only with nme_secret_store = \"output\": the REST API client secret for 02-nerdio-config. Export as NME_CLIENT_SECRET; never write it to a file."
  value       = local.nme_secret_store == "output" ? try(module.nerdio_identity[0].rest_api_client_secret, null) : null
  sensitive   = true
}

output "openbao_ca_cert" {
  description = "OpenBao's TLS certificate, which stage 2 trusts. Public. Write it to 02-nerdio-config/openbao-ca.pem."
  value       = try(module.openbao[0].ca_cert_pem, null)
}

output "github_oidc_client_id" {
  description = "Client ID for a GitHub Actions job to sign in with OIDC (azure/login), when nme_secret.github_oidc is set. Not a secret."
  value       = try(module.nerdio_secrets[0].github_client_id, null)
}
