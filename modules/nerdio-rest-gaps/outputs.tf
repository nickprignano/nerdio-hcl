output "uam_app_group_ids" {
  description = "UAM app group IDs keyed by logical key."
  value       = { for k, g in restapi_object.uam_app_group : k => g.id }
}
