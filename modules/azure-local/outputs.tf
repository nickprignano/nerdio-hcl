output "logical_network_id" {
  description = "ARM resource ID of the Azure Local logical network for Nerdio hybrid AVD session hosts."
  value       = azapi_resource.logical_network.id
}

output "custom_location_id" {
  description = "ARM resource ID of the Azure Local Custom Location."
  value       = var.custom_location_id
}

output "gallery_image_ids" {
  description = "ARM resource IDs of Azure Local gallery images keyed by name."
  value       = { for k, img in azapi_resource.gallery_image : k => img.id }
}
