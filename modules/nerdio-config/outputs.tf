output "workspace_id" {
  description = "AVD workspace ID."
  value       = nme_workspace.this.id
}

output "host_pool_ids" {
  description = "Host pool IDs keyed by name."
  value       = { for k, hp in nme_dynamic_host_pool.this : k => hp.id }
}

output "fslogix_profile_id" {
  description = "Nerdio FSLogix profile ID, or null."
  value       = try(nme_fslogix_profile.this[0].id, null)
}

output "auto_scale_profile_id" {
  description = "Nerdio auto-scale profile ID."
  value       = nme_auto_scale_profile.this.id
}
