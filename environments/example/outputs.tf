output "nerdio_url" {
  description = "Open this to run Nerdio's install step and setup wizard."
  value       = "https://${module.nerdio_manager.app_service_hostname}"
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
  description = "App ID for Nerdio's \"Use existing AD app\" option."
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
  description = "Values for the Packer gallery variable."
  value = try({
    resource_group   = module.foundation.resource_group_names["hostpools"]
    name             = module.image_gallery[0].gallery_name
    image_definition = keys(module.image_gallery[0].image_definition_ids)[0]
    build_rg         = module.image_gallery[0].build_resource_group_name
  }, null)
}
