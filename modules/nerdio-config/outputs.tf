output "workspace_ids" {
  description = "AVD workspace IDs keyed by workspace key."
  value       = { for k, ws in nme_workspace.this : k => ws.id }
}

output "workspace_id" {
  description = "Default AVD workspace ID (first sorted workspace key)."
  value       = nme_workspace.this[local.default_workspace_key].id
}

output "host_pool_ids" {
  description = "Dynamic host pool IDs keyed by name."
  value       = { for k, hp in nme_dynamic_host_pool.this : k => hp.id }
}

output "static_host_pool_ids" {
  description = "Static host pool IDs keyed by name."
  value       = { for k, hp in nme_static_host_pool.this : k => hp.id }
}

output "fslogix_profile_id" {
  description = "Primary Nerdio FSLogix profile ID, or null."
  value       = try(nme_fslogix_profile.this[0].id, null)
}

output "regional_fslogix_profile_ids" {
  description = "Secondary regional Nerdio FSLogix profile IDs keyed by region key."
  value       = { for k, p in nme_fslogix_profile.regional : k => p.id }
}

output "auto_scale_profile_id" {
  description = "Nerdio auto-scale profile ID."
  value       = nme_auto_scale_profile.this.id
}

output "rdp_profile_ids" {
  description = "Nerdio RDP profile IDs keyed by logical key."
  value       = { for k, p in nme_rdp_profile.this : k => p.id }
}

output "vm_deployment_profile_ids" {
  description = "Nerdio VM deployment profile IDs keyed by logical key."
  value       = { for k, p in nme_vm_deployment_profile.this : k => p.id }
}

output "scripted_action_ids" {
  description = "Nerdio scripted action IDs keyed by logical key."
  value       = { for k, a in nme_scripted_action.this : k => a.id }
}

output "scripted_action_group_ids" {
  description = "Nerdio scripted action group IDs keyed by logical key."
  value       = { for k, g in nme_scripted_action_group.this : k => g.id }
}

output "scripted_action_profile_ids" {
  description = "Nerdio scripted action profile IDs keyed by logical key."
  value       = { for k, p in nme_scripted_action_profile.this : k => p.id }
}
