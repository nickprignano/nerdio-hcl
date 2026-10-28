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

output "remote_app_ids" {
  description = "Published RemoteApp IDs keyed by logical key."
  value       = { for k, app in restapi_object.remote_app : k => app.id }
}

output "uam_repository_ids" {
  description = "Custom UAM repository IDs keyed by logical key."
  value       = { for k, r in restapi_object.uam_repository : k => r.id }
}

output "uam_shell_app_ids" {
  description = "UAM Shell App IDs keyed by logical key."
  value       = { for k, a in restapi_object.uam_shell_app : k => a.id }
}

output "host_pool_reimage_schedule_ids" {
  description = "Host pool re-image schedule IDs keyed by host pool name."
  value       = { for k, s in restapi_object.host_pool_reimage_schedule : k => s.id }
}
