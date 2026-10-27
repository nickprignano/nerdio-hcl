output "uam_app_group_ids" {
  description = "UAM app group IDs keyed by logical key."
  value       = { for k, g in restapi_object.uam_app_group : k => g.id }
}

output "app_attach_package_ids" {
  description = "App Attach package IDs keyed by logical key."
  value       = { for k, p in restapi_object.app_attach_package : k => p.id }
}

output "desktop_image_ids" {
  description = "Nerdio desktop image pipeline IDs keyed by logical key."
  value       = { for k, img in restapi_object.desktop_image : k => img.id }
}
