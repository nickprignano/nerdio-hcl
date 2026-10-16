output "gallery_name" {
  description = "Gallery name for the Packer gallery.name variable."
  value       = azurerm_shared_image_gallery.this.name
}

output "gallery_id" {
  description = "Gallery ID."
  value       = azurerm_shared_image_gallery.this.id
}

output "image_definition_ids" {
  description = "Image definition IDs keyed by name. Nerdio imports versions from these."
  value       = { for k, v in azurerm_shared_image.this : k => v.id }
}

output "build_resource_group_name" {
  description = "Resource group for the Packer build_resource_group variable."
  value       = azurerm_resource_group.build.name
}
