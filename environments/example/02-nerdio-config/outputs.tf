output "workspace_id" {
  description = "AVD workspace ID."
  value       = module.nerdio_config.workspace_id
}

output "host_pool_ids" {
  description = "Dynamic host pool IDs keyed by name."
  value       = module.nerdio_config.host_pool_ids
}

output "static_host_pool_ids" {
  description = "Static host pool IDs keyed by name."
  value       = module.nerdio_config.static_host_pool_ids
}

output "fslogix_profile_id" {
  description = "Nerdio FSLogix profile ID, or null."
  value       = module.nerdio_config.fslogix_profile_id
}

output "auto_scale_profile_id" {
  description = "Nerdio auto-scale profile ID."
  value       = module.nerdio_config.auto_scale_profile_id
}

output "rdp_profile_ids" {
  description = "Nerdio RDP profile IDs keyed by logical key."
  value       = module.nerdio_config.rdp_profile_ids
}

output "vm_deployment_profile_ids" {
  description = "Nerdio VM deployment profile IDs keyed by logical key."
  value       = module.nerdio_config.vm_deployment_profile_ids
}

output "scripted_action_ids" {
  description = "Nerdio scripted action IDs keyed by logical key."
  value       = module.nerdio_config.scripted_action_ids
}

output "scripted_action_group_ids" {
  description = "Nerdio scripted action group IDs keyed by logical key."
  value       = module.nerdio_config.scripted_action_group_ids
}

output "scripted_action_profile_ids" {
  description = "Nerdio scripted action profile IDs keyed by logical key."
  value       = module.nerdio_config.scripted_action_profile_ids
}
